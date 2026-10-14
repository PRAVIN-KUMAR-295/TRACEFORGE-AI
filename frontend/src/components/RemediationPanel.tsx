import React, { useState } from 'react';
import {
  ShieldAlert,
  CheckCircle,
  XCircle,
  AlertOctagon,
  Terminal,
  UserCheck,
  RotateCcw,
  Sliders,
  Power
} from 'lucide-react';
import { ActionPlanItem, ActionStatus } from '../types';

interface RemediationPanelProps {
  investigationId: string;
  actions: ActionPlanItem[];
  onApproveAction: (actionId: string, approved: boolean, notes: string) => Promise<void>;
  isProcessingAction?: boolean;
}

export const RemediationPanel: React.FC<RemediationPanelProps> = ({
  investigationId,
  actions,
  onApproveAction,
  isProcessingAction = false
}) => {
  const [selectedAction, setSelectedAction] = useState<ActionPlanItem | null>(null);
  const [approvalNotes, setApprovalNotes] = useState('');
  const [operatorName, setOperatorName] = useState('Alex Rivera (Lead SRE)');
  const [activeActionId, setActiveActionId] = useState<string | null>(null);

  const handleActionDecision = async (actionId: string, approved: boolean) => {
    setActiveActionId(actionId);
    try {
      await onApproveAction(actionId, approved, approvalNotes);
      setSelectedAction(null);
      setApprovalNotes('');
    } finally {
      setActiveActionId(null);
    }
  };

  const getActionIcon = (type: string) => {
    switch (type) {
      case 'ROLLBACK':
        return <RotateCcw className="w-4 h-4 text-violet-400" />;
      case 'CONFIG_UPDATE':
        return <Sliders className="w-4 h-4 text-cyan-400" />;
      case 'CIRCUIT_BREAKER':
        return <Power className="w-4 h-4 text-amber-400" />;
      default:
        return <Terminal className="w-4 h-4 text-blue-400" />;
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'HIGH':
        return <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] font-mono font-bold">HIGH RISK</span>;
      case 'MEDIUM':
        return <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[10px] font-mono font-bold">MEDIUM RISK</span>;
      default:
        return <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono font-bold">LOW RISK</span>;
    }
  };

  return (
    <div className="bg-dark-850 rounded-xl border border-dark-700 overflow-hidden shadow-xl">
      <div className="p-4 bg-gradient-to-r from-amber-950/40 via-dark-800 to-emerald-950/30 border-b border-dark-700">
        <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-amber-400 mb-1">
          <AlertOctagon className="w-4 h-4 text-amber-400" />
          <span>Actionable Recommendations & Human Gate</span>
        </div>
        <h2 className="text-base font-bold text-white mb-0.5">Mitigation Proposals (Human-in-the-Loop)</h2>
        <p className="text-xs text-slate-400">
          Strict Policy: Automated execution without explicit human approval is permanently disabled.
        </p>
      </div>

      <div className="p-4 space-y-3">
        {actions.map(action => {
          const isPending = action.status === 'PENDING_APPROVAL';
          const isExecuted = action.status === 'EXECUTED';
          const isRejected = action.status === 'REJECTED';
          const isCurrentLoading = isProcessingAction && activeActionId === action.action_id;

          return (
            <div
              key={action.action_id}
              className={`p-4 rounded-xl border transition-all ${
                isExecuted
                  ? 'bg-emerald-950/10 border-emerald-500/40'
                  : isRejected
                  ? 'bg-rose-950/10 border-rose-500/30 opacity-75'
                  : 'bg-dark-800 border-dark-700 hover:border-amber-500/40'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  <div className="p-2 rounded-lg bg-dark-900 border border-dark-750">
                    {getActionIcon(action.action_type)}
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-xs text-white">{action.title}</span>
                      {getRiskBadge(action.risk_level)}
                      <span className="text-[10px] font-mono text-slate-400 bg-dark-900 px-1.5 py-0.5 rounded border border-dark-750">
                        CONFIDENCE: {Math.round(action.confidence * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 mt-1 leading-relaxed">{action.description}</p>
                    <div className="mt-2 flex items-center space-x-4 text-[11px] font-mono text-slate-400">
                      <span>Target: <strong className="text-blue-400">{action.target_service}</strong></span>
                      <span>Action: <strong className="text-violet-400">{action.action_type}</strong></span>
                    </div>
                  </div>
                </div>

                {/* Status Indicator */}
                <div>
                  {isExecuted && (
                    <div className="flex items-center space-x-1.5 text-emerald-400 text-xs font-mono font-bold bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/30">
                      <CheckCircle className="w-4 h-4" />
                      <span>EXECUTED</span>
                    </div>
                  )}
                  {isRejected && (
                    <div className="flex items-center space-x-1.5 text-rose-400 text-xs font-mono font-bold bg-rose-500/10 px-2.5 py-1 rounded-lg border border-rose-500/30">
                      <XCircle className="w-4 h-4" />
                      <span>REJECTED</span>
                    </div>
                  )}
                  {isPending && (
                    <div className="flex items-center space-x-1.5 text-amber-400 text-xs font-mono font-bold bg-amber-500/10 px-2.5 py-1 rounded-lg border border-amber-500/30">
                      <UserCheck className="w-4 h-4" />
                      <span>AWAITING APPROVAL</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Dry Run Output Preview */}
              <div className="mt-3 p-2.5 rounded bg-dark-900 border border-dark-750 font-mono text-[11px] text-slate-300">
                <span className="text-slate-500 text-[10px] uppercase block mb-0.5 font-bold">
                  // Dry-Run Simulation Output:
                </span>
                <p className="text-cyan-300/90">{action.dry_run_output}</p>
              </div>

              {/* Executed notes / approval info */}
              {action.approval_notes && (
                <div className="mt-2 text-[11px] font-mono text-slate-400 italic">
                  Note: {action.approval_notes}
                </div>
              )}

              {/* Human Approval Gate Controls */}
              {isPending && (
                <div className="mt-3 pt-3 border-t border-dark-700/80 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2 text-xs text-slate-400">
                    <UserCheck className="w-3.5 h-3.5 text-blue-400" />
                    <span className="font-mono">Approver:</span>
                    <input
                      type="text"
                      value={operatorName}
                      onChange={e => setOperatorName(e.target.value)}
                      className="bg-dark-900 border border-dark-750 rounded px-2 py-1 text-xs text-slate-200 font-mono w-48 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleActionDecision(action.action_id, false)}
                      disabled={isCurrentLoading}
                      className="px-3 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 text-xs font-medium border border-rose-500/30 transition-all flex items-center space-x-1"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>

                    <button
                      onClick={() => handleActionDecision(action.action_id, true)}
                      disabled={isCurrentLoading}
                      className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all flex items-center space-x-1.5 disabled:opacity-50"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>{isCurrentLoading ? 'Executing...' : 'Approve & Execute'}</span>
                    </button>
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
