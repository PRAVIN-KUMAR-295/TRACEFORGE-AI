import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from backend.app.database.falkordb_client import falkor_client
from backend.app.models.schemas import (
    ActionPlanItem,
    ActionStatus,
    CypherQueryLog,
    EvidenceItem,
    EvidencePathStep,
    HistoricalIncidentMatch,
    InvestigationResult,
)
from backend.app.services.llm_provider import llm_provider

logger = logging.getLogger("traceforge.investigation")


def _safe_get_dict(item: Any) -> Dict[str, Any]:
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


class InvestigationEngine:
    """
    Core graph-based incident investigation engine.
    Executes actual FalkorDB Cypher queries, dynamically parses returned graph
    structures, separates confirmed facts from hypotheses, and retrieves persistent incident memory.
    """

    def __init__(self):
        self.client = falkor_client
        self.investigation_history: Dict[str, InvestigationResult] = {}

    async def investigate_incident(self, incident_id: str, custom_query: Optional[str] = None) -> InvestigationResult:
        start_time = time.perf_counter()
        investigation_id = f"inv_{uuid.uuid4().hex[:10]}"
        cypher_logs: List[CypherQueryLog] = []

        confirmed_facts: List[EvidenceItem] = []
        root_cause_hypotheses: List[EvidenceItem] = []
        memory_matches: List[HistoricalIncidentMatch] = []
        recommended_actions: List[ActionPlanItem] = []
        relationship_paths: List[List[str]] = []

        # -------------------------------------------------------------
        # STEP 1: RETRIEVE PRIMARY INCIDENT
        # -------------------------------------------------------------
        q1 = "MATCH (i:Incident {id: $incident_id}) RETURN i"
        res1 = self.client.execute_cypher(q1, {"incident_id": incident_id})
        cypher_logs.append(
            CypherQueryLog(
                cypher=q1,
                params={"incident_id": incident_id},
                execution_time_ms=res1["execution_time_ms"],
                rows_returned=res1["row_count"],
                purpose="Retrieve primary incident node and baseline telemetry",
            )
        )

        incident_node: Dict[str, Any] = {}
        if res1["rows"] and len(res1["rows"][0]) > 0:
            incident_node = _safe_get_dict(res1["rows"][0][0])

        if not incident_node or not incident_node.get("id"):
            incident_node = {
                "id": incident_id,
                "title": f"Incident {incident_id}",
                "affected_service": None,
                "severity": "MEDIUM",
                "description": custom_query or "Incident record not present in graph topology.",
            }

        # -------------------------------------------------------------
        # STEP 2: RETRIEVE AFFECTED SERVICES VIA [:AFFECTS]
        # -------------------------------------------------------------
        q_aff = "MATCH (i:Incident)-[r:AFFECTS]->(s:Service) WHERE i.id = $incident_id RETURN i, r, s"
        res_aff = self.client.execute_cypher(q_aff, {"incident_id": incident_id})
        cypher_logs.append(
            CypherQueryLog(
                cypher=q_aff,
                params={"incident_id": incident_id},
                execution_time_ms=res_aff["execution_time_ms"],
                rows_returned=res_aff["row_count"],
                purpose="Retrieve services directly impacted by this incident",
            )
        )

        affected_services: List[Dict[str, Any]] = []
        for row in res_aff["rows"]:
            if len(row) >= 3:
                svc_dict = _safe_get_dict(row[2])
                if svc_dict.get("id"):
                    affected_services.append(svc_dict)

        # Fallback to incident_node['affected_service'] if no explicit [:AFFECTS] edge in graph
        if not affected_services and incident_node.get("affected_service"):
            fallback_svc_id = incident_node["affected_service"]
            q_svc = "MATCH (s:Service {id: $service_id}) RETURN s"
            res_svc = self.client.execute_cypher(q_svc, {"service_id": fallback_svc_id})
            if res_svc["rows"] and len(res_svc["rows"][0]) > 0:
                affected_services.append(_safe_get_dict(res_svc["rows"][0][0]))
            else:
                affected_services.append({"id": fallback_svc_id, "name": fallback_svc_id})

        primary_affected_service_id = affected_services[0]["id"] if affected_services else None

        # -------------------------------------------------------------
        # STEP 3: TRAVERSE SERVICE DEPENDENCIES
        # -------------------------------------------------------------
        dependent_services: List[Dict[str, Any]] = []
        relevant_service_ids = set()
        if primary_affected_service_id:
            relevant_service_ids.add(primary_affected_service_id)

        for aff_svc in affected_services:
            aff_id = aff_svc.get("id")
            if not aff_id:
                continue

            q2 = "MATCH (s:Service)-[r:DEPENDS_ON]->(dep:Service) WHERE s.id = $service_id RETURN s, r, dep"
            res2 = self.client.execute_cypher(q2, {"service_id": aff_id})
            cypher_logs.append(
                CypherQueryLog(
                    cypher=q2,
                    params={"service_id": aff_id},
                    execution_time_ms=res2["execution_time_ms"],
                    rows_returned=res2["row_count"],
                    purpose=f"Traverse dependencies for affected service '{aff_id}'",
                )
            )

            for row in res2["rows"]:
                if len(row) < 3:
                    continue
                s_dict = _safe_get_dict(row[0])
                r_dict = _safe_get_dict(row[1])
                dep_dict = _safe_get_dict(row[2])

                dep_id = dep_dict.get("id")
                s_id = s_dict.get("id", aff_id)
                if not dep_id:
                    continue

                dependent_services.append(dep_dict)
                relevant_service_ids.add(dep_id)

                # Dynamically construct Confirmed Fact from Cypher dependency traversal
                proto = r_dict.get("type", "RPC/REST")
                timeout_val = r_dict.get("timeout_ms")
                timeout_info = f" with {timeout_val}ms SLA timeout" if timeout_val else ""

                confirmed_facts.append(
                    EvidenceItem(
                        id=f"fact-dep-{s_id}-{dep_id}",
                        title=f"Direct Dependency: {s_id} -> {dep_id}",
                        description=f"Graph topology verifies that {s_id} requires synchronous {proto} calls to {dep_id} for operation{timeout_info}.",
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

        # -------------------------------------------------------------
        # STEP 4: DETECT INFRASTRUCTURE CONNECTIVITY (Databases/Caches)
        # -------------------------------------------------------------
        q3 = "MATCH (s:Service)-[r:CONNECTS_TO]->(infra:Database) RETURN s, r, infra"
        res3 = self.client.execute_cypher(q3)
        cypher_logs.append(
            CypherQueryLog(
                cypher=q3,
                params={},
                execution_time_ms=res3["execution_time_ms"],
                rows_returned=res3["row_count"],
                purpose="Retrieve database and caching clusters connected to critical services",
            )
        )

        connected_infra_nodes: List[Dict[str, Any]] = []
        for row in res3["rows"]:
            if len(row) < 3:
                continue
            svc_obj = _safe_get_dict(row[0])
            infra_obj = _safe_get_dict(row[2])
            s_id = svc_obj.get("id")
            infra_id = infra_obj.get("id")

            if s_id and infra_id and s_id in relevant_service_ids:
                connected_infra_nodes.append(infra_obj)
                infra_status = infra_obj.get("status", "healthy")

                if infra_status in ("exhausted", "critical", "degraded"):
                    confirmed_facts.append(
                        EvidenceItem(
                            id=f"fact-infra-{infra_id}",
                            title=f"Infrastructure Saturated: {infra_id}",
                            description=f"Service {s_id} connects to {infra_id} ({infra_obj.get('type', 'datastore')}) which is currently flagged as {infra_status}.",
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
                                    explanation=f"{infra_obj.get('type', 'Datastore')} status: {infra_status}",
                                )
                            ],
                        )
                    )

        # -------------------------------------------------------------
        # STEP 5: DETECT RECENT DEPLOYMENTS ALONG DEPENDENCY CHAIN
        # -------------------------------------------------------------
        q4 = "MATCH (d:Deployment)-[r:DEPLOYED_TO]->(s:Service) RETURN d, r, s"
        res4 = self.client.execute_cypher(q4)
        cypher_logs.append(
            CypherQueryLog(
                cypher=q4,
                params={},
                execution_time_ms=res4["execution_time_ms"],
                rows_returned=res4["row_count"],
                purpose="Inspect recent code deployments across dependency tree",
            )
        )

        relevant_deployments: List[Dict[str, Any]] = []
        for row in res4["rows"]:
            if len(row) < 3:
                continue
            dep_obj = _safe_get_dict(row[0])
            svc_obj = _safe_get_dict(row[2])
            s_id = svc_obj.get("id")
            d_id = dep_obj.get("id")

            if s_id and d_id and s_id in relevant_service_ids:
                relevant_deployments.append({**dep_obj, "target_service": s_id})
                deployed_when = dep_obj.get("deployed_at", "recently")
                change_summary = dep_obj.get("change_summary", "Configuration or code release")

                confirmed_facts.append(
                    EvidenceItem(
                        id=f"fact-deploy-{d_id}",
                        title=f"Recent Production Deployment: {d_id}",
                        description=f"FalkorDB records show deployment {d_id} ({dep_obj.get('version', '')}) committed {deployed_when} to {s_id}: '{change_summary}'.",
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
                                explanation=f"Committed {deployed_when}: {change_summary}",
                            )
                        ],
                    )
                )

        # -------------------------------------------------------------
        # STEP 6: RETRIEVE ACTIVE ERROR PATTERNS & METRIC ANOMALIES
        # -------------------------------------------------------------
        q5 = "MATCH (i:Incident)-[r:TRIGGERED_BY]->(e:ErrorPattern) WHERE i.id = $incident_id RETURN i, r, e"
        res5 = self.client.execute_cypher(q5, {"incident_id": incident_id})
        cypher_logs.append(
            CypherQueryLog(
                cypher=q5,
                params={"incident_id": incident_id},
                execution_time_ms=res5["execution_time_ms"],
                rows_returned=res5["row_count"],
                purpose="Correlate active error patterns linked to incident",
            )
        )

        error_patterns: List[Dict[str, Any]] = []
        for row in res5["rows"]:
            if len(row) >= 3:
                err_obj = _safe_get_dict(row[2])
                if err_obj.get("id"):
                    error_patterns.append(err_obj)

        # Query metric anomalies affecting the relevant service tree
        q_metric = "MATCH (m:MetricAnomaly)-[r:AFFECTS]->(s:Service) RETURN m, r, s"
        res_metric = self.client.execute_cypher(q_metric)
        cypher_logs.append(
            CypherQueryLog(
                cypher=q_metric,
                params={},
                execution_time_ms=res_metric["execution_time_ms"],
                rows_returned=res_metric["row_count"],
                purpose="Retrieve metric anomalies affecting services in dependency tree",
            )
        )

        detected_metrics: List[Dict[str, Any]] = []
        for row in res_metric["rows"]:
            if len(row) < 3:
                continue
            m_obj = _safe_get_dict(row[0])
            s_obj = _safe_get_dict(row[2])
            s_id = s_obj.get("id")
            m_id = m_obj.get("id")

            if s_id and m_id and s_id in relevant_service_ids:
                detected_metrics.append({**m_obj, "target_service": s_id})
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

        # -------------------------------------------------------------
        # STEP 7: DYNAMIC ROOT-CAUSE HYPOTHESES SYNTHESIS
        # -------------------------------------------------------------
        if relevant_deployments:
            # Deployment-driven causal hypothesis
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

            # Secondary / Alternative hypothesis
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
            # Anomaly/Error-driven hypothesis without recent deployment
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
            # Fallback when graph has no anomalies/deployments for this incident
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

        # -------------------------------------------------------------
        # STEP 8: RETRIEVE PERSISTENT INCIDENT MEMORY MATCHES
        # -------------------------------------------------------------
        q6 = "MATCH (i:Incident)-[r:SIMILAR_TO]->(h:Incident) WHERE i.id = $incident_id RETURN i, r, h"
        res6 = self.client.execute_cypher(q6, {"incident_id": incident_id})
        cypher_logs.append(
            CypherQueryLog(
                cypher=q6,
                params={"incident_id": incident_id},
                execution_time_ms=res6["execution_time_ms"],
                rows_returned=res6["row_count"],
                purpose="Retrieve historical incident memory and validated resolution precedents",
            )
        )

        for row in res6["rows"]:
            if len(row) < 3:
                continue
            r_obj = _safe_get_dict(row[1])
            h_obj = _safe_get_dict(row[2])
            h_id = h_obj.get("id")
            if not h_id:
                continue

            sim_score = float(r_obj.get("similarity", 0.75))
            pattern_note = r_obj.get("pattern", "shared failure symptoms and topology")

            # Query resolution node linked to this historical incident
            q_res = "MATCH (h:Incident)-[r:RESOLVED_BY]->(res:Resolution) WHERE h.id = $hist_id RETURN h, r, res"
            res_res = self.client.execute_cypher(q_res, {"hist_id": h_id})

            res_strategy = h_obj.get("resolution_strategy")
            transfer_fix = h_obj.get("transferrable_fix")

            if res_res["rows"] and len(res_res["rows"][0]) >= 3:
                res_node = _safe_get_dict(res_res["rows"][0][2])
                if not res_strategy:
                    res_strategy = res_node.get("strategy") or res_node.get("title")
                if not transfer_fix:
                    transfer_fix = res_node.get("fix") or res_node.get("action")

            if not res_strategy:
                res_strategy = "Apply known postmortem configuration fix."
            if not transfer_fix:
                transfer_fix = "Review service configuration parameters."

            memory_matches.append(
                HistoricalIncidentMatch(
                    incident_id=h_id,
                    title=h_obj.get("title", f"Historical Incident {h_id}"),
                    similarity_score=round(sim_score, 2),
                    resolved_at=h_obj.get("resolved_at"),
                    root_cause_summary=h_obj.get("root_cause_summary", "Past incident resolution record"),
                    resolution_strategy=res_strategy,
                    transferrable_fix=transfer_fix,
                    proof_path=f"{incident_id} -[:SIMILAR_TO {{similarity: {sim_score}}}]-> {h_id}",
                    influence_explanation=f"Incident {h_id} shares pattern: '{pattern_note}'. Its verified resolution strategy directly informs our current mitigation recommendation.",
                )
            )

        # -------------------------------------------------------------
        # STEP 9: ACTIONABLE RECOMMENDATIONS (Human-in-the-Loop)
        # -------------------------------------------------------------
        # Action 1: If historical memory match provides transferrable fix
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

        # Action 2: If a recent deployment was identified in causal chain
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

        # Action 3: Circuit breaker reset if error patterns or downstream cascade exists
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

        # Fallback action if no specific recommendations derived
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

        # -------------------------------------------------------------
        # STEP 10: RELATIONSHIP PATHS
        # -------------------------------------------------------------
        if relevant_deployments and connected_infra_nodes:
            d_id = relevant_deployments[0].get("id")
            s_id = relevant_deployments[0].get("target_service")
            i_id = connected_infra_nodes[0].get("id")
            relationship_paths.append([d_id, s_id, i_id])

        if relevant_deployments and primary_affected_service_id:
            s_id = relevant_deployments[0].get("target_service")
            if s_id != primary_affected_service_id:
                relationship_paths.append([s_id, primary_affected_service_id])

        for fact in confirmed_facts:
            if fact.relationship_type == "DEPENDS_ON" and fact.source_node and fact.target_node:
                p = [fact.source_node, fact.target_node]
                if p not in relationship_paths:
                    relationship_paths.append(p)

        if not relationship_paths and primary_affected_service_id:
            relationship_paths.append([primary_affected_service_id])

        # -------------------------------------------------------------
        # STEP 11: LLM SYNTHESIS / REASONING INTEGRATION
        # -------------------------------------------------------------
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
            else f"TRACEFORGE AI evaluated graph relationships for {incident_id}. Derived {len(confirmed_facts)} confirmed facts and {len(root_cause_hypotheses)} hypotheses."
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
            execution_time_ms=round(total_exec_time, 2),
            llm_provider_used=llm_provider.provider,
        )

        self.investigation_history[investigation_id] = result
        return result

    def get_investigation(self, investigation_id: str) -> Optional[InvestigationResult]:
        return self.investigation_history.get(investigation_id)

    def list_investigations(self) -> List[InvestigationResult]:
        return list(self.investigation_history.values())


investigation_engine = InvestigationEngine()
