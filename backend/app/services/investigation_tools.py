import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from backend.app.database.falkordb_client import falkor_client
from backend.app.models.schemas import (
    CypherQueryLog,
    EvidenceItem,
    EvidencePathStep,
    HistoricalIncidentMatch,
    ToolExecutionRecord,
)

logger = logging.getLogger("traceforge.tools")


def safe_sanitize_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitizes parameter dictionary to avoid logging sensitive secrets."""
    if not params:
        return {}
    sanitized = {}
    for k, v in params.items():
        k_lower = str(k).lower()
        if any(secret_word in k_lower for secret_word in ("secret", "token", "password", "key", "auth")):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = safe_sanitize_params(v)
        elif isinstance(v, list):
            sanitized[k] = [safe_sanitize_params(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = v
    return sanitized


def safe_get_dict(item: Any) -> Dict[str, Any]:
    """Safely extracts a dictionary of properties from a query row element."""
    if isinstance(item, dict):
        return item
    if hasattr(item, "properties") and isinstance(item.properties, dict):
        d = dict(item.properties)
        if hasattr(item, "id") and "id" not in d:
            d["id"] = str(item.id)
        return d
    if hasattr(item, "__dict__"):
        return dict(item.__dict__)
    if isinstance(item, str) and item:
        return {"id": item, "name": item}
    return {}


class CypherToolResult(BaseModel):
    success: bool
    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    engine: str = "FalkorDB"
    error: Optional[str] = None
    query_log: Optional[CypherQueryLog] = None


class CypherQueryTool:
    """
    Tool 1: CypherQueryTool
    Executes parameterized OpenCypher queries against the FalkorDB graph layer,
    recording performance metrics and query audit logs safely.
    """

    def __init__(self, client=None):
        self.client = client or falkor_client

    def execute(self, query: str, params: Optional[Dict[str, Any]] = None, purpose: str = "Cypher query execution") -> CypherToolResult:
        params = params or {}
        safe_params = safe_sanitize_params(params)
        start_time = time.perf_counter()

        try:
            res = self.client.execute_cypher(query, params)
            elapsed = (time.perf_counter() - start_time) * 1000.0

            if res.get("error"):
                err_msg = res["error"]
                logger.error(f"CypherQueryTool execution failure: {err_msg}")
                q_log = CypherQueryLog(
                    cypher=query,
                    params=safe_params,
                    execution_time_ms=res.get("execution_time_ms", round(elapsed, 2)),
                    rows_returned=0,
                    purpose=f"{purpose} (FAILED: {err_msg})",
                )
                return CypherToolResult(
                    success=False,
                    columns=[],
                    rows=[],
                    row_count=0,
                    execution_time_ms=res.get("execution_time_ms", round(elapsed, 2)),
                    engine=res.get("engine", "FalkorDB"),
                    error=err_msg,
                    query_log=q_log,
                )

            q_log = CypherQueryLog(
                cypher=query,
                params=safe_params,
                execution_time_ms=res.get("execution_time_ms", round(elapsed, 2)),
                rows_returned=res.get("row_count", 0),
                purpose=purpose,
            )

            return CypherToolResult(
                success=True,
                columns=res.get("columns", []),
                rows=res.get("rows", []),
                row_count=res.get("row_count", 0),
                execution_time_ms=res.get("execution_time_ms", round(elapsed, 2)),
                engine=res.get("engine", "FalkorDB"),
                error=None,
                query_log=q_log,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            err_msg = str(e)
            logger.error(f"CypherQueryTool execution failure: {err_msg}")

            q_log = CypherQueryLog(
                cypher=query,
                params=safe_params,
                execution_time_ms=round(elapsed, 2),
                rows_returned=0,
                purpose=f"{purpose} (FAILED: {err_msg})",
            )

            return CypherToolResult(
                success=False,
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=round(elapsed, 2),
                engine="FalkorDB",
                error=err_msg,
                query_log=q_log,
            )


class CascadeAnalysisResult(BaseModel):
    affected_services: List[Dict[str, Any]] = Field(default_factory=list)
    dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    connected_infra: List[Dict[str, Any]] = Field(default_factory=list)
    deployments: List[Dict[str, Any]] = Field(default_factory=list)
    error_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    confirmed_facts: List[EvidenceItem] = Field(default_factory=list)
    relationship_paths: List[List[str]] = Field(default_factory=list)
    query_logs: List[CypherQueryLog] = Field(default_factory=list)
    tool_record: ToolExecutionRecord


class DependencyCascadeTool:
    """
    Tool 2: DependencyCascadeTool
    Explores incident-affected services, service-to-service dependencies,
    connected datastores/queues, and correlated deployments/errors in FalkorDB.
    """

    def __init__(self, cypher_tool: Optional[CypherQueryTool] = None):
        self.cypher_tool = cypher_tool or CypherQueryTool()

    def explore(
        self,
        incident_id: str,
        step_number: int = 1,
        fallback_service_id: Optional[str] = None
    ) -> CascadeAnalysisResult:
        start_time = time.perf_counter()
        query_logs: List[CypherQueryLog] = []
        confirmed_facts: List[EvidenceItem] = []
        relationship_paths: List[List[str]] = []

        affected_services: List[Dict[str, Any]] = []
        dependencies: List[Dict[str, Any]] = []
        connected_infra: List[Dict[str, Any]] = []
        deployments: List[Dict[str, Any]] = []
        error_patterns: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []

        total_rows = 0

        # 1. Discover affected services
        q_aff = "MATCH (i:Incident)-[r:AFFECTS]->(s:Service) WHERE i.id = $incident_id RETURN i, r, s"
        res_aff = self.cypher_tool.execute(q_aff, {"incident_id": incident_id}, "Retrieve services directly impacted by incident")
        if res_aff.query_log:
            query_logs.append(res_aff.query_log)
        total_rows += res_aff.row_count

        for row in res_aff.rows:
            if len(row) >= 3:
                svc = safe_get_dict(row[2])
                if svc.get("id"):
                    affected_services.append(svc)

        if not affected_services and fallback_service_id:
            # Fallback service query
            q_fallback = "MATCH (s:Service {id: $service_id}) RETURN s"
            res_fb = self.cypher_tool.execute(q_fallback, {"service_id": fallback_service_id}, f"Lookup fallback service '{fallback_service_id}'")
            if res_fb.query_log:
                query_logs.append(res_fb.query_log)
            total_rows += res_fb.row_count

            if res_fb.rows and len(res_fb.rows[0]) > 0:
                affected_services.append(safe_get_dict(res_fb.rows[0][0]))
            else:
                affected_services.append({"id": fallback_service_id, "name": fallback_service_id})

        primary_affected_service_id = affected_services[0]["id"] if affected_services else None
        relevant_service_ids = set()
        if primary_affected_service_id:
            relevant_service_ids.add(primary_affected_service_id)

        # 2. Traverse service dependencies
        for aff in affected_services:
            aff_id = aff.get("id")
            if not aff_id:
                continue

            q_dep = "MATCH (s:Service)-[r:DEPENDS_ON]->(dep:Service) WHERE s.id = $service_id RETURN s, r, dep"
            res_dep = self.cypher_tool.execute(q_dep, {"service_id": aff_id}, f"Traverse dependencies for service '{aff_id}'")
            if res_dep.query_log:
                query_logs.append(res_dep.query_log)
            total_rows += res_dep.row_count

            for row in res_dep.rows:
                if len(row) < 3:
                    continue
                s_dict = safe_get_dict(row[0])
                r_dict = safe_get_dict(row[1])
                dep_dict = safe_get_dict(row[2])

                dep_id = dep_dict.get("id")
                s_id = s_dict.get("id", aff_id)
                if not dep_id:
                    continue

                dependencies.append(dep_dict)
                relevant_service_ids.add(dep_id)

                proto = r_dict.get("type", "REST")
                timeout_val = r_dict.get("timeout_ms")
                timeout_str = f" with {timeout_val}ms SLA timeout" if timeout_val else ""

                confirmed_facts.append(
                    EvidenceItem(
                        id=f"fact-dep-{s_id}-{dep_id}",
                        title=f"Direct Dependency: {s_id} -> {dep_id}",
                        description=f"Graph topology verifies that {s_id} requires synchronous {proto} calls to {dep_id} for operation{timeout_str}.",
                        source_node=s_id,
                        target_node=dep_id,
                        relationship_type="DEPENDS_ON",
                        confidence_score=1.0,
                        is_confirmed_fact=True,
                        cypher_proof_query=f"MATCH (s:Service {{id: '{s_id}'}})-[r:DEPENDS_ON]->(d:Service {{id: '{dep_id}'}}) RETURN s, r, d",
                        evidence_path=[
                            EvidencePathStep(
                                from_node=s_id,
                                to_node=dep_id,
                                relationship="DEPENDS_ON",
                                explanation=f"{proto} dependency ({'critical' if r_dict.get('critical') else 'standard'}).",
                            )
                        ],
                    )
                )

        # 3. Infrastructure connectivity
        q_infra = "MATCH (s:Service)-[r:CONNECTS_TO]->(infra:Database) RETURN s, r, infra"
        res_infra = self.cypher_tool.execute(q_infra, {}, "Retrieve datastores connected to relevant services")
        if res_infra.query_log:
            query_logs.append(res_infra.query_log)
        total_rows += res_infra.row_count

        for row in res_infra.rows:
            if len(row) < 3:
                continue
            svc_dict = safe_get_dict(row[0])
            infra_dict = safe_get_dict(row[2])
            s_id = svc_dict.get("id")
            infra_id = infra_dict.get("id")

            if s_id and infra_id and s_id in relevant_service_ids:
                connected_infra.append(infra_dict)
                status_val = infra_dict.get("status", "healthy")
                if status_val in ("exhausted", "critical", "degraded"):
                    confirmed_facts.append(
                        EvidenceItem(
                            id=f"fact-infra-{infra_id}",
                            title=f"Infrastructure Saturated: {infra_id}",
                            description=f"Service {s_id} connects to {infra_id} ({infra_dict.get('type', 'datastore')}) which is currently flagged as {status_val}.",
                            source_node=s_id,
                            target_node=infra_id,
                            relationship_type="CONNECTS_TO",
                            confidence_score=0.98,
                            is_confirmed_fact=True,
                            cypher_proof_query=f"MATCH (s:Service {{id: '{s_id}'}})-[r:CONNECTS_TO]->(i:Database {{id: '{infra_id}'}}) RETURN s, r, i",
                            evidence_path=[
                                EvidencePathStep(
                                    from_node=s_id,
                                    to_node=infra_id,
                                    relationship="CONNECTS_TO",
                                    explanation=f"{infra_dict.get('type', 'Datastore')} status: {status_val}",
                                )
                            ],
                        )
                    )

        # 4. Recent deployments
        q_dep = "MATCH (d:Deployment)-[r:DEPLOYED_TO]->(s:Service) RETURN d, r, s"
        res_d = self.cypher_tool.execute(q_dep, {}, "Inspect recent deployments across dependency tree")
        if res_d.query_log:
            query_logs.append(res_d.query_log)
        total_rows += res_d.row_count

        for row in res_d.rows:
            if len(row) < 3:
                continue
            d_dict = safe_get_dict(row[0])
            s_dict = safe_get_dict(row[2])
            s_id = s_dict.get("id")
            d_id = d_dict.get("id")

            if s_id and d_id and s_id in relevant_service_ids:
                deployments.append({**d_dict, "target_service": s_id})
                deployed_at = d_dict.get("deployed_at", "recently")
                change_summary = d_dict.get("change_summary", "Configuration/code release")

                confirmed_facts.append(
                    EvidenceItem(
                        id=f"fact-deploy-{d_id}",
                        title=f"Recent Production Deployment: {d_id}",
                        description=f"FalkorDB records show deployment {d_id} ({d_dict.get('version', '')}) committed {deployed_at} to {s_id}: '{change_summary}'.",
                        source_node=d_id,
                        target_node=s_id,
                        relationship_type="DEPLOYED_TO",
                        confidence_score=1.0,
                        is_confirmed_fact=True,
                        cypher_proof_query=f"MATCH (d:Deployment {{id: '{d_id}'}})-[:DEPLOYED_TO]->(s:Service {{id: '{s_id}'}}) RETURN d, s",
                        evidence_path=[
                            EvidencePathStep(
                                from_node=d_id,
                                to_node=s_id,
                                relationship="DEPLOYED_TO",
                                explanation=f"Committed {deployed_at}: {change_summary}",
                            )
                        ],
                    )
                )

        # 5. Active errors
        q_err = "MATCH (i:Incident)-[r:TRIGGERED_BY]->(e:ErrorPattern) WHERE i.id = $incident_id RETURN i, r, e"
        res_err = self.cypher_tool.execute(q_err, {"incident_id": incident_id}, "Correlate active error patterns")
        if res_err.query_log:
            query_logs.append(res_err.query_log)
        total_rows += res_err.row_count

        for row in res_err.rows:
            if len(row) >= 3:
                e_obj = safe_get_dict(row[2])
                if e_obj.get("id"):
                    error_patterns.append(e_obj)

        # 6. Telemetry metrics
        q_m = "MATCH (m:MetricAnomaly)-[r:AFFECTS]->(s:Service) RETURN m, r, s"
        res_m = self.cypher_tool.execute(q_m, {}, "Retrieve metric anomalies on dependency tree")
        if res_m.query_log:
            query_logs.append(res_m.query_log)
        total_rows += res_m.row_count

        for row in res_m.rows:
            if len(row) < 3:
                continue
            m_obj = safe_get_dict(row[0])
            s_obj = safe_get_dict(row[2])
            s_id = s_obj.get("id")
            m_id = m_obj.get("id")

            if s_id and m_id and s_id in relevant_service_ids:
                metrics.append({**m_obj, "target_service": s_id})
                m_score = float(m_obj.get("anomaly_score", 0.95))

                confirmed_facts.append(
                    EvidenceItem(
                        id=f"fact-metric-{m_id}",
                        title=f"Telemetry Anomaly: {m_obj.get('name', m_id)}",
                        description=f"Telemetry node {m_id} confirms metric {m_obj.get('metric')}: {m_obj.get('value')} exceeding baseline threshold {m_obj.get('threshold')} on {s_id}.",
                        source_node=m_id,
                        target_node=s_id,
                        relationship_type="AFFECTS",
                        confidence_score=round(m_score, 2),
                        is_confirmed_fact=True,
                        cypher_proof_query=f"MATCH (m:MetricAnomaly {{id: '{m_id}'}})-[:AFFECTS]->(s:Service {{id: '{s_id}'}}) RETURN m, s",
                        evidence_path=[
                            EvidencePathStep(
                                from_node=m_id,
                                to_node=s_id,
                                relationship="AFFECTS",
                                explanation=f"Anomaly score {m_score} on {s_id}",
                            )
                        ],
                    )
                )

        # Build causal relationship paths
        if deployments and connected_infra:
            relationship_paths.append([deployments[0].get("id"), deployments[0].get("target_service"), connected_infra[0].get("id")])
        if deployments and primary_affected_service_id and deployments[0].get("target_service") != primary_affected_service_id:
            relationship_paths.append([deployments[0].get("target_service"), primary_affected_service_id])
        for f in confirmed_facts:
            if f.relationship_type == "DEPENDS_ON" and f.source_node and f.target_node:
                p = [f.source_node, f.target_node]
                if p not in relationship_paths:
                    relationship_paths.append(p)
        if not relationship_paths and primary_affected_service_id:
            relationship_paths.append([primary_affected_service_id])

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        tool_record = ToolExecutionRecord(
            step_number=step_number,
            tool_name="DependencyCascadeTool",
            operation="multi_hop_graph_traversal",
            input_parameters={"incident_id": incident_id, "fallback_service": fallback_service_id},
            rows_returned=total_rows,
            execution_time_ms=round(elapsed_ms, 2),
            evidence_items_derived=len(confirmed_facts),
            summary=(
                f"Discovered {len(affected_services)} affected service(s), {len(dependencies)} dependency link(s), "
                f"{len(deployments)} deployment(s), and {len(metrics)} telemetry anomaly(s)."
            ),
            status="SUCCESS" if total_rows > 0 else "EMPTY",
        )

        return CascadeAnalysisResult(
            affected_services=affected_services,
            dependencies=dependencies,
            connected_infra=connected_infra,
            deployments=deployments,
            error_patterns=error_patterns,
            metrics=metrics,
            confirmed_facts=confirmed_facts,
            relationship_paths=relationship_paths,
            query_logs=query_logs,
            tool_record=tool_record,
        )


class MemoryRetrievalResult(BaseModel):
    matches: List[HistoricalIncidentMatch] = Field(default_factory=list)
    query_logs: List[CypherQueryLog] = Field(default_factory=list)
    tool_record: ToolExecutionRecord


class MemoryRetrievalTool:
    """
    Tool 3: MemoryRetrievalTool
    Queries FalkorDB for historically similar incident precedents and their validated resolutions.
    """

    def __init__(self, cypher_tool: Optional[CypherQueryTool] = None):
        self.cypher_tool = cypher_tool or CypherQueryTool()

    def retrieve(self, incident_id: str, step_number: int = 2) -> MemoryRetrievalResult:
        start_time = time.perf_counter()
        query_logs: List[CypherQueryLog] = []
        matches: List[HistoricalIncidentMatch] = []
        total_rows = 0

        q_mem = "MATCH (i:Incident)-[r:SIMILAR_TO]->(h:Incident) WHERE i.id = $incident_id RETURN i, r, h"
        res_mem = self.cypher_tool.execute(q_mem, {"incident_id": incident_id}, "Retrieve similar historical incidents from graph memory")
        if res_mem.query_log:
            query_logs.append(res_mem.query_log)
        total_rows += res_mem.row_count

        for row in res_mem.rows:
            if len(row) < 3:
                continue
            r_obj = safe_get_dict(row[1])
            h_obj = safe_get_dict(row[2])
            h_id = h_obj.get("id")
            if not h_id:
                continue

            sim_score = float(r_obj.get("similarity", 0.75))
            pattern_note = r_obj.get("pattern", "shared failure symptoms and topology")

            # Query resolution node
            q_res = "MATCH (h:Incident)-[r:RESOLVED_BY]->(res:Resolution) WHERE h.id = $hist_id RETURN h, r, res"
            res_res = self.cypher_tool.execute(q_res, {"hist_id": h_id}, f"Lookup resolution for historical incident '{h_id}'")
            if res_res.query_log:
                query_logs.append(res_res.query_log)
            total_rows += res_res.row_count

            res_strategy = h_obj.get("resolution_strategy")
            transfer_fix = h_obj.get("transferrable_fix")
            has_resolution_node = False

            if res_res.rows and len(res_res.rows[0]) >= 3:
                has_resolution_node = True
                res_node = safe_get_dict(res_res.rows[0][2])
                if not res_strategy:
                    res_strategy = res_node.get("strategy") or res_node.get("title")
                if not transfer_fix:
                    transfer_fix = res_node.get("fix") or res_node.get("action")

            has_verified_fix = bool(
                (res_strategy and str(res_strategy).strip()) or
                (transfer_fix and str(transfer_fix).strip())
            )

            if has_verified_fix:
                if not res_strategy or not str(res_strategy).strip():
                    res_strategy = "Verified resolution record present without separate strategy narrative."
                if not transfer_fix or not str(transfer_fix).strip():
                    transfer_fix = "Verified resolution record present without specific automated config fix."
                influence_explanation = (
                    f"Incident {h_id} shares pattern: '{pattern_note}'. "
                    f"Its verified resolution strategy directly informs our mitigation recommendation."
                )
            elif has_resolution_node:
                res_strategy = "UNVERIFIED: Resolution node is linked in graph memory but contains empty or missing strategy properties."
                transfer_fix = "UNVERIFIED: Linked resolution node contains no actionable fix parameters."
                influence_explanation = (
                    f"Incident {h_id} shares pattern: '{pattern_note}' and references a resolution node, "
                    f"but its fix parameters are unrecorded in graph memory."
                )
            else:
                res_strategy = "UNAVAILABLE: No documented resolution recorded in graph memory for this historical incident."
                transfer_fix = "UNAVAILABLE: No verified transferable fix recorded in graph memory."
                influence_explanation = (
                    f"Incident {h_id} shares failure pattern: '{pattern_note}' (similarity {sim_score}), "
                    f"but has no recorded resolution in graph memory. Caution: manual investigation required before taking action."
                )

            matches.append(
                HistoricalIncidentMatch(
                    incident_id=h_id,
                    title=h_obj.get("title", f"Historical Incident {h_id}"),
                    similarity_score=round(sim_score, 2),
                    resolved_at=h_obj.get("resolved_at"),
                    root_cause_summary=h_obj.get("root_cause_summary", "Past incident resolution record"),
                    resolution_strategy=res_strategy,
                    transferrable_fix=transfer_fix,
                    proof_path=f"{incident_id} -[:SIMILAR_TO {{similarity: {sim_score}}}]-> {h_id}",
                    influence_explanation=influence_explanation,
                )
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        tool_record = ToolExecutionRecord(
            step_number=step_number,
            tool_name="MemoryRetrievalTool",
            operation="graph_memory_similarity_lookup",
            input_parameters={"incident_id": incident_id},
            rows_returned=total_rows,
            execution_time_ms=round(elapsed_ms, 2),
            evidence_items_derived=len(matches),
            summary=f"Retrieved {len(matches)} historical incident precedent(s) linked by graph similarity." if matches else "No historical incident precedents matched in graph memory.",
            status="SUCCESS" if matches else "EMPTY",
        )

        return MemoryRetrievalResult(
            matches=matches,
            query_logs=query_logs,
            tool_record=tool_record,
        )


cypher_query_tool = CypherQueryTool()
dependency_cascade_tool = DependencyCascadeTool()
memory_retrieval_tool = MemoryRetrievalTool()

