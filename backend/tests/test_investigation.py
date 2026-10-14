import pytest
from backend.app.database.falkordb_client import falkor_client
from backend.app.database.seed_data import seed_graph_database
from backend.app.services.investigation_engine import investigation_engine, _safe_get_dict
from backend.app.services.memory_service import memory_service
from backend.app.services.remediation_service import remediation_service


@pytest.fixture(autouse=True)
def setup_graph():
    seed_graph_database(falkor_client)


@pytest.mark.asyncio
async def test_end_to_end_investigation():
    result = await investigation_engine.investigate_incident("INC-2026-1042")

    assert result.incident_id == "INC-2026-1042"
    assert result.status == "IDENTIFIED"
    assert len(result.confirmed_facts) >= 3
    assert len(result.root_cause_hypotheses) >= 1
    assert len(result.memory_matches) >= 1
    assert len(result.recommended_actions) >= 2
    assert len(result.cypher_queries_executed) >= 4

    # Verify fact vs hypothesis separation
    for fact in result.confirmed_facts:
        assert fact.is_confirmed_fact is True
        assert fact.confidence_score >= 0.95
        assert len(fact.cypher_proof_query) > 0

    for hyp in result.root_cause_hypotheses:
        assert hyp.is_confirmed_fact is False
        assert len(hyp.evidence_path) > 0

    # Verify historical memory match
    top_match = result.memory_matches[0]
    assert top_match.incident_id == "INC-2026-0814"
    assert top_match.similarity_score >= 0.90
    assert "Redis" in top_match.root_cause_summary


@pytest.mark.asyncio
async def test_different_incidents_produce_different_findings():
    """Verify that different incident graphs produce dynamically distinct findings."""
    res_1042 = await investigation_engine.investigate_incident("INC-2026-1042")
    res_0702 = await investigation_engine.investigate_incident("INC-2026-0702")

    # res_1042 is checkout/auth failure
    nodes_1042 = {f.source_node for f in res_1042.confirmed_facts} | {f.target_node for f in res_1042.confirmed_facts}
    assert "auth-service" in nodes_1042 or "checkout-service" in nodes_1042

    # res_0702 is order processing
    nodes_0702 = {f.source_node for f in res_0702.confirmed_facts} | {f.target_node for f in res_0702.confirmed_facts}
    assert "deploy-auth-v2.4.1" not in nodes_0702
    assert res_1042.incident_id != res_0702.incident_id


@pytest.mark.asyncio
async def test_empty_or_missing_incident_query_results_handled_safely():
    """Verify non-existent incident produces no fabricated facts or crashes."""
    result = await investigation_engine.investigate_incident("INC-NONEXISTENT-9999")

    assert result.incident_id == "INC-NONEXISTENT-9999"
    # Must not invent confirmed facts or memory matches from non-existent incident
    assert len(result.confirmed_facts) == 0
    assert len(result.memory_matches) == 0
    # Hypotheses should clearly indicate insufficient evidence
    assert len(result.root_cause_hypotheses) >= 1
    assert result.root_cause_hypotheses[0].confidence_score <= 0.30
    assert "Insufficient Graph Evidence" in result.root_cause_hypotheses[0].title


def test_unexpected_row_shapes_handled_safely():
    """Verify that malformed row elements do not crash the parser."""
    assert _safe_get_dict(None) == {}
    assert _safe_get_dict(12345) == {}
    assert _safe_get_dict([]) == {}
    assert _safe_get_dict({"id": "node-1", "name": "Node 1"}) == {"id": "node-1", "name": "Node 1"}

    class MockNode:
        properties = {"id": "mock-id", "tier": "edge"}

    assert _safe_get_dict(MockNode()) == {"id": "mock-id", "tier": "edge"}


@pytest.mark.asyncio
async def test_findings_derived_from_query_results():
    """Verify that adding new graph nodes directly alters the derived findings."""
    g = falkor_client.memory_engine
    g.add_node("INC-DYNAMIC-TEST", "Incident", {
        "id": "INC-DYNAMIC-TEST",
        "title": "Inventory Deadlock",
        "affected_service": "inventory-service"
    })
    g.add_edge("INC-DYNAMIC-TEST", "inventory-service", "AFFECTS", {})
    g.add_edge("inventory-service", "order-service", "DEPENDS_ON", {"type": "gRPC", "critical": True, "timeout_ms": 1200})

    result = await investigation_engine.investigate_incident("INC-DYNAMIC-TEST")

    # Verify dependency fact is dynamically derived
    fact_targets = [f.target_node for f in result.confirmed_facts]
    assert "order-service" in fact_targets
    dep_fact = next(f for f in result.confirmed_facts if f.target_node == "order-service")
    assert dep_fact.source_node == "inventory-service"
    assert dep_fact.relationship_type == "DEPENDS_ON"
    assert "1200ms" in dep_fact.description


def test_persistent_memory_storage_and_search():
    res = memory_service.store_postmortem(
        incident_id="INC-2026-TEST",
        title="Kafka Lag Overflow in Notifications",
        affected_service="notification-service",
        root_cause_summary="Consumer partition skew caused 12k unhandled events.",
        resolution_strategy="Rebalanced topic partitions from 4 to 16.",
        transferrable_fix="Scale partition count.",
        impacted_services=["notification-service"]
    )
    assert res["status"] == "STORED"

    search_res = memory_service.search_memory("partition", service="notification-service")
    assert len(search_res) >= 1
    assert search_res[0]["id"] == "INC-2026-TEST"


