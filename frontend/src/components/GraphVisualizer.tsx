import React, { useState, useMemo } from 'react';
import {
  Server,
  Database,
  Layers,
  AlertTriangle,
  GitBranch,
  ShieldAlert,
  CheckCircle2,
  Filter,
  Search,
  Maximize2,
  X
} from 'lucide-react';
import { GraphNode, GraphEdge } from '../types';

interface GraphVisualizerProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightPath?: string[];
  onSelectNode?: (node: GraphNode | null) => void;
  selectedNodeId?: string | null;
  height?: string;
}

const TYPE_CONFIG: Record<string, { color: string; border: string; bg: string; icon: any }> = {
  Service: { color: '#3b82f6', border: 'border-blue-500', bg: 'bg-blue-500/20', icon: Server },
  Incident: { color: '#f43f5e', border: 'border-rose-500', bg: 'bg-rose-500/20', icon: ShieldAlert },
  Database: { color: '#06b6d4', border: 'border-cyan-500', bg: 'bg-cyan-500/20', icon: Database },
  Queue: { color: '#f59e0b', border: 'border-amber-500', bg: 'bg-amber-500/20', icon: Layers },
  Deployment: { color: '#8b5cf6', border: 'border-violet-500', bg: 'bg-violet-500/20', icon: GitBranch },
  ErrorPattern: { color: '#ea580c', border: 'border-orange-500', bg: 'bg-orange-500/20', icon: AlertTriangle },
  MetricAnomaly: { color: '#eab308', border: 'border-yellow-500', bg: 'bg-yellow-500/20', icon: AlertTriangle },
  Resolution: { color: '#10b981', border: 'border-emerald-500', bg: 'bg-emerald-500/20', icon: CheckCircle2 }
};

