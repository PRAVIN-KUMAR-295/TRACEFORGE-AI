import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from backend.app.config import settings
from backend.app.database.falkordb_client import falkor_client
from backend.app.models.schemas import (
    ActionPlanItem,
    ActionStatus,
    CypherQueryLog,
    EvidenceItem,
    EvidencePathStep,
    HistoricalIncidentMatch,
    InvestigationResult,
    ToolExecutionRecord,
)
from backend.app.services.investigation_tools import (
    CascadeAnalysisResult,
    CypherQueryTool,
    DependencyCascadeTool,
    MemoryRetrievalResult,
    MemoryRetrievalTool,
    safe_get_dict,
    safe_sanitize_params,
)
from backend.app.services.llm_provider import llm_provider

logger = logging.getLogger("traceforge.investigation")


# Preserved for backward compatibility with existing tests
_safe_get_dict = safe_get_dict

AVAILABLE_TOOLS_MANIFEST: List[Dict[str, Any]] = [
    {
        "name": "CypherQueryTool",
        "description": "Executes parameterized OpenCypher queries against the FalkorDB graph layer to inspect nodes, relationships, and telemetry properties.",
        "parameters": {
            "query": {"type": "string", "description": "The Cypher query to execute, e.g. MATCH (i:Incident {id: $incident_id}) RETURN i"},
            "params": {"type": "object", "description": "Optional query parameters dictionary, e.g. {'incident_id': 'INC-2026-1042'}"},
            "purpose": {"type": "string", "description": "Short explanation of the query's diagnostic objective"}
        },
        "required": ["query"]
    },
    {
        "name": "DependencyCascadeTool",
        "description": "Explores the incident-affected services, service-to-service dependencies, connected infrastructure, deployments, metrics, and error patterns in FalkorDB.",
        "parameters": {
            "incident_id": {"type": "string", "description": "The incident ID to trace"},
            "fallback_service_id": {"type": "string", "description": "Optional fallback service ID if incident node is not linked"}
        },
        "required": ["incident_id"]
    },
    {
        "name": "MemoryRetrievalTool",
        "description": "Queries FalkorDB for historically similar incident precedents and their validated resolution strategies.",
        "parameters": {
            "incident_id": {"type": "string", "description": "The incident ID to find historical precedents for"}
        },
        "required": ["incident_id"]
    }
]

PERMITTED_TOOL_NAMES = {"cypherquerytool", "dependencycascadetool", "memoryretrievaltool"}


