export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type IncidentStatus = 'ACTIVE' | 'INVESTIGATING' | 'IDENTIFIED' | 'MITIGATED' | 'RESOLVED';
export type ActionStatus = 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'EXECUTED';

export type NodeType =
  | 'Service'
  | 'Incident'
  | 'ErrorPattern'
  | 'Deployment'
  | 'MetricAnomaly'
  | 'Database'
  | 'Queue'
  | 'Resolution';

export type EdgeType =
  | 'DEPENDS_ON'
  | 'AFFECTS'
  | 'TRIGGERED_BY'
  | 'CAUSED_BY'
  | 'RESOLVED_BY'
  | 'DEPLOYED_TO'
  | 'CONNECTS_TO'
  | 'PROPAGATES_TO'
  | 'SIMILAR_TO';

export interface GraphNode {
  id: string;
  label: NodeType | string;
  name?: string;
  status?: string;
  tier?: string;
  language?: string;
  type?: string;
  version?: string;
  severity?: string;
  properties?: Record<string, any>;
  [key: string]: any;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: EdgeType | string;
  weight?: number;
  properties?: Record<string, any>;
  [key: string]: any;
}

export interface GraphTopology {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  query_time_ms: number;
  engine_type: string;
}

export interface EvidencePathStep {
  from_node: string;
  to_node: string;
  relationship: string;
  explanation: string;
}

export interface EvidenceItem {
  id: string;
  title: string;
  description: string;
  source_node: string;
  target_node: string;
  relationship_type: string;
  confidence_score: number;
  is_confirmed_fact: boolean;
  cypher_proof_query: string;
  evidence_path: EvidencePathStep[];
}

export interface HistoricalIncidentMatch {
  incident_id: string;
  title: string;
  similarity_score: number;
  resolved_at?: string;
  root_cause_summary: string;
  resolution_strategy: string;
  transferrable_fix: string;
  proof_path: string;
  influence_explanation: string;
}

export interface ActionPlanItem {
  action_id: string;
  title: string;
  description: string;
  target_service: string;
  action_type: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  confidence: number;
  requires_human_approval: boolean;
  status: ActionStatus;
  dry_run_output: string;
  approval_notes?: string;
  executed_at?: string;
}

export interface CypherQueryLog {
  cypher: string;
  params: Record<string, any>;
  execution_time_ms: number;
  rows_returned: number;
  purpose: string;
}

export interface ToolExecutionRecord {
  step_number: number;
  tool_name: string;
  operation: string;
  input_parameters?: Record<string, any>;
  rows_returned?: number;
  execution_time_ms?: number;
  evidence_items_derived?: number;
  summary?: string;
  status?: string;
}

export interface InvestigationResult {
  investigation_id: string;
  incident_id: string;
  incident_title: string;
  status: IncidentStatus | string;
  primary_root_cause: string;
  summary: string;
  confirmed_facts: EvidenceItem[];
  root_cause_hypotheses: EvidenceItem[];
  relationship_paths: string[][];
  memory_matches: HistoricalIncidentMatch[];
  recommended_actions: ActionPlanItem[];
  cypher_queries_executed: CypherQueryLog[];
  tool_execution_trace?: ToolExecutionRecord[];
  execution_time_ms: number;
  created_at: string;
  llm_provider_used: string;
}

export interface SystemHealthStatus {
  status: string;
  app_name: string;
  version: string;
  uptime_seconds: number;
  falkordb: {
    is_live_connected: boolean;
    engine_mode: string;
    total_nodes: number;
    total_edges: number;
    graph_name: string;
  };
  llm: {
    provider: string;
    model: string;
    is_demo_mode: boolean;
  };
}
