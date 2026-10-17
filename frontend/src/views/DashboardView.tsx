import React from 'react';
import {
  ShieldAlert,
  Server,
  Database,
  ArrowRight,
  Play,
  Clock,
  Sparkles,
  GitBranch,
  AlertTriangle,
  Layers,
  ChevronRight
} from 'lucide-react';
import { InvestigationResult } from '../types';

interface DashboardViewProps {
  onRunDemo: () => void;
  isDemoLoading: boolean;
  onSelectIncident: (incidentId: string) => void;
  recentInvestigations: InvestigationResult[];
  onOpenInvestigation: (inv: InvestigationResult) => void;
  onNavigateTab: (tab: string) => void;
  nodeCount?: number;
  edgeCount?: number;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  onRunDemo,
  isDemoLoading,
  onSelectIncident,
  recentInvestigations,
  onOpenInvestigation,
  onNavigateTab,
  nodeCount,
  edgeCount
}) => {
  // Deduplicate by incident ID keeping the latest run per incident, sorted newest first
  const displayInvestigations = React.useMemo(() => {
    const seen = new Set<string>();
    const unique: InvestigationResult[] = [];
    const sorted = [...recentInvestigations].sort((a, b) => {
      const tA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const tB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return tB - tA;
    });
    for (const inv of sorted) {
      if (!seen.has(inv.incident_id)) {
        seen.add(inv.incident_id);
        unique.push(inv);
      }
    }
    return unique;
  }, [recentInvestigations]);
  return (
    <div className="space-y-6">
      {/* Top Banner / Hero */}
      <div className="rounded-2xl bg-gradient-to-r from-blue-900/40 via-dark-850 to-indigo-900/40 border border-dark-700 p-6 shadow-2xl relative overflow-hidden">
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-500/20 border border-blue-400/30 text-blue-300 text-xs font-mono font-medium mb-3">
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            <span>FalkorDB Graph-Powered Incident Investigation Engine</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-tight">
            Trace software failures backwards through graph dependencies & incident memory.
          </h1>

          <p className="mt-2 text-sm text-slate-300 leading-relaxed">
            When microservices fail, ordinary chatbots lack topological relationship context. TRACEFORGE AI evaluates OpenCypher graph traversals across services, infrastructure, errors, deployments, and historical resolutions to deliver explainable, evidence-backed root cause analysis.
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              onClick={onRunDemo}
              disabled={isDemoLoading}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-semibold text-xs transition-all shadow-lg shadow-blue-500/25 flex items-center space-x-2 active:scale-95 disabled:opacity-50"
            >
              <Play className={`w-4 h-4 fill-current ${isDemoLoading ? 'animate-spin' : ''}`} />
              <span className="font-mono">{isDemoLoading ? 'Running Investigation...' : 'Start 1-Click Demo Investigation'}</span>
            </button>

            <button
              onClick={() => onNavigateTab('graph')}
              className="px-4 py-2.5 rounded-xl bg-dark-800 hover:bg-dark-750 border border-dark-700 text-slate-300 hover:text-white text-xs font-medium font-mono transition-all flex items-center space-x-1.5"
            >
              <span>Explore Graph Topology</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Background glow decoration */}
        <div className="absolute right-0 top-0 bottom-0 w-96 bg-gradient-to-l from-blue-600/10 to-transparent pointer-events-none" />
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>ACTIVE INCIDENTS</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-white">1 <span className="text-xs text-rose-400 font-normal">CRITICAL</span></div>
          <div className="text-[11px] text-slate-500 mt-1">Payment & Checkout Cascade</div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>GRAPH TOPOLOGY</span>
            <Database className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-white">{nodeCount || 29} <span className="text-xs text-cyan-400 font-normal">NODES</span></div>
          <div className="text-[11px] text-slate-500 mt-1">{edgeCount || 32} relationships mapped</div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>PERSISTENT MEMORY</span>
            <Layers className="w-4 h-4 text-violet-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-white">3 <span className="text-xs text-violet-400 font-normal">POSTMORTEMS</span></div>
          <div className="text-[11px] text-slate-500 mt-1">Cross-session graph recall</div>
        </div>

        <div className="p-4 rounded-xl bg-dark-850 border border-dark-700">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>AVERAGE TRIAGE TIME</span>
            <Clock className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-white">&lt; 50<span className="text-xs text-emerald-400 font-normal">ms</span></div>
          <div className="text-[11px] text-slate-500 mt-1">Real-time Cypher traversal</div>
        </div>
      </div>

      {/* Main Grid: Active Incidents & Recent Investigations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 cols: Active Incidents to Investigate */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold font-mono uppercase text-slate-300 flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span>Active Incidents Awaiting Triage</span>
            </h2>
            <span className="text-xs text-slate-500 font-mono">1 incident detected</span>
          </div>

          {/* Primary Live Incident Card */}
          <div className="p-5 rounded-xl bg-dark-850 border border-rose-500/40 shadow-xl space-y-3 relative overflow-hidden">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs font-bold text-rose-400">INC-2026-1042</span>
                  <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] font-mono font-bold">
                    CRITICAL SEVERITY
                  </span>
                </div>
                <h3 className="text-base font-bold text-white mt-1">
                  Payment & Checkout Cascade Outage (HTTP 503 Spike)
                </h3>
              </div>

              <button
                onClick={() => onSelectIncident('INC-2026-1042')}
                disabled={isDemoLoading}
                className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-semibold transition-all flex items-center space-x-1.5 shadow-md shadow-blue-600/30"
              >
                <span>Investigate</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Checkout failure rate spiked to 48.2% across mobile and web clients. Customers report unable to complete purchase; API Gateway returns 503 Service Unavailable on POST /v1/checkout.
            </p>

            {/* Incident Symptoms */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2 text-[11px] font-mono">
              <div className="p-2 rounded bg-dark-900 border border-dark-750 text-slate-300">
                <span className="text-slate-500 block text-[10px]">AFFECTED ROOT:</span>
                <span className="text-rose-400 font-semibold">checkout-service</span>
              </div>
              <div className="p-2 rounded bg-dark-900 border border-dark-750 text-slate-300">
                <span className="text-slate-500 block text-[10px]">ERROR SIGNATURE:</span>
                <span className="text-amber-400">ConnectionPoolExhausted</span>
              </div>
              <div className="p-2 rounded bg-dark-900 border border-dark-750 text-slate-300">
                <span className="text-slate-500 block text-[10px]">CASCADE SCOPE:</span>
                <span className="text-blue-400">4 services impacted</span>
              </div>
            </div>

            {/* Error Log Snippet */}
            <div className="p-2.5 rounded-lg bg-dark-900 border border-dark-750 font-mono text-[11px] text-slate-400 space-y-1">
              <div className="text-[10px] text-slate-500 uppercase font-bold">// Telemetry Log Stream:</div>
              <div className="text-rose-400 truncate">
                2026-10-14T16:18:22Z [auth-service] ConnectionPoolExhaustedError: Timeout waiting for free Redis connection (5000ms)
              </div>
              <div className="text-amber-300 truncate">
                2026-10-14T16:18:15Z [checkout-service] CircuitBreakerOpenException: Checkout-&gt;Auth circuit opened
              </div>
            </div>
          </div>
        </div>

        {/* Right 1 col: Recent Investigations History */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold font-mono uppercase text-slate-300 flex items-center space-x-2">
              <Clock className="w-4 h-4 text-cyan-400" />
              <span>Investigation History</span>
            </h2>
            {displayInvestigations.length > 0 && (
              <span className="text-[10px] font-mono text-slate-500">
                {displayInvestigations.length} incident{displayInvestigations.length === 1 ? '' : 's'}
                {recentInvestigations.length > displayInvestigations.length ? ` (${recentInvestigations.length} runs)` : ''}
              </span>
            )}
          </div>

          <div className="rounded-xl bg-dark-850 border border-dark-700 p-4 space-y-3">
            {displayInvestigations.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-500 font-mono space-y-2">
                <p>No investigations completed in this session.</p>
                <p className="text-blue-400 cursor-pointer hover:underline" onClick={onRunDemo}>
                  Run the 1-Click Demo to launch the first investigation.
                </p>
              </div>
            ) : (
              displayInvestigations.map(inv => {
                const runTime = inv.created_at
                  ? new Date(inv.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : null;
                const isMitigated = inv.status === 'MITIGATED';
                return (
                  <div
                    key={inv.investigation_id}
                    onClick={() => onOpenInvestigation(inv)}
                    className="p-3 rounded-lg bg-dark-800 hover:bg-dark-750 border border-dark-700/80 cursor-pointer transition-all space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-blue-400 font-bold">{inv.incident_id}</span>
                        <span className="font-mono text-[10px] text-slate-500">#{inv.investigation_id.slice(0, 8)}</span>
                      </div>
                      <div className="flex items-center space-x-1.5">
                        {runTime && <span className="font-mono text-[10px] text-slate-500">{runTime}</span>}
                        <span
                          className={`font-mono text-[10px] px-1.5 py-0.2 rounded ${
                            isMitigated
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                          }`}
                        >
                          {inv.status}
                        </span>
                      </div>
                    </div>
                    <h4 className="text-xs font-semibold text-white truncate">{inv.incident_title}</h4>
                    <p className="text-[11px] text-slate-400 line-clamp-2">{inv.primary_root_cause}</p>
                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 pt-1 border-t border-dark-750">
                      <span>{inv.execution_time_ms}ms</span>
                      <span>{(inv.confirmed_facts || []).length} facts / {(inv.recommended_actions || []).length} actions</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