@pytest.mark.asyncio
async def test_human_approval_remediation_workflow():
    result = await investigation_engine.investigate_incident("INC-2026-1042")
    inv_id = result.investigation_id
    action_id = result.recommended_actions[0].action_id

    # Verify action requires human approval
    assert result.recommended_actions[0].requires_human_approval is True
    assert result.recommended_actions[0].status == "PENDING_APPROVAL"

    # Process Approval
    approval_res = remediation_service.process_action_approval(
        investigation_id=inv_id,
        action_id=action_id,
        approved=True,
        approved_by="Lead SRE Alex",
        notes="Safe to apply config change."
    )

    assert approval_res["status"] == "EXECUTED"
    assert approval_res["approved_by"] == "Lead SRE Alex"

    # Verify updated status
    updated_inv = investigation_engine.get_investigation(inv_id)
    assert updated_inv.recommended_actions[0].status == "EXECUTED"
    assert updated_inv.status == "MITIGATED"


@pytest.mark.asyncio
async def test_cypher_query_tool_structured_result_and_sanitization():
    from backend.app.services.investigation_tools import cypher_query_tool, safe_sanitize_params

    # 1. Parameter sanitization check
    sensitive_params = {
        "incident_id": "INC-2026-1042",
        "auth_token": "secret-token-12345",
        "api_key": "sk-real-live-api-key-999",
        "nested": {"password": "mypassword123", "normal": "value"}
    }
    sanitized = safe_sanitize_params(sensitive_params)
    assert sanitized["incident_id"] == "INC-2026-1042"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert sanitized["nested"]["normal"] == "value"

    # 2. Tool execution returns structured result
    res = cypher_query_tool.execute(
        query="MATCH (s:Service) WHERE s.id = $service_id RETURN s",
        params={"service_id": "auth-service"},
        purpose="Find auth service node"
    )
    assert res.success is True
    assert res.error is None
    assert res.row_count >= 1
    assert res.execution_time_ms >= 0
    assert len(res.rows) >= 1
    s_data = _safe_get_dict(res.rows[0][0])
    assert s_data.get("name") == "Authentication Service"


@pytest.mark.asyncio
async def test_dependency_cascade_tool_graph_traversal():
    from backend.app.services.investigation_tools import dependency_cascade_tool

    res = dependency_cascade_tool.explore(incident_id="INC-2026-1042", step_number=2)
    assert len(res.affected_services) >= 1
    assert any(s.get("id") == "checkout-service" for s in res.affected_services)

    # Verify downstream dependencies found
    dep_targets = {d.get("id") for d in res.dependencies if "id" in d}
    assert "auth-service" in dep_targets or "payment-service" in dep_targets or "order-service" in dep_targets

    # Verify confirmed facts and Cypher logs produced
    assert len(res.confirmed_facts) >= 2
    assert len(res.query_logs) >= 3
    assert res.tool_record.tool_name == "DependencyCascadeTool"


@pytest.mark.asyncio
async def test_memory_retrieval_tool_grounded_records():
    from backend.app.services.investigation_tools import memory_retrieval_tool

    # Precedent match for INC-2026-1042 auth service
    res = memory_retrieval_tool.retrieve(incident_id="INC-2026-1042", step_number=3)
    assert len(res.matches) >= 1
    assert res.matches[0].incident_id == "INC-2026-0814"
    assert "Redis" in res.matches[0].root_cause_summary
    assert len(res.query_logs) >= 1
    assert res.tool_record.tool_name == "MemoryRetrievalTool"

    # Empty match for totally unrelated non-existent incident
    empty_res = memory_retrieval_tool.retrieve(incident_id="INC-NONEXISTENT", step_number=3)
    assert len(empty_res.matches) == 0
    assert empty_res.tool_record.status == "EMPTY"


@pytest.mark.asyncio
async def test_investigation_trace_recorded_in_order_with_backward_compatibility():
    result = await investigation_engine.investigate_incident("INC-2026-1042")

    # 1. Trace presence and sequence
    assert hasattr(result, "tool_execution_trace")
    assert len(result.tool_execution_trace) == 3

    tool_names = [t.tool_name for t in result.tool_execution_trace]
    assert tool_names == [
        "CypherQueryTool",
        "DependencyCascadeTool",
        "MemoryRetrievalTool"
    ]

    for trace_item in result.tool_execution_trace:
        assert trace_item.status in ("SUCCESS", "EMPTY")
        assert trace_item.execution_time_ms >= 0
        assert len(trace_item.operation) > 0
        assert len(trace_item.summary) > 0

    # 2. Backward compatibility with existing fields
    assert result.incident_id == "INC-2026-1042"
    assert result.status == "IDENTIFIED"
    assert len(result.confirmed_facts) >= 3
    assert len(result.root_cause_hypotheses) >= 1
    assert len(result.memory_matches) >= 1
    assert len(result.recommended_actions) >= 2
    assert len(result.cypher_queries_executed) >= 4


