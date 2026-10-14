import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { SystemHealthBanner } from './components/SystemHealthBanner';
import { DashboardView } from './views/DashboardView';
import { InvestigationDetailView } from './views/InvestigationDetailView';
import { GraphExplorerView } from './views/GraphExplorerView';
import { IncidentMemoryView } from './views/IncidentMemoryView';
import { CypherQueryConsole } from './components/CypherQueryConsole';
import {
  fetchHealth,
  fetchTopology,
  runOneClickDemo,
  startInvestigation,
  listInvestigations,
  approveRemediationAction
} from './services/api';
import {
  GraphEdge,
  GraphNode,
  InvestigationResult,
  SystemHealthStatus
} from './types';

export function App() {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [health, setHealth] = useState<SystemHealthStatus | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [isDemoLoading, setIsDemoLoading] = useState(false);
  const [isRefreshingGraph, setIsRefreshingGraph] = useState(false);
  const [isProcessingAction, setIsProcessingAction] = useState(false);
  const [activeInvestigation, setActiveInvestigation] = useState<InvestigationResult | null>(null);
  const [recentInvestigations, setRecentInvestigations] = useState<InvestigationResult[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Initialize data on mount
  useEffect(() => {
    loadHealthAndTopology();
    loadInvestigationsList();
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const loadHealthAndTopology = async () => {
    try {
      const [hData, topoData] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchTopology().catch(() => ({ nodes: [], edges: [] }))
      ]);
      if (hData) setHealth(hData);
      if (topoData) {
        setNodes(topoData.nodes || []);
        setEdges(topoData.edges || []);
      }
    } catch (err) {
      console.error('Error loading startup state:', err);
    }
  };

  const loadInvestigationsList = async () => {
    try {
      const invs = await listInvestigations();
      setRecentInvestigations(invs);
    } catch (err) {
      console.error('Failed to load investigations:', err);
    }
  };

  const handleRunDemo = async () => {
    setIsDemoLoading(true);
    try {
      const result = await runOneClickDemo();
      setActiveInvestigation(result);
      setRecentInvestigations(prev => [result, ...prev.filter(x => x.investigation_id !== result.investigation_id)]);
      setCurrentTab('investigation');
      showToast('1-Click Demo Investigation completed successfully!');
    } catch (err: any) {
      showToast(`Demo failed: ${err.message}`);
    } finally {
      setIsDemoLoading(false);
    }
  };

  const handleSelectIncident = async (incidentId: string) => {
    setIsDemoLoading(true);
    try {
      const result = await startInvestigation(incidentId);
      setActiveInvestigation(result);
      setRecentInvestigations(prev => [result, ...prev.filter(x => x.investigation_id !== result.investigation_id)]);
      setCurrentTab('investigation');
      showToast(`Investigation for ${incidentId} completed.`);
    } catch (err: any) {
      showToast(`Investigation failed: ${err.message}`);
    } finally {
      setIsDemoLoading(false);
    }
  };

  const handleApproveAction = async (actionId: string, approved: boolean, notes: string) => {
    if (!activeInvestigation) return;
    setIsProcessingAction(true);
    try {
      const res = await approveRemediationAction(
        activeInvestigation.investigation_id,
        actionId,
        approved,
        'Alex Rivera (Lead SRE)',
        notes
      );

      // Update state in place
      setActiveInvestigation(prev => {
        if (!prev) return null;
        const updatedActions = prev.recommended_actions.map(act => {
          if (act.action_id === actionId) {
            return {
              ...act,
              status: approved ? ('EXECUTED' as const) : ('REJECTED' as const),
              approval_notes: notes || (approved ? 'Approved by Alex Rivera' : 'Rejected by Alex Rivera'),
              executed_at: approved ? new Date().toISOString() : undefined
            };
          }
          return act;
        });
        return {
          ...prev,
          status: approved ? 'MITIGATED' : prev.status,
          recommended_actions: updatedActions
        };
      });

      showToast(
        approved
          ? `Action ${actionId} approved & executed safely.`
          : `Action ${actionId} rejected.`
      );
    } catch (err: any) {
      showToast(`Action failed: ${err.message}`);
    } finally {
      setIsProcessingAction(false);
    }
  };

  const handleRefreshGraph = async () => {
    setIsRefreshingGraph(true);
    try {
      const topo = await fetchTopology();
      setNodes(topo.nodes || []);
      setEdges(topo.edges || []);
      showToast('Graph topology refreshed from FalkorDB.');
    } catch (err: any) {
      showToast(`Refresh error: ${err.message}`);
    } finally {
      setIsRefreshingGraph(false);
    }
  };

  return (
    <div className="min-h-screen bg-dark-900 text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      {/* Navigation */}
      <Navbar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        onRunDemo={handleRunDemo}
        isDemoLoading={isDemoLoading}
        health={health}
      />

      {/* System Health Strip */}
      <SystemHealthBanner health={health} />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-xl bg-blue-600/90 text-white font-mono text-xs shadow-2xl backdrop-blur border border-blue-400/40 flex items-center space-x-2 animate-bounce">
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {currentTab === 'dashboard' && (
          <DashboardView
            onRunDemo={handleRunDemo}
            isDemoLoading={isDemoLoading}
            onSelectIncident={handleSelectIncident}
            recentInvestigations={recentInvestigations}
            onOpenInvestigation={inv => {
              setActiveInvestigation(inv);
              setCurrentTab('investigation');
            }}
            onNavigateTab={setCurrentTab}
          />
        )}

        {currentTab === 'investigation' && activeInvestigation && (
          <InvestigationDetailView
            investigation={activeInvestigation}
            nodes={nodes}
            edges={edges}
            onBack={() => setCurrentTab('dashboard')}
            onApproveAction={handleApproveAction}
            isProcessingAction={isProcessingAction}
          />
        )}

        {currentTab === 'investigation' && !activeInvestigation && (
          <div className="rounded-2xl border border-dark-700 bg-dark-850 p-12 text-center space-y-4">
            <h2 className="text-lg font-bold text-white font-mono">No Active Investigation Selected</h2>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              Launch an automated investigation from the dashboard or click the 1-Click Demo button to evaluate FalkorDB graph relationships.
            </p>
            <button
              onClick={handleRunDemo}
              disabled={isDemoLoading}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-semibold shadow-lg shadow-blue-600/30 inline-flex items-center space-x-2"
            >
              <span>{isDemoLoading ? 'Running Demo...' : 'Launch 1-Click Demo Investigation'}</span>
            </button>
          </div>
        )}

        {currentTab === 'graph' && (
          <GraphExplorerView
            nodes={nodes}
            edges={edges}
            onRefreshTopology={handleRefreshGraph}
            isRefreshing={isRefreshingGraph}
          />
        )}

        {currentTab === 'memory' && <IncidentMemoryView />}

        {currentTab === 'cypher' && (
          <div className="space-y-4">
            <CypherQueryConsole
              executedLogs={activeInvestigation?.cypher_queries_executed || []}
            />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-dark-750 bg-dark-850 py-4 text-center text-xs font-mono text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-wrap items-center justify-between gap-2">
          <span>TRACEFORGE AI • Graph Hacks 2026 Submission</span>
          <span className="text-cyan-400">Powered by FalkorDB Graph Engine & Context for AI Agents</span>
          <span>Deterministic Demo Mode Enabled</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
