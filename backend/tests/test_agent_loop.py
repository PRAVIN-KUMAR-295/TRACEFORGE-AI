import pytest
from unittest.mock import AsyncMock, patch
from backend.app.config import settings
from backend.app.database.falkordb_client import falkor_client
from backend.app.database.seed_data import seed_graph_database
from backend.app.models.schemas import ActionStatus
from backend.app.services.investigation_engine import (
    investigation_engine,
    AVAILABLE_TOOLS_MANIFEST,
    PERMITTED_TOOL_NAMES,
)
from backend.app.services.llm_provider import llm_provider


@pytest.fixture(autouse=True)
def setup_graph():
    seed_graph_database(falkor_client)


@pytest.mark.asyncio
async def test_agent_loop_dynamic_tool_selection():
    """Verify autonomous agent loop selects permitted tools and produces grounded findings."""
    result = await investigation_engine.run_autonomous_agent_loop("INC-2026-1042")

    assert result.incident_id == "INC-2026-1042"
    assert result.status == "IDENTIFIED"
    assert len(result.tool_execution_trace) >= 3

    # Verify tool names used are in permitted set
    executed_tool_names = [t.tool_name for t in result.tool_execution_trace]
    for name in executed_tool_names:
        assert name.lower().replace("_", "").replace("-", "") in PERMITTED_TOOL_NAMES

    # Verify findings are grounded in graph evidence
    assert len(result.confirmed_facts) >= 3
    for fact in result.confirmed_facts:
        assert fact.is_confirmed_fact is True
        assert len(fact.cypher_proof_query) > 0

    assert len(result.memory_matches) >= 1
    assert result.memory_matches[0].incident_id == "INC-2026-0814"


@pytest.mark.asyncio
async def test_agent_loop_rejects_invalid_tool_calls_safely():
    """Verify agent loop rejects unknown or forbidden tool names safely with an ERROR trace."""
    mock_decisions = [
        # Step 1: Model attempts an unsupported tool
        {
            "action": "call_tool",
            "tool_name": "ArbitraryBashExecutionTool",
            "tool_args": {"cmd": "rm -rf /"},
            "thought": "Attempting unauthorized command.",
        },
        # Step 2: Model calls valid tool
        {
            "action": "call_tool",
            "tool_name": "CypherQueryTool",
            "tool_args": {
                "query": "MATCH (i:Incident {id: $incident_id}) RETURN i",
                "params": {"incident_id": "INC-2026-1042"},
            },
            "thought": "Recovering and calling permitted tool.",
        },
        # Step 3: Finish
        {
            "action": "finish",
            "thought": "Finishing test investigation.",
        },
    ]

    with patch.object(llm_provider, "decide_next_tool_action", side_effect=mock_decisions):
        result = await investigation_engine.run_autonomous_agent_loop("INC-2026-1042", max_iterations=4)

        # Step 1 must be recorded as ERROR without crashing
        assert len(result.tool_execution_trace) >= 1
        first_step = result.tool_execution_trace[0]
        assert first_step.tool_name == "ArbitraryBashExecutionTool"
        assert first_step.status == "ERROR"
        assert "Rejected unsupported tool" in first_step.summary
        assert first_step.rows_returned == 0

        # Subsequent step executed successfully
        second_step = result.tool_execution_trace[1]
        assert second_step.tool_name == "CypherQueryTool"
        assert second_step.status == "SUCCESS"


@pytest.mark.asyncio
async def test_agent_loop_handles_malformed_arguments_safely():
    """Verify agent loop catches invalid or missing parameters in tool calls."""
    mock_decisions = [
        # Call CypherQueryTool without a query string
        {
            "action": "call_tool",
            "tool_name": "CypherQueryTool",
            "tool_args": {"wrong_param": 123},
            "thought": "Malformed arguments without query.",
        },
        # Finish
        {
            "action": "finish",
            "thought": "Finishing.",
        },
    ]

    with patch.object(llm_provider, "decide_next_tool_action", side_effect=mock_decisions):
        result = await investigation_engine.run_autonomous_agent_loop("INC-2026-1042", max_iterations=3)

        assert len(result.tool_execution_trace) >= 1
        malformed_step = result.tool_execution_trace[0]
        assert malformed_step.tool_name == "CypherQueryTool"
        assert malformed_step.status == "ERROR"
        assert "missing or invalid 'query'" in malformed_step.summary


