import React, { useState } from 'react';
import {
  Terminal,
  GitBranch,
  Layers,
  Activity,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  Database,
  Code2
} from 'lucide-react';
import { ToolExecutionRecord } from '../types';

interface ToolExecutionTraceCardProps {
  trace?: ToolExecutionRecord[];
}

function getToolIcon(toolName: string) {
  const lower = (toolName || '').toLowerCase();
  if (lower.includes('cypher')) return Terminal;
  if (lower.includes('cascade') || lower.includes('dependency')) return GitBranch;
  if (lower.includes('memory') || lower.includes('retrieval')) return Layers;
  return Activity;
}

function getStatusBadge(status?: string) {
  const s = (status || '').toUpperCase();
  if (s === 'SUCCESS') {
    return {
      label: 'SUCCESS',
      className: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
      dotClass: 'bg-emerald-400',
      icon: CheckCircle2
    };
  }
  if (s === 'EMPTY') {
    return {
      label: 'EMPTY RESULT',
      className: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
      dotClass: 'bg-amber-400',
      icon: AlertCircle
    };
  }
  if (s === 'ERROR' || s === 'FAILED') {
    return {
      label: 'EXECUTION FAILED',
      className: 'bg-rose-500/15 text-rose-400 border border-rose-500/30',
      dotClass: 'bg-rose-400',
      icon: XCircle
    };
  }
  return {
    label: s || 'UNKNOWN',
    className: 'bg-slate-500/15 text-slate-300 border border-slate-500/30',
    dotClass: 'bg-slate-400',
    icon: Activity
  };
}

export const ToolExecutionTraceCard: React.FC<ToolExecutionTraceCardProps> = ({ trace = [] }) => {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  const toggleStepParams = (stepNum: number) => {
    setExpandedStep(prev => (prev === stepNum ? null : stepNum));
  };

  if (!trace || trace.length === 0) {
    return (
      <div className="bg-dark-850 rounded-xl border border-dark-700 p-5 shadow-xl">
        <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span>Agent Tool Execution Trace</span>
        </div>
        <p className="text-xs text-slate-400 font-mono">
          No tool execution audit records available for this investigation.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-dark-850 rounded-xl border border-dark-700 overflow-hidden shadow-xl">
      {/* Header */}
      <div className="p-4 bg-gradient-to-r from-cyan-950/40 via-dark-800 to-indigo-950/30 border-b border-dark-700 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-cyan-400 mb-1">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span>Agent Tool Execution Trace</span>
          </div>
          <h2 className="text-base font-bold text-white mb-0.5">
            Traceable Connected-Data Tool Execution
          </h2>
          <p className="text-xs text-slate-400">
            Audit trail of graph tools invoked during automated investigation.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <span className="px-2.5 py-1 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-mono text-[11px] font-semibold">
            {trace.length} tool step{trace.length === 1 ? '' : 's'} recorded
          </span>
        </div>
      </div>

      {/* Steps List */}
      <div className="p-4 space-y-3">
        {trace.map((step, idx) => {
          const ToolIcon = getToolIcon(step.tool_name);
          const badge = getStatusBadge(step.status);
          const StatusIcon = badge.icon;
          const hasParams =
            step.input_parameters && Object.keys(step.input_parameters).length > 0;
          const isExpanded = expandedStep === step.step_number;

          return (
            <div
              key={`tool-step-${step.step_number || idx}`}
              className="p-3.5 rounded-xl bg-dark-900 border border-dark-750 hover:border-dark-650 transition-all space-y-2.5"
            >
              {/* Top row: Step, Tool Name, Operation, and Status */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-2.5">
                  <span className="w-6 h-6 rounded-lg bg-dark-800 border border-dark-700 flex items-center justify-center font-mono text-xs font-bold text-cyan-300">
                    #{step.step_number ?? idx + 1}
                  </span>
                  <div className="flex items-center space-x-2">
                    <ToolIcon className="w-4 h-4 text-cyan-400" />
                    <span className="font-mono text-xs font-bold text-white">
                      {step.tool_name}
                    </span>
                  </div>
                  {step.operation && (
                    <span className="px-2 py-0.5 rounded bg-dark-800 text-slate-400 border border-dark-700 font-mono text-[10px]">
                      {step.operation}
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-2">
                  {step.execution_time_ms !== undefined && (
                    <div className="flex items-center space-x-1 text-[11px] font-mono text-slate-400">
                      <Clock className="w-3 h-3 text-slate-500" />
                      <span>{step.execution_time_ms}ms</span>
                    </div>
                  )}

                  <span
                    className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold ${badge.className}`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${badge.dotClass}`} />
                    <span>{badge.label}</span>
                  </span>
                </div>
              </div>

              {/* Summary / Observation */}
              {step.summary && (
                <p className="text-xs text-slate-300 leading-relaxed font-sans pl-8">
                  {step.summary}
                </p>
              )}

              {/* Metrics row: Rows returned & Derived evidence items */}
              <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono text-slate-400 pl-8 pt-1">
                {step.rows_returned !== undefined && (
                  <div className="flex items-center space-x-1">
                    <Database className="w-3 h-3 text-slate-500" />
                    <span>
                      Rows returned:{' '}
                      <strong className="text-slate-200">{step.rows_returned}</strong>
                    </span>
                  </div>
                )}

                {step.evidence_items_derived !== undefined && (
                  <div className="flex items-center space-x-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                    <span>
                      Evidence items derived:{' '}
                      <strong className="text-cyan-300">
                        {step.evidence_items_derived}
                      </strong>
                    </span>
                  </div>
                )}

                {hasParams && (
                  <button
                    onClick={() => toggleStepParams(step.step_number)}
                    className="ml-auto inline-flex items-center space-x-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
                  >
                    <Code2 className="w-3 h-3 text-cyan-400" />
                    <span>Parameters</span>
                    {isExpanded ? (
                      <ChevronDown className="w-3 h-3" />
                    ) : (
                      <ChevronRight className="w-3 h-3" />
                    )}
                  </button>
                )}
              </div>

              {/* Expandable Parameters Drawer */}
              {hasParams && isExpanded && (
                <div className="mt-2 pl-8">
                  <div className="p-2.5 rounded-lg bg-dark-950 border border-dark-800 font-mono text-[11px] text-slate-300 overflow-x-auto">
                    <div className="text-[10px] text-slate-500 uppercase mb-1">
                      // Input Parameters (Sanitized):
                    </div>
                    <pre className="text-cyan-300">
                      {JSON.stringify(step.input_parameters, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
