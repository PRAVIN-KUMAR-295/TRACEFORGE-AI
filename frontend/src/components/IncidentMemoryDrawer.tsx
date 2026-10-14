import React from 'react';
import { History, Sparkles, CheckCircle2, ArrowRight, GitCommit, ExternalLink } from 'lucide-react';
import { HistoricalIncidentMatch } from '../types';

interface IncidentMemoryDrawerProps {
  memoryMatches: HistoricalIncidentMatch[];
  onViewHistoricalIncident?: (incidentId: string) => void;
}

export const IncidentMemoryDrawer: React.FC<IncidentMemoryDrawerProps> = ({
  memoryMatches,
  onViewHistoricalIncident
}) => {
  return (
    <div className="bg-dark-850 rounded-xl border border-dark-700 overflow-hidden shadow-xl">
      <div className="p-4 bg-gradient-to-r from-cyan-950/40 via-dark-800 to-blue-950/30 border-b border-dark-700">
        <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-cyan-400 mb-1">
          <History className="w-4 h-4 text-cyan-400" />
          <span>FalkorDB Persistent Incident Memory</span>
        </div>
        <h2 className="text-base font-bold text-white mb-0.5">Historical Memory Matches & Precedents</h2>
        <p className="text-xs text-slate-400">
          Cross-session operational memory indexed in FalkorDB graph relationships to prevent recurring failures.
        </p>
      </div>

      <div className="p-4 space-y-4">
        {memoryMatches.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-xs font-mono">
            No historical precedent matches found in graph memory.
          </div>
        ) : (
          memoryMatches.map((match) => (
            <div
              key={match.incident_id}
              className="p-4 rounded-xl bg-dark-800 border border-dark-700/80 hover:border-cyan-500/50 transition-all space-y-3"
            >
              {/* Top row */}
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-cyan-400">{match.incident_id}</span>
                    <span className="text-xs font-semibold text-white">{match.title}</span>
                  </div>
                  {match.resolved_at && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      Resolved: {new Date(match.resolved_at).toLocaleDateString()}
                    </span>
                  )}
                </div>

                {/* Similarity Score Pill */}
                <div className="flex items-center space-x-1 px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 font-mono text-xs font-bold">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{Math.round(match.similarity_score * 100)}% SIMILARITY</span>
                </div>
              </div>

              {/* Historical Root Cause & Strategy */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 rounded-lg bg-dark-900 border border-dark-750">
                  <span className="text-slate-400 font-mono text-[10px] uppercase block mb-1">
                    Historical Root Cause:
                  </span>
                  <p className="text-slate-300 text-[11px] leading-relaxed">{match.root_cause_summary}</p>
                </div>

                <div className="p-2.5 rounded-lg bg-dark-900 border border-dark-750">
                  <span className="text-emerald-400 font-mono text-[10px] uppercase block mb-1">
                    Applied Resolution Strategy:
                  </span>
                  <p className="text-slate-300 text-[11px] leading-relaxed">{match.resolution_strategy}</p>
                </div>
              </div>

              {/* Influence Explanation (Section 4B requirement) */}
              <div className="p-2.5 rounded-lg bg-blue-950/30 border border-blue-500/30 text-xs">
                <div className="flex items-center space-x-1.5 text-blue-400 font-mono text-[11px] font-bold mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>How This Past Incident Influenced Current Recommendation:</span>
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">{match.influence_explanation}</p>
              </div>

              {/* Transferrable Fix */}
              <div className="flex items-center justify-between text-xs pt-1 border-t border-dark-750 text-slate-400">
                <div className="flex items-center space-x-1.5 font-mono text-[11px]">
                  <span className="text-slate-500">Transferrable Fix:</span>
                  <strong className="text-emerald-400">{match.transferrable_fix}</strong>
                </div>

                <span className="text-[10px] font-mono text-slate-500">
                  {match.proof_path}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