@pytest.mark.asyncio
async def test_agent_loop_bounded_max_iterations():
    """Verify agent loop strictly halts when max_iterations limit is reached."""
    # Endless tool-call generator
    endless_decision = {
        "action": "call_tool",
        "tool_name": "CypherQueryTool",
        "tool_args": {
            "query": "MATCH (n:Service) RETURN n.id",
            "params": {},
        },
        "thought": "Keep calling endlessly.",
    }

    with patch.object(llm_provider, "decide_next_tool_action", return_value=endless_decision):
        # Set max_iterations = 3
        result = await investigation_engine.run_autonomous_agent_loop("INC-2026-1042", max_iterations=3)

        # The loop must have terminated at exactly 3 steps (plus fallback completion if required)
        agent_steps = [t for t in result.tool_execution_trace if t.operation == "agent_cypher_query"]
        assert len(agent_steps) == 3


@pytest.mark.asyncio
async def test_investigate_incident_fallback_on_agent_failure():
    """Verify investigate_incident seamlessly falls back to sequential pipeline on agent exception."""
    with patch.object(investigation_engine, "run_autonomous_agent_loop", side_effect=RuntimeError("LLM API connection dropped")):
        # Request with enable_agent_mode=True
        result = await investigation_engine.investigate_incident(
            "INC-2026-1042",
            enable_agent_mode=True
        )

        # Must not raise RuntimeError; must successfully fallback to sequential pipeline
        assert result.incident_id == "INC-2026-1042"
        assert result.status == "IDENTIFIED"
        assert len(result.tool_execution_trace) == 3
        assert len(result.confirmed_facts) >= 3


@pytest.mark.asyncio
async def test_agent_mode_preserves_human_approval_requirement():
    """Verify all proposed remediation actions require human approval and are NEVER auto-executed."""
    result = await investigation_engine.investigate_incident(
        "INC-2026-1042",
        enable_agent_mode=True
    )

    assert len(result.recommended_actions) >= 1
    for action in result.recommended_actions:
        assert action.requires_human_approval is True
        assert action.status == ActionStatus.PENDING_APPROVAL
        assert action.executed_at is None
        assert "DRY RUN OK" in action.dry_run_output


@pytest.mark.asyncio
async def test_agent_trace_order_and_metrics_integrity():
    """Verify tool execution trace ordering, timing, and parameters recording."""
    result = await investigation_engine.investigate_incident(
        "INC-2026-1042",
        enable_agent_mode=True
    )

    trace = result.tool_execution_trace
    assert len(trace) >= 3

    # Step numbers must be strictly sequential (1, 2, 3...)
    step_numbers = [t.step_number for t in trace]
    assert step_numbers == list(range(1, len(trace) + 1))

    for item in trace:
        assert item.execution_time_ms >= 0.0
        assert item.status in ("SUCCESS", "EMPTY", "ERROR")
        assert isinstance(item.input_parameters, dict)
        assert len(item.summary) > 0


@pytest.mark.asyncio
async def test_agent_grounded_in_dynamic_graph_data():
    """Verify agent findings dynamically adapt to real graph changes and do not invent facts."""
    orig_connected = falkor_client.is_connected
    try:
        falkor_client.is_connected = False
        g = falkor_client.memory_engine
        g.add_node("INC-AGENT-DYN", "Incident", {
            "id": "INC-AGENT-DYN",
            "title": "Payment Gateway Timeout",
            "affected_service": "payment-service"
        })
        g.add_node("stripe-external-api", "Service", {
            "id": "stripe-external-api",
            "name": "Stripe Gateway API",
        })
        g.add_edge("INC-AGENT-DYN", "payment-service", "AFFECTS", {})
        g.add_edge("payment-service", "stripe-external-api", "DEPENDS_ON", {"type": "HTTPS", "timeout_ms": 3500})

        result = await investigation_engine.investigate_incident(
            "INC-AGENT-DYN",
            enable_agent_mode=True
        )

        assert result.incident_id == "INC-AGENT-DYN"
        fact_targets = [f.target_node for f in result.confirmed_facts]
        assert "stripe-external-api" in fact_targets
    finally:
        falkor_client.is_connected = orig_connected


