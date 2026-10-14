import React from 'react';
import {
  Activity,
  Compass,
  Database,
  History,
  Play,
  Terminal,
  ShieldAlert,
  Server
} from 'lucide-react';
import { SystemHealthStatus } from '../types';

interface NavbarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  onRunDemo: () => void;
  isDemoLoading: boolean;
  health: SystemHealthStatus | null;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onSelectTab,
  onRunDemo,
  isDemoLoading,
  health
}) => {
  const isFalkorLive = health?.falkordb?.is_live_connected;
  const engineName = health?.falkordb?.engine_mode || 'FalkorDB In-Memory';

  return (
    <header className="border-b border-dark-700 bg-dark-850/90 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onSelectTab('dashboard')}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-tight text-white font-mono">TRACEFORGE</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 border border-blue-400/30 text-blue-400 font-semibold uppercase">
                AI
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono tracking-wider">GRAPH INCIDENT INVESTIGATOR</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center space-x-1">
          <button
            onClick={() => onSelectTab('dashboard')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2 ${
              currentTab === 'dashboard'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-white hover:bg-dark-750'
            }`}
          >
            <Server className="w-4 h-4" />
            <span>Dashboard</span>
          </button>

          <button
            onClick={() => onSelectTab('investigation')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2 ${
              currentTab === 'investigation'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-white hover:bg-dark-750'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>Investigation</span>
          </button>

          <button
            onClick={() => onSelectTab('graph')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2 ${
              currentTab === 'graph'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-white hover:bg-dark-750'
            }`}
          >
            <Compass className="w-4 h-4" />
            <span>Graph Explorer</span>
          </button>

          <button
            onClick={() => onSelectTab('memory')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2 ${
              currentTab === 'memory'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-white hover:bg-dark-750'
            }`}
          >
            <History className="w-4 h-4" />
            <span>Incident Memory</span>
          </button>

          <button
            onClick={() => onSelectTab('cypher')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2 ${
              currentTab === 'cypher'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-white hover:bg-dark-750'
            }`}
          >
            <Terminal className="w-4 h-4" />
            <span>Cypher Console</span>
          </button>
        </nav>

        {/* Right side controls */}
        <div className="flex items-center space-x-3">
          {/* FalkorDB Badge */}
          <div className="hidden lg:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-dark-750 border border-dark-700 text-xs text-slate-300">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-mono text-[11px]">{engineName.includes('Live') ? 'FalkorDB Live' : 'FalkorDB Engine'}</span>
            <span className={`w-2 h-2 rounded-full ${isFalkorLive ? 'bg-emerald-400 animate-pulse' : 'bg-cyan-400'}`}></span>
          </div>

          {/* One-Click Demo CTA */}
          <button
            onClick={onRunDemo}
            disabled={isDemoLoading}
            className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-xs transition-all shadow-md shadow-blue-600/30 flex items-center space-x-2 active:scale-95 disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${isDemoLoading ? 'animate-spin' : ''}`} />
            <span>{isDemoLoading ? 'Investigating...' : '1-Click Demo'}</span>
          </button>
        </div>
      </div>
    </header>
  );
};
