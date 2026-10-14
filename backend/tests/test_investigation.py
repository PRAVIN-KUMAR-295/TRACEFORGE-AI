import pytest
from backend.app.database.falkordb_client import falkor_client
from backend.app.database.seed_data import seed_graph_database
from backend.app.services.investigation_engine import investigation_engine
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
