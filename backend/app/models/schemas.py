from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IncidentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    IDENTIFIED = "IDENTIFIED"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"


class ActionStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class NodeType(str, Enum):
    SERVICE = "Service"
    INCIDENT = "Incident"
    ERROR_PATTERN = "ErrorPattern"
    DEPLOYMENT = "Deployment"
    METRIC_ANOMALY = "MetricAnomaly"
    DATABASE = "Database"
    QUEUE = "Queue"
    RESOLUTION = "Resolution"


class EdgeType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    AFFECTS = "AFFECTS"
    TRIGGERED_BY = "TRIGGERED_BY"
    CAUSED_BY = "CAUSED_BY"
    RESOLVED_BY = "RESOLVED_BY"
    DEPLOYED_TO = "DEPLOYED_TO"
    CONNECTS_TO = "CONNECTS_TO"
    PROPAGATES_TO = "PROPAGATES_TO"


class GraphNode(BaseModel):
    id: str
    label: str
    type: NodeType
    properties: Dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = "healthy"
    description: Optional[str] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: EdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)
    weight: Optional[float] = 1.0


class GraphTopologyResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int
    total_edges: int
    query_time_ms: float
    engine_type: str = "FalkorDB"


class Incident(BaseModel):
    id: str
    title: str
    description: str
    severity: SeverityLevel
    status: IncidentStatus
    affected_service: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_pattern: Optional[str] = None
    error_logs: List[str] = Field(default_factory=list)
    impacted_services: List[str] = Field(default_factory=list)
    symptoms: List[str] = Field(default_factory=list)


class EvidencePathStep(BaseModel):
    from_node: str
    to_node: str
    relationship: str
    explanation: str


class EvidenceItem(BaseModel):
    id: str
    title: str
    description: str
    source_node: str
    target_node: str
    relationship_type: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    is_confirmed_fact: bool = False  # Distinguish confirmed facts from hypotheses
    cypher_proof_query: str
    evidence_path: List[EvidencePathStep] = Field(default_factory=list)


class HistoricalIncidentMatch(BaseModel):
    incident_id: str
    title: str
    similarity_score: float
    resolved_at: Optional[str] = None
    root_cause_summary: str
    resolution_strategy: str
    transferrable_fix: str
    proof_path: str
    influence_explanation: str  # Explains why this past incident influenced current recommendation


class ActionPlanItem(BaseModel):
    action_id: str
    title: str
    description: str
    target_service: str
    action_type: str  # ROLLBACK, SCALE, FLUSH_CACHE, CIRCUIT_BREAKER, RESTART
    risk_level: str  # LOW, MEDIUM, HIGH
    confidence: float
    requires_human_approval: bool = True
    status: ActionStatus = ActionStatus.PENDING_APPROVAL
    dry_run_output: str
    approval_notes: Optional[str] = None
    executed_at: Optional[str] = None


class CypherQueryLog(BaseModel):
    cypher: str
    params: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float
    rows_returned: int
    purpose: str


class InvestigationResult(BaseModel):
    investigation_id: str
    incident_id: str
    incident_title: str
    status: str
    primary_root_cause: str
    summary: str
    confirmed_facts: List[EvidenceItem]
    root_cause_hypotheses: List[EvidenceItem]
    relationship_paths: List[List[str]]
    memory_matches: List[HistoricalIncidentMatch]
    recommended_actions: List[ActionPlanItem]
    cypher_queries_executed: List[CypherQueryLog]
    execution_time_ms: float
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    llm_provider_used: str = "demo"


class IncidentCreateRequest(BaseModel):
    title: str
    description: str
    severity: SeverityLevel = SeverityLevel.HIGH
    affected_service: str
    error_logs: List[str] = Field(default_factory=list)


class ActionApprovalRequest(BaseModel):
    approved: bool
    notes: Optional[str] = None
    approved_by: str = "DevOps Engineer"


class CypherExecuteRequest(BaseModel):
    query: str
    params: Dict[str, Any] = Field(default_factory=dict)


class CypherExecuteResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    columns: List[str]
    row_count: int
    execution_time_ms: float
    engine: str