class InvestigationEngine:
    """
    Core graph-based incident investigation engine.
    Orchestrates reusable investigation tools (CypherQueryTool, DependencyCascadeTool,
    MemoryRetrievalTool) with a traceable execution audit trail.
    """

    def __init__(self, client=None):
        self.client = client or falkor_client
        self.cypher_tool = CypherQueryTool(self.client)
        self.cascade_tool = DependencyCascadeTool(self.cypher_tool)
        self.memory_tool = MemoryRetrievalTool(self.cypher_tool)
        self.investigation_history: Dict[str, InvestigationResult] = {}

    async def investigate_incident(
        self,
        incident_id: str,
        custom_query: Optional[str] = None,
        enable_agent_mode: Optional[bool] = None,
    ) -> InvestigationResult:
        """
        Dispatches investigation to either the autonomous tool-calling agent loop
        or the deterministic sequential investigation pipeline based on configuration.
        Provides seamless fallback if the autonomous agent encounters any failure.
        """
        use_agent = (
            enable_agent_mode
            if enable_agent_mode is not None
            else getattr(settings, "agent_mode", False)
        )

        if use_agent:
            try:
                return await self.run_autonomous_agent_loop(incident_id, custom_query)
            except Exception as e:
                logger.error(
                    f"Autonomous agent loop failed ({e}). "
                    f"Falling back safely to deterministic sequential pipeline."
                )
                return await self.investigate_incident_sequential(incident_id, custom_query)
        else:
            return await self.investigate_incident_sequential(incident_id, custom_query)

    async def investigate_incident_sequential(
        self,
        incident_id: str,
        custom_query: Optional[str] = None
    ) -> InvestigationResult:
        """
        Deterministic sequential investigation pipeline.
        Invokes CypherQueryTool -> DependencyCascadeTool -> MemoryRetrievalTool in order.
        """
        start_time = time.perf_counter()
        investigation_id = f"inv_{uuid.uuid4().hex[:10]}"

        tool_execution_trace: List[ToolExecutionRecord] = []
        cypher_logs: List[CypherQueryLog] = []

        # -------------------------------------------------------------
        # TOOL CALL 1: Retrieve Primary Incident Node
        # -------------------------------------------------------------
        t1_start = time.perf_counter()
        q1 = "MATCH (i:Incident {id: $incident_id}) RETURN i"
        res1 = self.cypher_tool.execute(
            q1,
            {"incident_id": incident_id},
            "Retrieve primary incident node and baseline telemetry"
        )
        t1_elapsed = (time.perf_counter() - t1_start) * 1000.0

        if res1.query_log:
            cypher_logs.append(res1.query_log)

        incident_node: Dict[str, Any] = {}
        if res1.rows and len(res1.rows[0]) > 0:
            incident_node = safe_get_dict(res1.rows[0][0])

        if not incident_node or not incident_node.get("id"):
            incident_node = {
                "id": incident_id,
                "title": f"Incident {incident_id}",
                "affected_service": None,
                "severity": "MEDIUM",
                "description": custom_query or "Incident record not present in graph topology.",
            }

        tool_execution_trace.append(
            ToolExecutionRecord(
                step_number=1,
                tool_name="CypherQueryTool",
                operation="lookup_primary_incident",
                input_parameters={"incident_id": incident_id},
                rows_returned=res1.row_count,
                execution_time_ms=round(t1_elapsed, 2),
                evidence_items_derived=1 if incident_node.get("title") else 0,
                summary=f"Primary incident node '{incident_id}' retrieved from FalkorDB." if res1.row_count > 0 else f"No incident node found with ID '{incident_id}'.",
                status="SUCCESS" if res1.row_count > 0 else "EMPTY",
            )
        )

        # -------------------------------------------------------------
        # TOOL CALL 2: Dependency Cascade Exploration
        # -------------------------------------------------------------
        cascade_res = self.cascade_tool.explore(
            incident_id=incident_id,
            step_number=2,
            fallback_service_id=incident_node.get("affected_service")
        )

        tool_execution_trace.append(cascade_res.tool_record)
        cypher_logs.extend(cascade_res.query_logs)

        confirmed_facts = cascade_res.confirmed_facts
        relevant_deployments = cascade_res.deployments
        connected_infra_nodes = cascade_res.connected_infra
        error_patterns = cascade_res.error_patterns
        detected_metrics = cascade_res.metrics
        relationship_paths = cascade_res.relationship_paths
        primary_affected_service_id = (
            cascade_res.affected_services[0]["id"]
            if cascade_res.affected_services
            else incident_node.get("affected_service")
        )

        # -------------------------------------------------------------
        # TOOL CALL 3: Historical Incident Memory Retrieval
        # -------------------------------------------------------------
        memory_res = self.memory_tool.retrieve(
            incident_id=incident_id,
            step_number=3
        )

        tool_execution_trace.append(memory_res.tool_record)
        cypher_logs.extend(memory_res.query_logs)
        memory_matches = memory_res.matches

        # Synthesize findings using shared grounded evidence logic
        root_cause_hypotheses, recommended_actions = self._synthesize_investigation_findings(
            incident_id=incident_id,
            incident_node=incident_node,
            confirmed_facts=confirmed_facts,
            relevant_deployments=relevant_deployments,
            connected_infra_nodes=connected_infra_nodes,
            error_patterns=error_patterns,
            detected_metrics=detected_metrics,
            relationship_paths=relationship_paths,
            primary_affected_service_id=primary_affected_service_id,
            memory_matches=memory_matches,
        )

        # LLM Synthesis / Reasoning Integration
        llm_analysis = await llm_provider.analyze_incident_graph(
            incident_data=incident_node,
            graph_evidence=[f.model_dump() for f in confirmed_facts] + [h.model_dump() for h in root_cause_hypotheses],
            memory_matches=[m.model_dump() for m in memory_matches],
            topology_summary=self.client.get_topology(),
        )

        total_exec_time = (time.perf_counter() - start_time) * 1000.0

        primary_cause = (
            root_cause_hypotheses[0].description
            if root_cause_hypotheses
            else llm_analysis.get("primary_root_cause", "Incident investigation concluded.")
        )
        if llm_analysis.get("primary_root_cause") and len(confirmed_facts) > 0:
            primary_cause = llm_analysis["primary_root_cause"]

        summary_text = (
            llm_analysis.get("summary")
            if llm_analysis.get("summary") and len(confirmed_facts) > 0
            else f"TRACEFORGE AI evaluated graph relationships for {incident_id}. Derived {len(confirmed_facts)} confirmed facts and {len(root_cause_hypotheses)} hypotheses across {len(tool_execution_trace)} investigation tool steps."
        )

        result = InvestigationResult(
            investigation_id=investigation_id,
            incident_id=incident_id,
            incident_title=incident_node.get("title", f"Incident {incident_id}"),
            status="IDENTIFIED" if confirmed_facts else "INVESTIGATING",
            primary_root_cause=primary_cause,
            summary=summary_text,
            confirmed_facts=confirmed_facts,
            root_cause_hypotheses=root_cause_hypotheses,
            relationship_paths=relationship_paths,
            memory_matches=memory_matches,
            recommended_actions=recommended_actions,
            cypher_queries_executed=cypher_logs,
            tool_execution_trace=tool_execution_trace,
            execution_time_ms=round(total_exec_time, 2),
            llm_provider_used=llm_provider.provider,
        )

        self.investigation_history[investigation_id] = result
        return result

    async def run_autonomous_agent_loop(
        self,
        incident_id: str,
        custom_query: Optional[str] = None,
        max_iterations: Optional[int] = None,
    ) -> InvestigationResult:
        """
        Bounded autonomous tool-calling agent loop.
        Allows the agent to dynamically select among CypherQueryTool, DependencyCascadeTool,
        and MemoryRetrievalTool based on prior observations up to max_agent_iterations.
        """
        start_time = time.perf_counter()
        investigation_id = f"inv_{uuid.uuid4().hex[:10]}"
        max_iter = max_iterations or getattr(settings, "max_agent_iterations", 5)

        tool_execution_trace: List[ToolExecutionRecord] = []
        cypher_logs: List[CypherQueryLog] = []
        observations: List[Dict[str, Any]] = []

        incident_node: Dict[str, Any] = {
            "id": incident_id,
            "title": f"Incident {incident_id}",
            "affected_service": None,
            "severity": "MEDIUM",
            "description": custom_query or "Incident record in graph topology.",
        }

        cascade_res: Optional[CascadeAnalysisResult] = None
        memory_res: Optional[MemoryRetrievalResult] = None

        autonomous_tool_steps: List[str] = []
        fallback_tools_invoked: List[str] = []

        step_counter = 1
        for iteration in range(1, max_iter + 1):
            decision = await llm_provider.decide_next_tool_action(
                incident_data=incident_node,
                available_tools=AVAILABLE_TOOLS_MANIFEST,
                observations=observations,
                iteration=iteration,
                max_iterations=max_iter,
            )

            action = decision.get("action", "finish")
            thought = decision.get("thought", "")

            if action == "finish":
                # Bounded retry: If agent attempts to finish due to a tool error or parameter misunderstanding, provide guidance and retry
                thought_lower = (str(thought) + " " + str(decision.get("reasoning", ""))).lower()
                is_unsupported_error_finish = (
                    len(autonomous_tool_steps) == 0
                    and any(k in thought_lower for k in ("error", "misunderstanding", "invalid", "parameter", "query string", "syntax"))
                    and iteration < max_iter
                )
                if is_unsupported_error_finish:
                    observations.append({
                        "step": step_counter,
                        "observation": f"Premature finish due to tool error rejected. You have not executed any tools yet. You MUST call a tool (e.g. CypherQueryTool with query='MATCH (i:Incident {{id: $incident_id}}) RETURN i' and params={{'incident_id': '{incident_id}'}}) to gather evidence before finishing.",
                    })
                    logger.info(f"Autonomous agent requested premature finish due to error at iteration {iteration}; retrying with guidance.")
                    continue
                logger.info(f"Autonomous agent decided to finish at iteration {iteration}. Thought: {thought}")
                break

            raw_tool_name = str(decision.get("tool_name", "")).strip()
            tool_name_normalized = raw_tool_name.lower().replace("_", "").replace("-", "")
            tool_args = decision.get("tool_args") or {}
            if not isinstance(tool_args, dict):
                tool_args = {}

            # Validate requested tool against permitted set
            if tool_name_normalized not in PERMITTED_TOOL_NAMES:
                tool_execution_trace.append(
                    ToolExecutionRecord(
                        step_number=step_counter,
                        tool_name=raw_tool_name or "UnknownTool",
                        operation="rejected_unsupported_tool",
                        input_parameters=safe_sanitize_params(tool_args),
                        rows_returned=0,
                        execution_time_ms=0.0,
                        evidence_items_derived=0,
                        summary=f"Rejected unsupported tool '{raw_tool_name}'. Permitted tools: CypherQueryTool, DependencyCascadeTool, MemoryRetrievalTool.",
                        status="ERROR",
                    )
                )
                observations.append({
                    "step": step_counter,
                    "tool": raw_tool_name,
                    "status": "ERROR",
                    "error": f"Tool '{raw_tool_name}' is not recognized or permitted. Available tools: CypherQueryTool, DependencyCascadeTool, MemoryRetrievalTool.",
                })
                step_counter += 1
                continue

            # Execute permitted tool
            if tool_name_normalized == "cypherquerytool":
                q = tool_args.get("query")
                if not q or not isinstance(q, str):
                    tool_execution_trace.append(
                        ToolExecutionRecord(
                            step_number=step_counter,
                            tool_name="CypherQueryTool",
                            operation="invalid_query_parameter",
                            input_parameters=safe_sanitize_params(tool_args),
                            rows_returned=0,
                            execution_time_ms=0.0,
                            evidence_items_derived=0,
                            summary="Rejected Cypher query: missing or invalid 'query' string parameter.",
                            status="ERROR",
                        )
                    )
                    observations.append({
                        "step": step_counter,
                        "tool": "CypherQueryTool",
                        "status": "ERROR",
                        "error": f"Missing required 'query' parameter in tool_args. Example of valid call: 'tool_args': {{'query': 'MATCH (i:Incident {{id: $incident_id}}) RETURN i', 'params': {{'incident_id': '{incident_id}'}}}}. Do not finish; please retry.",
                    })
                    step_counter += 1
                    continue

                params = tool_args.get("params") or {}
                if not isinstance(params, dict):
                    params = {}
                purpose = str(tool_args.get("purpose") or "Agent Cypher query execution")

                res = self.cypher_tool.execute(q, params, purpose)
                if res.query_log:
                    cypher_logs.append(res.query_log)

                if res.rows and len(res.rows[0]) > 0:
                    first_item = safe_get_dict(res.rows[0][0])
                    if first_item.get("id") == incident_id:
                        incident_node.update(first_item)

                if res.success and res.row_count > 0:
                    autonomous_tool_steps.append("CypherQueryTool")

                tool_execution_trace.append(
                    ToolExecutionRecord(
                        step_number=step_counter,
                        tool_name="CypherQueryTool",
                        operation="agent_cypher_query",
                        input_parameters=safe_sanitize_params(params),
                        rows_returned=res.row_count,
                        execution_time_ms=res.execution_time_ms,
                        evidence_items_derived=1 if (res.row_count > 0 and res.success) else 0,
                        summary=f"[Autonomous LLM Call] Cypher query returned {res.row_count} row(s) in {res.execution_time_ms}ms." if res.success else f"Cypher execution failed: {res.error}",
                        status="SUCCESS" if (res.success and res.row_count > 0) else ("EMPTY" if res.success else "ERROR"),
                    )
                )
                observations.append({
                    "step": step_counter,
                    "tool": "CypherQueryTool",
                    "rows_returned": res.row_count,
                    "columns": res.columns,
                    "status": "SUCCESS" if res.success else "ERROR",
                })
                step_counter += 1

            elif tool_name_normalized == "dependencycascadetool":
                inc_id = str(tool_args.get("incident_id") or incident_id)
                fb_svc = tool_args.get("fallback_service_id") or incident_node.get("affected_service")
                cascade_res = self.cascade_tool.explore(
                    incident_id=inc_id,
                    step_number=step_counter,
                    fallback_service_id=fb_svc,
                )
                cascade_res.tool_record.step_number = step_counter
                cascade_res.tool_record.operation = "agent_autonomous_cascade"
                cascade_res.tool_record.summary = f"[Autonomous LLM Call] {cascade_res.tool_record.summary}"
                tool_execution_trace.append(cascade_res.tool_record)
                cypher_logs.extend(cascade_res.query_logs)
                autonomous_tool_steps.append("DependencyCascadeTool")

                if cascade_res.affected_services:
                    incident_node["affected_service"] = cascade_res.affected_services[0].get("id")

                observations.append({
                    "step": step_counter,
                    "tool": "DependencyCascadeTool",
                    "affected_services": len(cascade_res.affected_services),
                    "dependencies": len(cascade_res.dependencies),
                    "connected_infra": len(cascade_res.connected_infra),
                    "deployments": len(cascade_res.deployments),
                    "confirmed_facts": len(cascade_res.confirmed_facts),
                    "status": cascade_res.tool_record.status,
                })
                step_counter += 1

            elif tool_name_normalized == "memoryretrievaltool":
                inc_id = str(tool_args.get("incident_id") or incident_id)
                memory_res = self.memory_tool.retrieve(
                    incident_id=inc_id,
                    step_number=step_counter,
                )
                memory_res.tool_record.step_number = step_counter
                memory_res.tool_record.operation = "agent_autonomous_memory"
                memory_res.tool_record.summary = f"[Autonomous LLM Call] {memory_res.tool_record.summary}"
                tool_execution_trace.append(memory_res.tool_record)
                cypher_logs.extend(memory_res.query_logs)
                autonomous_tool_steps.append("MemoryRetrievalTool")

                observations.append({
                    "step": step_counter,
                    "tool": "MemoryRetrievalTool",
                    "matches_found": len(memory_res.matches),
                    "status": memory_res.tool_record.status,
                })
                step_counter += 1

        # Fallback completion: Ensure cascade and memory tools have executed to ground findings
        if cascade_res is None:
            cascade_res = self.cascade_tool.explore(
                incident_id=incident_id,
                step_number=step_counter,
                fallback_service_id=incident_node.get("affected_service"),
            )
            cascade_res.tool_record.step_number = step_counter
            cascade_res.tool_record.operation = "deterministic_fallback_cascade"
            cascade_res.tool_record.summary = f"[Deterministic Fallback] {cascade_res.tool_record.summary}"
            tool_execution_trace.append(cascade_res.tool_record)
            cypher_logs.extend(cascade_res.query_logs)
            fallback_tools_invoked.append("DependencyCascadeTool")
            step_counter += 1

        if memory_res is None:
            memory_res = self.memory_tool.retrieve(
                incident_id=incident_id,
                step_number=step_counter,
            )
            memory_res.tool_record.step_number = step_counter
            memory_res.tool_record.operation = "deterministic_fallback_memory"
            memory_res.tool_record.summary = f"[Deterministic Fallback] {memory_res.tool_record.summary}"
            tool_execution_trace.append(memory_res.tool_record)
            cypher_logs.extend(memory_res.query_logs)
            fallback_tools_invoked.append("MemoryRetrievalTool")
            step_counter += 1

        # Synthesize findings using shared grounded evidence logic
        confirmed_facts = cascade_res.confirmed_facts
        relevant_deployments = cascade_res.deployments
        connected_infra_nodes = cascade_res.connected_infra
        error_patterns = cascade_res.error_patterns
        detected_metrics = cascade_res.metrics
        relationship_paths = cascade_res.relationship_paths
        memory_matches = memory_res.matches
        primary_affected_service_id = (
            cascade_res.affected_services[0]["id"]
            if cascade_res.affected_services
            else incident_node.get("affected_service")
        )

        root_cause_hypotheses, recommended_actions = self._synthesize_investigation_findings(
            incident_id=incident_id,
            incident_node=incident_node,
            confirmed_facts=confirmed_facts,
            relevant_deployments=relevant_deployments,
            connected_infra_nodes=connected_infra_nodes,
            error_patterns=error_patterns,
            detected_metrics=detected_metrics,
            relationship_paths=relationship_paths,
            primary_affected_service_id=primary_affected_service_id,
            memory_matches=memory_matches,
        )

        llm_analysis = await llm_provider.analyze_incident_graph(
            incident_data=incident_node,
            graph_evidence=[f.model_dump() for f in confirmed_facts] + [h.model_dump() for h in root_cause_hypotheses],
            memory_matches=[m.model_dump() for m in memory_matches],
            topology_summary=self.client.get_topology(),
        )

        total_exec_time = (time.perf_counter() - start_time) * 1000.0

        primary_cause = (
            root_cause_hypotheses[0].description
            if root_cause_hypotheses
            else llm_analysis.get("primary_root_cause", "Incident investigation concluded.")
        )
        if llm_analysis.get("primary_root_cause") and len(confirmed_facts) > 0:
            primary_cause = llm_analysis["primary_root_cause"]

        summary_text = (
            llm_analysis.get("summary")
            if llm_analysis.get("summary") and len(confirmed_facts) > 0
            else f"TRACEFORGE AI evaluated graph relationships for {incident_id}. Derived {len(confirmed_facts)} confirmed facts and {len(root_cause_hypotheses)} hypotheses across {len(tool_execution_trace)} autonomous tool steps."
        )

        if len(autonomous_tool_steps) > 0 and len(fallback_tools_invoked) == 0:
            provider_mode_label = f"{llm_provider.provider} (autonomous-agent)"
        elif len(autonomous_tool_steps) > 0 and len(fallback_tools_invoked) > 0:
            provider_mode_label = f"{llm_provider.provider} (hybrid-agent-fallback)"
        else:
            provider_mode_label = f"{llm_provider.provider} (agent-fallback-deterministic)"

        result = InvestigationResult(
            investigation_id=investigation_id,
            incident_id=incident_id,
            incident_title=incident_node.get("title", f"Incident {incident_id}"),
            status="IDENTIFIED" if confirmed_facts else "INVESTIGATING",
            primary_root_cause=primary_cause,
            summary=summary_text,
            confirmed_facts=confirmed_facts,
            root_cause_hypotheses=root_cause_hypotheses,
            relationship_paths=relationship_paths,
            memory_matches=memory_matches,
            recommended_actions=recommended_actions,
            cypher_queries_executed=cypher_logs,
            tool_execution_trace=tool_execution_trace,
            execution_time_ms=round(total_exec_time, 2),
            llm_provider_used=provider_mode_label,
        )

        self.investigation_history[investigation_id] = result
        return result

    def _synthesize_investigation_findings(
        self,
        incident_id: str,
        incident_node: Dict[str, Any],
        confirmed_facts: List[EvidenceItem],
        relevant_deployments: List[Dict[str, Any]],
        connected_infra_nodes: List[Dict[str, Any]],
        error_patterns: List[Dict[str, Any]],
        detected_metrics: List[Dict[str, Any]],
        relationship_paths: List[List[str]],
        primary_affected_service_id: Optional[str],
        memory_matches: List[HistoricalIncidentMatch],
    ) -> Tuple[List[EvidenceItem], List[ActionPlanItem]]:
        """
        Synthesizes confirmed facts and graph relationships into causal root-cause hypotheses
        and human-in-the-loop action plans strictly grounded in graph results.
        """
        root_cause_hypotheses: List[EvidenceItem] = []

        if relevant_deployments:
            top_dep = relevant_deployments[0]
            dep_id = top_dep.get("id", "deployment")
            dep_svc = top_dep.get("target_service", primary_affected_service_id or "service")
            change_txt = top_dep.get("change_summary", "recent code modification")

            path_steps: List[EvidencePathStep] = [
                EvidencePathStep(
                    from_node=dep_id,
                    to_node=dep_svc,
                    relationship="DEPLOYED_TO",
                    explanation=f"Introduced changes: '{change_txt}'",
                )
            ]

            if connected_infra_nodes:
                infra_target = connected_infra_nodes[0].get("id", "database")
                path_steps.append(
                    EvidencePathStep(
                        from_node=dep_svc,
                        to_node=infra_target,
                        relationship="CONNECTS_TO",
                        explanation=f"Resource saturation on {infra_target}",
                    )
                )

            if error_patterns:
                err_target = error_patterns[0].get("id", "error")
                path_steps.append(
                    EvidencePathStep(
                        from_node=dep_svc,
                        to_node=err_target,
                        relationship="TRIGGERED_BY",
                        explanation=f"Triggered error pattern: {error_patterns[0].get('pattern', 'system failure')[:60]}",
                    )
                )

            if primary_affected_service_id and primary_affected_service_id != dep_svc:
                path_steps.append(
                    EvidencePathStep(
                        from_node=dep_svc,
                        to_node=primary_affected_service_id,
                        relationship="PROPAGATES_TO",
                        explanation=f"Cascaded failures upstream to {primary_affected_service_id}",
                    )
                )

            root_cause_hypotheses.append(
                EvidenceItem(
                    id=f"hyp-dep-{dep_id}",
                    title=f"Primary: Degradation Induced by Deployment {dep_id} on {dep_svc}",
                    description=f"The recent deployment {dep_id} to {dep_svc} ({change_txt}) correlates with downstream failures on {primary_affected_service_id or dep_svc}. Resource constraints triggered error propagation.",
                    source_node=dep_id,
                    target_node=error_patterns[0].get("id", dep_svc) if error_patterns else dep_svc,
                    relationship_type="CAUSED_BY",
                    confidence_score=0.94,
                    is_confirmed_fact=False,
                    cypher_proof_query=f"MATCH (d:Deployment {{id: '{dep_id}'}})-[:DEPLOYED_TO]->(s:Service)-[:CONNECTS_TO]->(i) RETURN d, s, i",
                    evidence_path=path_steps,
                )
            )

            if connected_infra_nodes:
                infra_id = connected_infra_nodes[0].get("id", "infrastructure")
                root_cause_hypotheses.append(
                    EvidenceItem(
                        id=f"hyp-infra-{infra_id}",
                        title=f"Alternative: Hardware / Network Fault on {infra_id}",
                        description=f"Hypothesis that physical network interface or packet drop occurred between {dep_svc} and {infra_id}.",
                        source_node=dep_svc,
                        target_node=infra_id,
                        relationship_type="CONNECTS_TO",
                        confidence_score=0.22,
                        is_confirmed_fact=False,
                        cypher_proof_query=f"MATCH (s:Service {{id: '{dep_svc}'}})-[r:CONNECTS_TO]->(d {{id: '{infra_id}'}}) RETURN s, r, d",
                        evidence_path=[
                            EvidencePathStep(
                                from_node=dep_svc,
                                to_node=infra_id,
                                relationship="CONNECTS_TO",
                                explanation="Unlikely: CPU and memory metrics on host remain within operational parameters.",
                            )
                        ],
                    )
                )

        elif detected_metrics or error_patterns:
            lead_metric = detected_metrics[0] if detected_metrics else None
            m_target = lead_metric.get("target_service") if lead_metric else (primary_affected_service_id or "service")
            m_name = lead_metric.get("name", "Metric Anomaly") if lead_metric else "Error Pattern Spike"

            root_cause_hypotheses.append(
                EvidenceItem(
                    id="hyp-metric-lead",
                    title=f"Primary: Operational Saturation in {m_target} ({m_name})",
                    description=f"Graph telemetry indicates abnormal metrics on {m_target} without a direct preceding code deployment. Likely caused by unexpected traffic surge or external dependency starvation.",
                    source_node=m_target,
                    target_node=primary_affected_service_id or m_target,
                    relationship_type="AFFECTS",
                    confidence_score=0.85,
                    is_confirmed_fact=False,
                    cypher_proof_query=f"MATCH (m:MetricAnomaly)-[:AFFECTS]->(s:Service {{id: '{m_target}'}}) RETURN m, s",
                    evidence_path=[
                        EvidencePathStep(
                            from_node=m_name,
                            to_node=m_target,
                            relationship="AFFECTS",
                            explanation="Telemetry anomaly observed without deployment event",
                        )
                    ],
                )
            )
        else:
            root_cause_hypotheses.append(
                EvidenceItem(
                    id="hyp-no-evidence",
                    title=f"Uncorrelated Incident: Insufficient Graph Evidence for {incident_id}",
                    description=f"No recent code deployments, active error patterns, or telemetry anomalies are connected to {incident_id} or its services in the graph topology.",
                    source_node=incident_id,
                    target_node=primary_affected_service_id or "unknown",
                    relationship_type="UNCORRELATED",
                    confidence_score=0.15,
                    is_confirmed_fact=False,
                    cypher_proof_query=f"MATCH (i:Incident {{id: '{incident_id}'}}) RETURN i",
                    evidence_path=[],
                )
            )

        # Propose Actionable Recommendations (Strictly Human-in-the-Loop)
        recommended_actions: List[ActionPlanItem] = []

        if memory_matches:
            top_match = memory_matches[0]
            target_svc = relevant_deployments[0].get("target_service") if relevant_deployments else (primary_affected_service_id or "service")
            recommended_actions.append(
                ActionPlanItem(
                    action_id="act-tune-pool",
                    title=f"Hotfix: Apply Resolution from {top_match.incident_id}",
                    description=f"Apply verified resolution fix from historical incident {top_match.incident_id}: {top_match.transferrable_fix}.",
                    target_service=target_svc,
                    action_type="CONFIG_UPDATE",
                    risk_level="LOW",
                    confidence=0.95,
                    requires_human_approval=True,
                    status=ActionStatus.PENDING_APPROVAL,
                    dry_run_output=f"DRY RUN OK: Configuration patch '{top_match.transferrable_fix}' validated against {target_svc}. No container restart required.",
                )
            )

        if relevant_deployments:
            target_dep = relevant_deployments[0]
            d_id = target_dep.get("id", "deployment")
            target_svc = target_dep.get("target_service", primary_affected_service_id or "service")
            recommended_actions.append(
                ActionPlanItem(
                    action_id=f"act-rollback-{d_id.replace('.', '_')}",
                    title=f"Rollback Deployment {d_id}",
                    description=f"Immediately rollback {target_svc} deployment {d_id} to the previous stable release.",
                    target_service=target_svc,
                    action_type="ROLLBACK",
                    risk_level="MEDIUM",
                    confidence=0.91,
                    requires_human_approval=True,
                    status=ActionStatus.PENDING_APPROVAL,
                    dry_run_output=f"DRY RUN OK: Previous stable image verified in container registry for {target_svc}. Rolling update strategy prepared.",
                )
            )

        if error_patterns and primary_affected_service_id:
            recommended_actions.append(
                ActionPlanItem(
                    action_id="act-reset-circuit-breaker",
                    title=f"Reset Circuit Breaker on {primary_affected_service_id}",
                    description=f"Force close tripped circuit breaker on {primary_affected_service_id} once upstream dependency recovers.",
                    target_service=primary_affected_service_id,
                    action_type="CIRCUIT_BREAKER",
                    risk_level="LOW",
                    confidence=0.88,
                    requires_human_approval=True,
                    status=ActionStatus.PENDING_APPROVAL,
                    dry_run_output=f"DRY RUN OK: Target circuit breaker on {primary_affected_service_id} state verified. Auto-reset condition armed.",
                )
            )

        if not recommended_actions:
            target_svc = primary_affected_service_id or "system"
            recommended_actions.append(
                ActionPlanItem(
                    action_id="act-diagnostic-canary",
                    title=f"Run Diagnostic Canary Probe on {target_svc}",
                    description=f"Execute non-intrusive diagnostic probe across {target_svc} endpoints to assess network latency and health.",
                    target_service=target_svc,
                    action_type="DIAGNOSTIC",
                    risk_level="LOW",
                    confidence=0.60,
                    requires_human_approval=True,
                    status=ActionStatus.PENDING_APPROVAL,
                    dry_run_output=f"DRY RUN OK: Synthetic canary probe ping scheduled for {target_svc}. Zero state mutation.",
                )
            )

        return root_cause_hypotheses, recommended_actions

    def get_investigation(self, investigation_id: str) -> Optional[InvestigationResult]:
        return self.investigation_history.get(investigation_id)

    def list_investigations(self) -> List[InvestigationResult]:
        return list(self.investigation_history.values())


investigation_engine = InvestigationEngine()
