import {
  GraphTopology,
  InvestigationResult,
  SystemHealthStatus,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL !== undefined ? import.meta.env.VITE_API_URL : '';

export async function fetchHealth(): Promise<SystemHealthStatus> {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchTopology(): Promise<GraphTopology> {
  const res = await fetch(`${API_BASE_URL}/api/graph/topology`);
  if (!res.ok) throw new Error('Failed to load topology');
  return res.json();
}

export async function fetchSubgraph(nodeId: string, depth = 2): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/graph/subgraph/${encodeURIComponent(nodeId)}?depth=${depth}`);
  if (!res.ok) throw new Error(`Failed to load subgraph for ${nodeId}`);
  return res.json();
}

export async function runOneClickDemo(): Promise<InvestigationResult> {
  const res = await fetch(`${API_BASE_URL}/api/investigations/demo`);
  if (!res.ok) throw new Error('Failed to run demo investigation');
  return res.json();
}

export async function startInvestigation(incidentId: string, customDescription?: string): Promise<InvestigationResult> {
  const res = await fetch(`${API_BASE_URL}/api/investigations/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ incident_id: incidentId, custom_description: customDescription })
  });
  if (!res.ok) throw new Error('Investigation request failed');
  return res.json();
}

export async function getInvestigation(investigationId: string): Promise<InvestigationResult> {
  const res = await fetch(`${API_BASE_URL}/api/investigations/${investigationId}`);
  if (!res.ok) throw new Error('Failed to fetch investigation');
  return res.json();
}

export async function listInvestigations(): Promise<InvestigationResult[]> {
  const res = await fetch(`${API_BASE_URL}/api/investigations`);
  if (!res.ok) throw new Error('Failed to list investigations');
  return res.json();
}

export async function approveRemediationAction(
  investigationId: string,
  actionId: string,
  approved: boolean,
  approvedBy = 'DevOps Lead',
  notes?: string
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/remediation/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      investigation_id: investigationId,
      action_id: actionId,
      approved,
      approved_by: approvedBy,
      notes
    })
  });
  if (!res.ok) throw new Error('Failed to process approval action');
  return res.json();
}

export async function executeCypherQuery(query: string, params: Record<string, any> = {}): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/graph/cypher`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, params })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Cypher execution failed' }));
    throw new Error(err.detail || 'Cypher query execution error');
  }
  return res.json();
}

export async function fetchHistoricalIncidents(): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/api/memory/incidents`);
  if (!res.ok) throw new Error('Failed to fetch historical incidents');
  return res.json();
}

export async function searchMemory(term: string, service?: string): Promise<any> {
  const url = `${API_BASE_URL}/api/memory/search?term=${encodeURIComponent(term)}${service ? `&service=${encodeURIComponent(service)}` : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to search memory');
  return res.json();
}

export async function storePostmortem(postmortemData: {
  incident_id: string;
  title: string;
  affected_service: string;
  root_cause_summary: string;
  resolution_strategy: string;
  transferrable_fix: string;
  impacted_services: string[];
}): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/memory/store`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(postmortemData)
  });
  if (!res.ok) throw new Error('Failed to record postmortem');
  return res.json();
}