export const GraphVisualizer: React.FC<GraphVisualizerProps> = ({
  nodes,
  edges,
  highlightPath = [],
  onSelectNode,
  selectedNodeId,
  height = '620px'
}) => {
  const [activeFilters, setActiveFilters] = useState<Record<string, boolean>>({
    Service: true,
    Incident: true,
    Database: true,
    Deployment: true,
    ErrorPattern: true,
    MetricAnomaly: true,
    Queue: true,
    Resolution: true
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Position nodes across logical enterprise architectural layers
  const nodePositions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    const width = 1100;
    const heightNum = 560;

    const layers: Record<string, string[]> = {
      layer_edge: ['api-gateway'],
      layer_business: ['checkout-service', 'payment-service', 'order-service', 'inventory-service', 'search-service'],
      layer_core: ['auth-service', 'notification-service'],
      layer_infra: ['redis-auth-cache', 'postgres-order-db', 'postgres-payment-db', 'kafka-cluster', 'elasticsearch-cluster'],
      layer_incidents: ['INC-2026-1042', 'INC-2026-0814', 'INC-2026-0702', 'INC-2026-0519'],
      layer_deployments: ['deploy-auth-v2.4.1', 'deploy-checkout-v1.8.0', 'deploy-search-v3.0.2'],
      layer_errors: ['err-redis-timeout', 'err-auth-503', 'err-circuit-breaker', 'err-payment-token-invalid', 'metric-conn-pool-leak', 'metric-checkout-5xx-surge', 'metric-gateway-latency', 'res-conn-pool-tune', 'res-rollback-auth']
    };

    // Calculate layer X coordinates
    const layerX: Record<string, number> = {
      layer_incidents: 100,
      layer_edge: 240,
      layer_business: 460,
      layer_core: 700,
      layer_infra: 940,
      layer_deployments: 700,
      layer_errors: 460
    };

    // Place categorized nodes
    Object.entries(layers).forEach(([layerKey, nodeIds]) => {
      const x = layerX[layerKey] || 500;
      const count = nodeIds.length;
      nodeIds.forEach((id, idx) => {
        let y = 80 + (idx + 1) * (heightNum / (count + 1));
        if (layerKey === 'layer_deployments') y = 480 + idx * 60;
        if (layerKey === 'layer_errors') y = 380 + idx * 50;
        pos[id] = { x, y };
      });
    });

    // Fallback for any unmapped node
    let extraCount = 0;
    nodes.forEach(n => {
      if (!pos[n.id]) {
        pos[n.id] = { x: 300 + (extraCount % 4) * 180, y: 100 + Math.floor(extraCount / 4) * 80 };
        extraCount++;
      }
    });

    return pos;
  }, [nodes]);

  // Filtered nodes & edges
  const visibleNodes = useMemo(() => {
    return nodes.filter(n => {
      const typeAllowed = activeFilters[n.label] ?? true;
      const matchesSearch = !searchQuery || n.id.toLowerCase().includes(searchQuery.toLowerCase()) || (n.name && n.name.toLowerCase().includes(searchQuery.toLowerCase()));
      return typeAllowed && matchesSearch;
    });
  }, [nodes, activeFilters, searchQuery]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map(n => n.id)), [visibleNodes]);

  const visibleEdges = useMemo(() => {
    return edges.filter(e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target));
  }, [edges, visibleNodeIds]);

  const handleNodeClick = (n: GraphNode) => {
    setSelectedNode(n);
    if (onSelectNode) onSelectNode(n);
  };

  const toggleFilter = (type: string) => {
    setActiveFilters(prev => ({ ...prev, [type]: !prev[type] }));
  };

  const isHighlighted = (nodeId: string) => highlightPath.includes(nodeId);
  const isEdgeHighlighted = (source: string, target: string) => {
    const sIdx = highlightPath.indexOf(source);
    const tIdx = highlightPath.indexOf(target);
    return sIdx !== -1 && tIdx !== -1 && Math.abs(sIdx - tIdx) === 1;
  };

  return (
    <div className="relative rounded-xl border border-dark-700 bg-dark-900 overflow-hidden flex flex-col" style={{ height }}>
      {/* Top Toolbar */}
      <div className="p-3 border-b border-dark-700 bg-dark-850/80 flex flex-wrap items-center justify-between gap-2 z-10">
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1.5 text-xs text-slate-400 font-mono">
            <Filter className="w-3.5 h-3.5 text-blue-400" />
            <span>Filters:</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {Object.keys(TYPE_CONFIG).map(type => {
              const active = activeFilters[type] ?? true;
              return (
                <button
                  key={type}
                  onClick={() => toggleFilter(type)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono transition-all border ${
                    active
                      ? `${TYPE_CONFIG[type].bg} ${TYPE_CONFIG[type].border} text-slate-200`
                      : 'bg-dark-800 border-dark-700 text-slate-500 opacity-60'
                  }`}
                >
                  {type}
                </button>
              );
            })}
          </div>
        </div>

        {/* Search */}
        <div className="flex items-center space-x-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
            <input
              type="text"
              placeholder="Search graph..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1 bg-dark-800 border border-dark-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 w-44 font-mono"
            />
          </div>
          <span className="text-[11px] font-mono text-slate-500">
            {visibleNodes.length} nodes / {visibleEdges.length} edges
          </span>
        </div>
      </div>

      {/* SVG Interactive Canvas */}
      <div className="relative flex-1 overflow-auto graph-grid-bg">
        <svg className="w-full h-full min-w-[1150px] min-h-[620px]">
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="26"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569" />
            </marker>
            <marker
              id="arrow-highlight"
              viewBox="0 0 10 10"
              refX="26"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#3b82f6" />
            </marker>
          </defs>

          {/* Edges */}
          {visibleEdges.map(edge => {
            const srcPos = nodePositions[edge.source];
            const tgtPos = nodePositions[edge.target];
            if (!srcPos || !tgtPos) return null;

            const highlighted = isEdgeHighlighted(edge.source, edge.target);

            // Compute midpoint for edge label
            const midX = (srcPos.x + tgtPos.x) / 2;
            const midY = (srcPos.y + tgtPos.y) / 2;

            return (
              <g key={edge.id} className="cursor-pointer">
                <line
                  x1={srcPos.x}
                  y1={srcPos.y}
                  x2={tgtPos.x}
                  y2={tgtPos.y}
                  stroke={highlighted ? '#3b82f6' : '#334155'}
                  strokeWidth={highlighted ? 2.5 : 1.2}
                  strokeDasharray={edge.type === 'CONNECTS_TO' ? '4 3' : undefined}
                  markerEnd={highlighted ? 'url(#arrow-highlight)' : 'url(#arrow)'}
                  className="transition-colors duration-200"
                />
                <text
                  x={midX}
                  y={midY - 4}
                  textAnchor="middle"
                  className="fill-slate-500 font-mono text-[9px] pointer-events-none select-none bg-dark-900"
                >
                  :{edge.type}
                </text>
              </g>
            );
          })}

          {/* Nodes */}
          {visibleNodes.map(node => {
            const pos = nodePositions[node.id] || { x: 200, y: 200 };
            const cfg = TYPE_CONFIG[node.label] || TYPE_CONFIG.Service;
            const isSelected = selectedNode?.id === node.id || selectedNodeId === node.id;
            const isPathNode = isHighlighted(node.id);
            const isIncident = node.label === 'Incident' && node.status === 'ACTIVE';

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x}, ${pos.y})`}
                onClick={() => handleNodeClick(node)}
                className="cursor-pointer group"
              >
                {/* Active Incident pulse ring */}
                {isIncident && (
                  <circle r="32" className="fill-rose-500/20 animate-ping opacity-75" />
                )}

                {/* Highlight ring */}
                {(isSelected || isPathNode) && (
                  <circle
                    r="28"
                    className="fill-none stroke-blue-400 stroke-2 animate-pulse"
                  />
                )}

                {/* Node Body */}
                <circle
                  r="20"
                  fill="#111827"
                  stroke={cfg.color}
                  strokeWidth={isSelected ? 3 : 2}
                  className="group-hover:filter group-hover:drop-shadow-[0_0_8px_rgba(59,130,246,0.6)] transition-all"
                />

                {/* Node ID label */}
                <text
                  y="34"
                  textAnchor="middle"
                  className="fill-slate-300 font-mono text-[10px] font-medium pointer-events-none select-none drop-shadow"
                >
                  {node.id}
                </text>

                {/* Node type badge */}
                <text
                  y="-26"
                  textAnchor="middle"
                  fill={cfg.color}
                  className="font-mono text-[9px] font-bold pointer-events-none select-none"
                >
                  :{node.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Selected Node Details Drawer */}
        {selectedNode && (
          <div className="absolute top-4 right-4 w-80 bg-dark-850/95 border border-dark-700 rounded-xl shadow-2xl p-4 z-20 backdrop-blur">
            <div className="flex items-center justify-between pb-3 border-b border-dark-700">
              <div className="flex items-center space-x-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: (TYPE_CONFIG[selectedNode.label] || TYPE_CONFIG.Service).color }}
                />
                <span className="font-mono font-bold text-sm text-white">{selectedNode.id}</span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-white p-1 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-dark-750">
                <span className="text-slate-400">Node Type:</span>
                <span className="font-mono font-medium text-blue-400">{selectedNode.label}</span>
              </div>

              {selectedNode.status && (
                <div className="flex justify-between py-1 border-b border-dark-750">
                  <span className="text-slate-400">Status:</span>
                  <span
                    className={`font-mono font-semibold uppercase ${
                      selectedNode.status === 'healthy'
                        ? 'text-emerald-400'
                        : selectedNode.status === 'critical'
                        ? 'text-rose-400'
                        : 'text-amber-400'
                    }`}
                  >
                    {selectedNode.status}
                  </span>
                </div>
              )}

              {selectedNode.name && (
                <div className="flex justify-between py-1 border-b border-dark-750">
                  <span className="text-slate-400">Display Name:</span>
                  <span className="text-slate-200">{selectedNode.name}</span>
                </div>
              )}

              {selectedNode.tier && (
                <div className="flex justify-between py-1 border-b border-dark-750">
                  <span className="text-slate-400">Architectural Tier:</span>
                  <span className="font-mono text-slate-300">{selectedNode.tier}</span>
                </div>
              )}

              {selectedNode.owner && (
                <div className="flex justify-between py-1 border-b border-dark-750">
                  <span className="text-slate-400">Team Owner:</span>
                  <span className="font-mono text-slate-300">{selectedNode.owner}</span>
                </div>
              )}

              {selectedNode.description && (
                <div className="pt-1">
                  <span className="text-slate-400 block mb-1">Description:</span>
                  <p className="text-slate-300 bg-dark-900 p-2 rounded border border-dark-750 text-[11px] leading-relaxed">
                    {selectedNode.description}
                  </p>
                </div>
              )}

              {/* Raw Properties Accordion */}
              <div className="pt-2">
                <span className="text-slate-500 text-[10px] uppercase font-mono tracking-wider block mb-1">
                  FalkorDB Properties
                </span>
                <pre className="text-[10px] font-mono bg-dark-900 p-2 rounded border border-dark-750 text-slate-300 overflow-x-auto max-h-36">
                  {JSON.stringify(selectedNode.properties || selectedNode, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom status bar */}
      <div className="px-4 py-2 border-t border-dark-700 bg-dark-850 flex items-center justify-between text-xs text-slate-400 font-mono">
        <div className="flex items-center space-x-4">
          <span>Engine: <strong className="text-cyan-400">FalkorDB OpenCypher</strong></span>
          {highlightPath.length > 0 && (
            <span className="text-blue-400 flex items-center space-x-1">
              <span>Investigation Path:</span>
              <strong className="text-white">{highlightPath.join(' → ')}</strong>
            </span>
          )}
        </div>
        <span className="text-slate-500">Click any node to inspect relationship topology</span>
      </div>
    </div>
  );
};