@pytest.mark.asyncio
async def test_ollama_provider_not_diverted_merely_due_to_empty_api_key():
    """Verify Ollama does not divert to deterministic mode merely because its API key is None or empty."""
    from backend.app.services.llm_provider import LLMProvider

    provider = LLMProvider(provider="ollama", api_key=None, model="llama3.2:1b")
    mock_resp = {
        "action": "call_tool",
        "tool_name": "CypherQueryTool",
        "tool_args": {"query": "MATCH (i:Incident) RETURN i"},
        "thought": "Ollama autonomous decision reached successfully.",
    }

    with patch.object(provider, "_call_llm_tool_decision", AsyncMock(return_value=mock_resp)) as mock_call:
        decision = await provider.decide_next_tool_action(
            incident_data={"id": "INC-TEST"},
            available_tools=AVAILABLE_TOOLS_MANIFEST,
            observations=[],
            iteration=1,
            max_iterations=5,
        )

        mock_call.assert_called_once()
        assert decision["thought"] == "Ollama autonomous decision reached successfully."
        assert decision["tool_name"] == "CypherQueryTool"


@pytest.mark.asyncio
async def test_demo_mode_remains_deterministic():
    """Verify demo mode remains strictly deterministic regardless of whether an API key is present."""
    from backend.app.services.llm_provider import LLMProvider

    provider = LLMProvider(provider="demo", api_key="dummy-key")
    decision = await provider.decide_next_tool_action(
        incident_data={"id": "INC-TEST"},
        available_tools=AVAILABLE_TOOLS_MANIFEST,
        observations=[],
        iteration=1,
        max_iterations=5,
    )

    assert decision["action"] == "call_tool"
    assert decision["tool_name"] == "CypherQueryTool"
    assert "Establish baseline incident properties" in decision["thought"]


@pytest.mark.asyncio
async def test_cloud_providers_without_keys_safely_fallback():
    """Verify cloud providers without configured API keys safely fall back to deterministic policy."""
    from backend.app.services.llm_provider import LLMProvider

    for cloud_p in ("openai", "anthropic", "gemini", "groq"):
        provider = LLMProvider(provider=cloud_p, api_key=None)
        decision = await provider.decide_next_tool_action(
            incident_data={"id": "INC-TEST"},
            available_tools=AVAILABLE_TOOLS_MANIFEST,
            observations=[],
            iteration=1,
            max_iterations=5,
        )
        assert decision["action"] == "call_tool"
        assert decision["tool_name"] == "CypherQueryTool"


@pytest.mark.asyncio
async def test_ollama_connection_errors_and_malformed_responses_fallback_safely():
    """Verify Ollama network failures or malformed outputs fall back safely to deterministic reasoning."""
    import httpx
    from backend.app.services.llm_provider import LLMProvider

    provider = LLMProvider(provider="ollama", api_key=None, model="llama3.2:1b")

    # Case 1: Local server offline / ConnectionRefusedError
    with patch.object(provider, "_call_llm_tool_decision", side_effect=httpx.ConnectError("Connection refused to 127.0.0.1:11434")):
        fallback_decision = await provider.decide_next_tool_action(
            incident_data={"id": "INC-TEST"},
            available_tools=AVAILABLE_TOOLS_MANIFEST,
            observations=[],
            iteration=1,
            max_iterations=5,
        )
        assert fallback_decision["action"] == "call_tool"
        assert fallback_decision["tool_name"] == "CypherQueryTool"
        assert "Establish baseline incident properties" in fallback_decision["thought"]

    # Case 2: Malformed response / json parse error
    with patch.object(provider, "_call_llm_tool_decision", side_effect=ValueError("Invalid JSON from LLM")):
        fallback_decision2 = await provider.decide_next_tool_action(
            incident_data={"id": "INC-TEST"},
            available_tools=AVAILABLE_TOOLS_MANIFEST,
            observations=[],
            iteration=1,
            max_iterations=5,
        )
        assert fallback_decision2["action"] == "call_tool"
        assert fallback_decision2["tool_name"] == "CypherQueryTool"


