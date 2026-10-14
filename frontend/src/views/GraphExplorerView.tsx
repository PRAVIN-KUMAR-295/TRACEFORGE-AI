import React from 'react';
import { Compass, Database, RefreshCw, ZoomIn } from 'lucide-react';
import { GraphEdge, GraphNode } from '../types';
import { GraphVisualizer } from '../components/GraphVisualizer';
import { CypherQueryConsole } from '../components/CypherQueryConsole';

interface GraphExplorerViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onRefreshTopology: () => void;
  isRefreshing?: boolean;
}

export const GraphExplorerView: React.FC<GraphExplorerViewProps> = ({
  nodes,
  edges,
  onRefreshTopology,
  isRefreshing
}) => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-dark-700">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-cyan-400 mb-1">
            <Compass className="w-4 h-4 text-cyan-400" />
            <span>FalkorDB Graph Explorer</span>
          </div>
          <h1 className="text-xl font-bold text-white">Interactive Enterprise Graph Topology</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Explore services, databases, queues, deployments, and error relationships powering TRACEFORGE AI.
          </p>
        </div>

        <button
          onClick={onRefreshTopology}
          disabled={isRefreshing}
          className="px-3.5 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 border border-dark-700 text-xs font-mono text-slate-300 hover:text-white flex items-center space-x-2 transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>Refresh Graph</span>
        </button>
      </div>

      {/* Main Full-Size Graph Visualizer */}
      <GraphVisualizer
        nodes={nodes}
        edges={edges}
        height="640px"
      />

      {/* Embedded Live Cypher Console */}
      <CypherQueryConsole />
    </div>
  );
};
