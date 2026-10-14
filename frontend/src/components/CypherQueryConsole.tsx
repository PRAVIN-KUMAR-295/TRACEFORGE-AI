import React, { useState } from 'react';
import { Terminal, Play, Clock, Database, Check, AlertCircle } from 'lucide-react';
import { executeCypherQuery } from '../services/api';
import { CypherQueryLog } from '../types';

interface CypherQueryConsoleProps {
  executedLogs?: CypherQueryLog[];
}

const TEMPLATE_QUERIES = [
  {
    name: 'Find All Services & Tiers',
    query: 'MATCH (s:Service) RETURN s.id, s.name, s.tier, s.status'
  },
  {
    name: 'Traverse Service Dependencies',
    query: 'MATCH (s:Service)-[r:DEPENDS_ON]->(dep:Service) RETURN s.id, r.type, dep.id'
  },
  {
    name: 'Find Critical Auth Cascades',
    query: 'MATCH (s:Service)-[:DEPENDS_ON]->(a:Service {id: "auth-service"}) RETURN s.id, s.name'
  },
  {
    name: 'Inspect Connected Databases',
    query: 'MATCH (s:Service)-[r:CONNECTS_TO]->(db:Database) RETURN s.id, db.id, db.status'
  },
  {
    name: 'Inspect Recent Deployments',
    query: 'MATCH (d:Deployment)-[r:DEPLOYED_TO]->(s:Service) RETURN d.id, d.version, s.id'
  }
];

export const CypherQueryConsole: React.FC<CypherQueryConsoleProps> = ({ executedLogs = [] }) => {
  const [activeTab, setActiveTab] = useState<'console' | 'logs'>('console');
  const [queryInput, setQueryInput] = useState(
    'MATCH (s:Service)-[r:DEPENDS_ON]->(dep:Service) RETURN s.id, dep.id'
  );
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRunQuery = async (queryToRun?: string) => {
    const q = queryToRun || queryInput;
    setIsLoading(true);
    setError(null);
    try {
      const res = await executeCypherQuery(q);
      setResults(res);
    } catch (err: any) {
      setError(err.message || 'Error executing Cypher query');
      setResults(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-dark-850 rounded-xl border border-dark-700 overflow-hidden shadow-xl flex flex-col">
      {/* Header */}
      <div className="p-4 bg-gradient-to-r from-slate-900 via-dark-800 to-cyan-950/40 border-b border-dark-700 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-cyan-400 mb-1">
            <Terminal className="w-4 h-4 text-cyan-400" />
            <span>FalkorDB OpenCypher Query Console</span>
          </div>
          <h2 className="text-base font-bold text-white mb-0.5">Live Graph Query Engine</h2>
          <p className="text-xs text-slate-400">
            Execute native OpenCypher queries directly against FalkorDB.
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex bg-dark-900 p-1 rounded-lg border border-dark-750 text-xs font-mono">
          <button
            onClick={() => setActiveTab('console')}
            className={`px-3 py-1 rounded-md transition-all ${
              activeTab === 'console'
                ? 'bg-blue-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Interactive Console
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`px-3 py-1 rounded-md transition-all flex items-center space-x-1.5 ${
              activeTab === 'logs'
                ? 'bg-blue-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <span>Investigation Trace Logs</span>
            {executedLogs.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-blue-500/30 text-[10px]">
                {executedLogs.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {activeTab === 'console' ? (
        <div className="p-4 space-y-4">
          {/* Preset Templates */}
          <div>
            <span className="text-[11px] font-mono text-slate-400 block mb-1.5">Preset OpenCypher Queries:</span>
            <div className="flex flex-wrap gap-1.5">
              {TEMPLATE_QUERIES.map((tpl, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setQueryInput(tpl.query);
                    handleRunQuery(tpl.query);
                  }}
                  className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-750 border border-dark-700 text-xs font-mono text-cyan-300 transition-all hover:border-cyan-500/50"
                >
                  {tpl.name}
                </button>
              ))}
            </div>
          </div>

          {/* Editor & Execute */}
          <div className="space-y-2">
            <div className="relative">
              <textarea
                value={queryInput}
                onChange={e => setQueryInput(e.target.value)}
                rows={3}
                className="w-full bg-dark-900 border border-dark-700 rounded-xl p-3 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30 shadow-inner"
                placeholder="Enter OpenCypher query e.g. MATCH (n) RETURN n..."
              />
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-slate-500">
                Press Run to evaluate query on FalkorDB
              </span>

              <button
                onClick={() => handleRunQuery()}
                disabled={isLoading}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-mono font-semibold transition-all shadow-md shadow-cyan-600/20 flex items-center space-x-2 disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>{isLoading ? 'Executing Cypher...' : 'Run OpenCypher'}</span>
              </button>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-500/40 text-xs text-rose-300 font-mono flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Results Grid */}
          {results && (
            <div className="border border-dark-700 rounded-xl overflow-hidden bg-dark-900">
              <div className="px-3 py-2 bg-dark-800/80 border-b border-dark-700 flex items-center justify-between text-xs font-mono">
                <span className="text-slate-300">
                  Returned <strong className="text-cyan-400">{results.row_count}</strong> rows
                </span>
                <div className="flex items-center space-x-4 text-slate-400">
                  <span className="flex items-center space-x-1">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    <span>{results.execution_time_ms}ms</span>
                  </span>
                  <span className="text-blue-400 font-semibold">{results.engine}</span>
                </div>
              </div>

              <div className="overflow-x-auto max-h-72">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-dark-800 text-slate-400 uppercase text-[10px] tracking-wider sticky top-0">
                    <tr>
                      {results.columns.map((col: string, i: number) => (
                        <th key={i} className="px-3 py-2 border-b border-dark-700 font-semibold">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-dark-750 text-slate-300">
                    {results.results.length === 0 ? (
                      <tr>
                        <td colSpan={results.columns.length || 1} className="px-3 py-4 text-center text-slate-500">
                          Empty result set.
                        </td>
                      </tr>
                    ) : (
                      results.results.map((row: any, i: number) => (
                        <tr key={i} className="hover:bg-dark-800/50 transition-colors">
                          {results.columns.map((col: string, j: number) => (
                            <td key={j} className="px-3 py-2 text-slate-300 max-w-xs truncate">
                              {typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col] ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-4 space-y-3">
          <div className="text-xs text-slate-400 font-mono mb-2">
            Every Cypher query issued during the automated investigation pipeline:
          </div>

          {executedLogs.length === 0 ? (
            <div className="p-6 text-center text-slate-500 text-xs font-mono">
              Run an investigation to record FalkorDB Cypher execution traces.
            </div>
          ) : (
            executedLogs.map((log, index) => (
              <div key={index} className="p-3 rounded-lg bg-dark-900 border border-dark-750 space-y-1.5 font-mono">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[10px] font-bold">
                      STEP {index + 1}
                    </span>
                    <span className="text-slate-300 font-medium">{log.purpose}</span>
                  </div>
                  <div className="flex items-center space-x-3 text-[11px] text-slate-400">
                    <span className="text-cyan-400">{log.execution_time_ms}ms</span>
                    <span className="text-slate-500">({log.rows_returned} rows)</span>
                  </div>
                </div>

                <div className="p-2 rounded bg-dark-950 border border-dark-800 text-cyan-300 text-[11px] overflow-x-auto">
                  <code>{log.cypher}</code>
                </div>

                {Object.keys(log.params || {}).length > 0 && (
                  <div className="text-[10px] text-slate-500">
                    Params: {JSON.stringify(log.params)}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
