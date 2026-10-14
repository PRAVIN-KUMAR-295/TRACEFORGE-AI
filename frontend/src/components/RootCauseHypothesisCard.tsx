import React, { useState } from 'react';
import {
  CheckCircle,
  HelpCircle,
  Code2,
  ChevronRight,
  ChevronDown,
  ArrowRight,
  ShieldCheck,
  AlertTriangle
} from 'lucide-react';
import { EvidenceItem } from '../types';

interface RootCauseHypothesisCardProps {
  confirmedFacts: EvidenceItem[];
  hypotheses: EvidenceItem[];
  primaryRootCause: string;
  onHighlightPath?: (path: string[]) => void;
}

export const RootCauseHypothesisCard: React.FC<RootCauseHypothesisCardProps> = ({
  confirmedFacts,
  hypotheses,
  primaryRootCause,
  onHighlightPath
}) => {
  const [activeTab, setActiveTab] = useState<'facts' | 'hypotheses'>('facts');
  const [expandedQueryId, setExpandedQueryId] = useState<string | null>(null);

  const toggleQuery = (id: string) => {
    setExpandedQueryId(prev => (prev === id ? null : id));
  };

  return (
    <div className="bg-dark-850 rounded-xl border border-dark-700 overflow-hidden shadow-xl">
      {/* Header Banner */}
      <div className="p-4 bg-gradient-to-r from-blue-950/40 via-dark-800 to-indigo-950/30 border-b border-dark-700">
        <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-blue-400 mb-1">
          <ShieldCheck className="w-4 h-4 text-blue-400" />
          <span>FalkorDB Evidence Synthesis</span>
        </div>
        <h2 className="text-base font-bold text-white mb-1">Root Cause & Evidence Analysis</h2>
        <div className="p-2.5 rounded-lg bg-dark-900/80 border border-dark-700/80 text-xs text-slate-200 mt-2">
          <strong className="text-rose-400 font-mono block mb-0.5">PRIMARY ROOT CAUSE IDENTIFIED:</strong>
          <p className="leading-relaxed">{primaryRootCause}</p>
        </div>
      </div>

      {/* Tabs: Confirmed Facts vs Hypotheses */}
      <div className="flex border-b border-dark-700 bg-dark-800">
        <button
          onClick={() => setActiveTab('facts')}
          className={`flex-1 py-3 px-4 text-xs font-medium font-mono flex items-center justify-center space-x-2 border-b-2 transition-all ${
            activeTab === 'facts'
              ? 'border-emerald-500 text-emerald-400 bg-dark-850'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <CheckCircle className="w-4 h-4 text-emerald-400" />
          <span>Confirmed Facts ({confirmedFacts.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('hypotheses')}
          className={`flex-1 py-3 px-4 text-xs font-medium font-mono flex items-center justify-center space-x-2 border-b-2 transition-all ${
            activeTab === 'hypotheses'
              ? 'border-violet-500 text-violet-400 bg-dark-850'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <HelpCircle className="w-4 h-4 text-violet-400" />
          <span>Root-Cause Hypotheses ({hypotheses.length})</span>
        </button>
      </div>

      {/* Tab Content */}
      <div className="p-4 space-y-3">
        {activeTab === 'facts' ? (
          <div>
            <div className="mb-3 text-[11px] text-slate-400 flex items-center space-x-1.5 font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>100% verified against FalkorDB graph topology and active system telemetry.</span>
            </div>

            <div className="space-y-3">
              {confirmedFacts.map((fact, index) => (
                <div
                  key={fact.id}
                  className="p-3.5 rounded-lg bg-dark-800/90 border border-emerald-500/30 hover:border-emerald-500/60 transition-all"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-2.5">
                      <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-400 mt-0.5">
                        <CheckCircle className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-xs text-white">{fact.title}</span>
                          <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-mono text-[10px]">
                            FACT
                          </span>
                        </div>
                        <p className="text-xs text-slate-300 mt-1 leading-relaxed">{fact.description}</p>
                      </div>
                    </div>
                  </div>

                  {/* Relationship Path */}
                  {fact.evidence_path.length > 0 && (
                    <div className="mt-2.5 pt-2.5 border-t border-dark-700/60 text-[11px] font-mono flex flex-wrap items-center gap-1.5 text-slate-400">
                      <span className="text-slate-500 font-medium">Path:</span>
                      {fact.evidence_path.map((step, idx) => (
                        <div key={idx} className="flex items-center space-x-1 bg-dark-900 px-2 py-0.5 rounded border border-dark-750">
                          <span className="text-blue-300">{step.from_node}</span>
                          <ArrowRight className="w-3 h-3 text-slate-500" />
                          <span className="text-emerald-400">:{step.relationship}</span>
                          <ArrowRight className="w-3 h-3 text-slate-500" />
                          <span className="text-blue-300">{step.to_node}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Toggle Cypher Proof Query */}
                  <div className="mt-2 pt-2 border-t border-dark-700/60">
                    <button
                      onClick={() => toggleQuery(fact.id)}
                      className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
                    >
                      <Code2 className="w-3 h-3" />
                      <span>{expandedQueryId === fact.id ? 'Hide FalkorDB Cypher Proof' : 'Inspect FalkorDB Cypher Proof'}</span>
                      {expandedQueryId === fact.id ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    </button>

                    {expandedQueryId === fact.id && (
                      <div className="mt-2 p-2 rounded bg-dark-950 border border-cyan-900/40 font-mono text-[11px] text-cyan-300 overflow-x-auto">
                        <div className="text-[10px] text-slate-500 mb-1">// OpenCypher Query Evaluated on FalkorDB:</div>
                        <code>{fact.cypher_proof_query}</code>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div>
            <div className="mb-3 text-[11px] text-slate-400 flex items-center space-x-1.5 font-mono">
              <span className="w-2 h-2 rounded-full bg-violet-400"></span>
              <span>Inferred causal candidates ranked by confidence and graph relationship weight.</span>
            </div>

            <div className="space-y-3">
              {hypotheses.map(hyp => (
                <div
                  key={hyp.id}
                  className="p-3.5 rounded-lg bg-dark-800/90 border border-violet-500/30 hover:border-violet-500/60 transition-all"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-2.5">
                      <div className="p-1.5 rounded-md bg-violet-500/10 text-violet-400 mt-0.5">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-xs text-white">{hyp.title}</span>
                          <span className="px-1.5 py-0.2 rounded bg-violet-500/20 text-violet-300 font-mono text-[10px]">
                            CONFIDENCE: {Math.round(hyp.confidence_score * 100)}%
                          </span>
                        </div>
                        <p className="text-xs text-slate-300 mt-1 leading-relaxed">{hyp.description}</p>
                      </div>
                    </div>
                  </div>

                  {/* Multi-hop Evidence Steps */}
                  {hyp.evidence_path.length > 0 && (
                    <div className="mt-3 p-2.5 rounded bg-dark-900 border border-dark-750 space-y-1.5">
                      <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                        Causal Propagation Cascade:
                      </div>
                      {hyp.evidence_path.map((step, idx) => (
                        <div key={idx} className="text-xs flex items-center justify-between text-slate-300 py-0.5">
                          <div className="flex items-center space-x-1.5 font-mono text-[11px]">
                            <span className="text-blue-400">{step.from_node}</span>
                            <ArrowRight className="w-3 h-3 text-slate-500" />
                            <span className="text-amber-400">:{step.relationship}</span>
                            <ArrowRight className="w-3 h-3 text-slate-500" />
                            <span className="text-blue-400">{step.to_node}</span>
                          </div>
                          <span className="text-slate-400 text-[11px] italic">{step.explanation}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Highlight on Graph Button */}
                  <div className="mt-2.5 flex items-center justify-between pt-2 border-t border-dark-700/60">
                    <button
                      onClick={() => toggleQuery(hyp.id)}
                      className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
                    >
                      <Code2 className="w-3 h-3" />
                      <span>{expandedQueryId === hyp.id ? 'Hide Cypher Proof' : 'Inspect Cypher Proof'}</span>
                    </button>

                    {onHighlightPath && hyp.evidence_path.length > 0 && (
                      <button
                        onClick={() => {
                          const nodes = [hyp.evidence_path[0].from_node, ...hyp.evidence_path.map(s => s.to_node)];
                          onHighlightPath(nodes);
                        }}
                        className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 border border-blue-500/30"
                      >
                        Highlight Path on Graph
                      </button>
                    )}
                  </div>

                  {expandedQueryId === hyp.id && (
                    <div className="mt-2 p-2 rounded bg-dark-950 border border-cyan-900/40 font-mono text-[11px] text-cyan-300 overflow-x-auto">
                      <code>{hyp.cypher_proof_query}</code>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
