import React, { useState } from 'react';
import {
  ShieldAlert,
  ArrowLeft,
  Clock,
  Cpu,
  Database,
  Terminal,
  Layers,
  Sparkles,
  CheckCircle,
  AlertTriangle
} from 'lucide-react';
import { GraphEdge, GraphNode, InvestigationResult } from '../types';
import { RootCauseHypothesisCard } from '../components/RootCauseHypothesisCard';
import { IncidentMemoryDrawer } from '../components/IncidentMemoryDrawer';
import { RemediationPanel } from '../components/RemediationPanel';
import { GraphVisualizer } from '../components/GraphVisualizer';
import { CypherQueryConsole } from '../components/CypherQueryConsole';

interface InvestigationDetailViewProps {
  investigation: InvestigationResult;
  nodes: GraphNode[];
  edges: GraphEdge[];
  onBack: () => void;
  onApproveAction: (actionId: string, approved: boolean, notes: string) => Promise<void>;
  isProcessingAction?: boolean;
}

export const InvestigationDetailView: React.FC<InvestigationDetailViewProps> = ({
  investigation,
  nodes,
  edges,
  onBack,
  onApproveAction,
  isProcessingAction
}) => {
  const [highlightPath, setHighlightPath] = useState<string[]>(
    investigation.relationship_paths?.[0] || []
  );

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-dark-700">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-dark-800 hover:bg-dark-750 border border-dark-700 text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-sm font-bold text-rose-400">{investigation.incident_id}</span>
              <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono text-[10px] font-bold border border-rose-500/30">
                CRITICAL
              </span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono text-[10px] font-bold border border-emerald-500/30">
                STATUS: {investigation.status}
              </span>
            </div>
            <h1 className="text-xl font-bold text-white mt-1">{investigation.incident_title}</h1>
          </div>
        </div>

        {/* Telemetry metadata */}
        <div className="flex items-center space-x-4 text-xs font-mono text-slate-400">
          <div className="flex items-center space-x-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>Triage: <strong className="text-white">{investigation.execution_time_ms}ms</strong></span>
          </div>
          <div className="flex items-center space-x-1.5">
            <Cpu className="w-3.5 h-3.5 text-violet-400" />
            <span>Provider: <strong className="text-violet-300 uppercase">{investigation.llm_provider_used}</strong></span>
          </div>
          <div className="flex items-center space-x-1.5">
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>Cypher Queries: <strong className="text-cyan-300">{investigation.cypher_queries_executed.length}</strong></span>
          </div>
        </div>
      </div>

      {/* Investigation Synthesis Summary */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-blue-950/30 via-dark-850 to-indigo-950/20 border border-blue-500/30">
        <div className="flex items-center space-x-2 text-xs font-mono font-bold text-blue-400 mb-1">
          <Sparkles className="w-4 h-4" />
          <span>INVESTIGATION EXECUTIVE SUMMARY</span>
        </div>
        <p className="text-xs text-slate-200 leading-relaxed font-sans">{investigation.summary}</p>
      </div>

      {/* Grid: Graph Visualizer & Evidence Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Interactive Dependency Cascade Graph */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold font-mono uppercase text-slate-400 flex items-center space-x-1.5">
              <Database className="w-3.5 h-3.5 text-cyan-400" />
              <span>Causal Cascade Graph View</span>
            </h3>
            <span className="text-[11px] font-mono text-slate-500">
              Interactive FalkorDB Topology
            </span>
          </div>
          <GraphVisualizer
            nodes={nodes}
            edges={edges}
            highlightPath={highlightPath}
            height="560px"
          />
        </div>

        {/* Right: Confirmed Facts vs Hypotheses */}
        <div>
          <RootCauseHypothesisCard
            confirmedFacts={investigation.confirmed_facts}
            hypotheses={investigation.root_cause_hypotheses}
            primaryRootCause={investigation.primary_root_cause}
            onHighlightPath={path => setHighlightPath(path)}
          />
        </div>
      </div>

      {/* Lower Grid: Persistent Memory & Actionable Remediation Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Historical Incident Memory */}
        <IncidentMemoryDrawer memoryMatches={investigation.memory_matches} />

        {/* Actionable Human-in-the-loop Recommendations */}
        <RemediationPanel
          investigationId={investigation.investigation_id}
          actions={investigation.recommended_actions}
          onApproveAction={onApproveAction}
          isProcessingAction={isProcessingAction}
        />
      </div>

      {/* Cypher Execution Trace Log */}
      <div>
        <CypherQueryConsole executedLogs={investigation.cypher_queries_executed} />
      </div>
    </div>
  );
};