def test_build_tool_decision_prompt_contains_explicit_arguments_and_schema_examples():
    """Verify LLM prompt explicitly enumerates required tool arguments and valid schema examples."""
    prompt = llm_provider._build_tool_decision_prompt(
        incident_data={"id": "INC-2026-1042", "title": "Checkout Cascade"},
        available_tools=AVAILABLE_TOOLS_MANIFEST,
        observations=[],
        iteration=1,
        max_iterations=4,
    )

    assert "CypherQueryTool: REQUIRED tool_args -> {'query':" in prompt
    assert "DependencyCascadeTool: REQUIRED tool_args -> {'incident_id': 'INC-2026-1042'}" in prompt
    assert "MemoryRetrievalTool: REQUIRED tool_args -> {'incident_id': 'INC-2026-1042'}" in prompt
    assert "Example A - CypherQueryTool" in prompt
    assert "Example B - DependencyCascadeTool" in prompt
    assert "Example C - MemoryRetrievalTool" in prompt
    assert "MATCH (i:Incident {id: $incident_id}) RETURN i" in prompt


@pytest.mark.asyncio
async def test_agent_loop_bounded_retry_on_premature_finish():
    """Verify agent loop gives guidance observation and allows bounded retry if model tries to finish with 0 tools executed."""
    mock_decisions = [
        # Decision 1: Model immediately tries to finish before calling any tool due to parameter confusion
        {"action": "finish", "thought": "Premature finish due to error in query parameter."},
        # Decision 2: Model calls valid tool after receiving guidance observation
        {
            "action": "call_tool",
            "tool_name": "CypherQueryTool",
            "tool_args": {
                "query": "MATCH (i:Incident {id: $incident_id}) RETURN i",
                "params": {"incident_id": "INC-2026-1042"},
            },
            "thought": "Retrying with required tool.",
        },
        # Decision 3: Finish after successful tool execution
        {"action": "finish", "thought": "Conclude investigation after gathering facts."},
    ]

    with patch.object(llm_provider, "decide_next_tool_action", side_effect=mock_decisions):
        result = await investigation_engine.run_autonomous_agent_loop("INC-2026-1042", max_iterations=4)

        # Confirm step was not aborted immediately at iteration 1
        executed_tools = [t.tool_name for t in result.tool_execution_trace]
        assert "CypherQueryTool" in executed_tools
        cypher_step = next(t for t in result.tool_execution_trace if t.tool_name == "CypherQueryTool")
        assert cypher_step.status == "SUCCESS"
        assert "[Autonomous LLM Call]" in cypher_step.summary


@pytest.mark.asyncio
async def test_trace_clearly_distinguishes_autonomous_llm_vs_deterministic_fallback():
    """Verify trace and provider label clearly distinguish autonomous calls from deterministic fallback."""
    # Only execute CypherQueryTool autonomously, leaving DependencyCascadeTool and MemoryRetrievalTool to fallback
    mock_decisions = [
        {
            "action": "call_tool",
            "tool_name": "CypherQueryTool",
            "tool_args": {
                "query": "MATCH (i:Incident {id: $incident_id}) RETURN i",
                "params": {"incident_id": "INC-2026-1042"},
            },
            "thought": "Only inspect incident node.",
        },
        {"action": "finish", "thought": "Stop here."},
    ]

    with patch.object(llm_provider, "decide_next_tool_action", side_effect=mock_decisions):
        result = await investigation_engine.run_autonomous_agent_loop("INC-2026-1042", max_iterations=3)

        # Provider mode must be hybrid, NOT purely autonomous
        assert "hybrid-agent-fallback" in result.llm_provider_used

        # Autonomous call marked in trace
        auto_step = next(t for t in result.tool_execution_trace if t.tool_name == "CypherQueryTool")
        assert "[Autonomous LLM Call]" in auto_step.summary

        # Fallback calls marked in trace with [Deterministic Fallback] prefix and distinct operations
        fallback_steps = [t for t in result.tool_execution_trace if "[Deterministic Fallback]" in t.summary]
        assert len(fallback_steps) == 2
        for fb in fallback_steps:
            assert fb.operation.startswith("deterministic_fallback_")
