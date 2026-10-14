import React from 'react';
import { Database, Cpu, Activity, Clock } from 'lucide-react';
import { SystemHealthStatus } from '../types';

interface SystemHealthBannerProps {
  health: SystemHealthStatus | null;
}

export const SystemHealthBanner: React.FC<SystemHealthBannerProps> = ({ health }) => {
  if (!health) return null;

  return (
    <div className="bg-dark-850/80 border-b border-dark-750 px-4 py-2.5">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between text-xs text-slate-400 gap-y-2">
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-slate-300 font-medium">TraceForge Engine:</span>
            <span className="text-emerald-400 font-mono">ONLINE</span>
          </div>

          <div className="flex items-center space-x-2">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span>Graph Context:</span>
            <span className="text-cyan-300 font-mono">
              {health.falkordb.total_nodes} nodes / {health.falkordb.total_edges} edges
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <Activity className="w-3.5 h-3.5 text-blue-400" />
            <span>Active Engine:</span>
            <span className="text-blue-300 font-mono">{health.falkordb.engine_mode}</span>
          </div>
        </div>

        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2">
            <Cpu className="w-3.5 h-3.5 text-violet-400" />
            <span>Reasoning Provider:</span>
            <span className="text-violet-300 font-mono uppercase font-semibold">
              {health.llm.provider}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-dark-700 text-[10px] text-slate-300 font-mono">
              {health.llm.model}
            </span>
          </div>

          <div className="flex items-center space-x-1.5 text-slate-400">
            <Clock className="w-3.5 h-3.5" />
            <span className="font-mono">{health.uptime_seconds}s uptime</span>
          </div>
        </div>
      </div>
    </div>
  );
};
