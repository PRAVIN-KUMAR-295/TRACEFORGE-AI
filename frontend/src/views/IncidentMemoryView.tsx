import React, { useState, useEffect } from 'react';
import {
  History,
  Search,
  Plus,
  Sparkles,
  CheckCircle2,
  Filter,
  Layers,
  Database,
  ArrowRight,
  X
} from 'lucide-react';
import { fetchHistoricalIncidents, searchMemory, storePostmortem } from '../services/api';

export const IncidentMemoryView: React.FC = () => {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedService, setSelectedService] = useState<string>('all');
  const [showAddModal, setShowAddModal] = useState(false);

  // New postmortem form state
  const [newId, setNewId] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [newService, setNewService] = useState('auth-service');
  const [newRootCause, setNewRootCause] = useState('');
  const [newResolution, setNewResolution] = useState('');
  const [newFix, setNewFix] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const loadIncidents = async () => {
    setIsLoading(true);
    try {
      const data = await fetchHistoricalIncidents();
      setIncidents(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      loadIncidents();
      return;
    }
    setIsLoading(true);
    try {
      const res = await searchMemory(searchQuery, selectedService === 'all' ? undefined : selectedService);
      setIncidents(res.matches || []);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSavePostmortem = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await storePostmortem({
        incident_id: newId || `INC-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`,
        title: newTitle,
        affected_service: newService,
        root_cause_summary: newRootCause,
        resolution_strategy: newResolution,
        transferrable_fix: newFix,
        impacted_services: [newService]
      });
      setShowAddModal(false);
      setNewTitle('');
      setNewRootCause('');
      setNewResolution('');
      setNewFix('');
      loadIncidents();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-dark-700">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-cyan-400 mb-1">
            <History className="w-4 h-4 text-cyan-400" />
            <span>FalkorDB Cross-Session Memory</span>
          </div>
          <h1 className="text-xl font-bold text-white">Persistent Incident Memory & Postmortems</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Retain operational knowledge across incidents to accelerate root-cause identification and automate proven resolution transfer.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-semibold flex items-center space-x-1.5 shadow-md shadow-blue-600/25 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Record Resolved Postmortem</span>
        </button>
      </div>

      {/* Search & Filter Toolbar */}
      <form onSubmit={handleSearch} className="p-4 rounded-xl bg-dark-850 border border-dark-700 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search incident symptoms, error signatures, or resolution keywords..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-dark-900 border border-dark-700 rounded-lg text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <select
            value={selectedService}
            onChange={e => setSelectedService(e.target.value)}
            className="bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Services</option>
            <option value="auth-service">auth-service</option>
            <option value="checkout-service">checkout-service</option>
            <option value="order-service">order-service</option>
            <option value="search-service">search-service</option>
            <option value="payment-service">payment-service</option>
          </select>
        </div>

        <button
          type="submit"
          className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-semibold transition-all shadow"
        >
          Search Memory
        </button>
      </form>

      {/* Incidents Grid */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="p-8 text-center text-xs font-mono text-slate-500">
            Querying FalkorDB incident memory...
          </div>
        ) : incidents.length === 0 ? (
          <div className="p-8 text-center text-xs font-mono text-slate-500">
            No incident memories found matching your search.
          </div>
        ) : (
          incidents.map((inc, i) => (
            <div
              key={inc.id || i}
              className="p-5 rounded-xl bg-dark-850 border border-dark-700 hover:border-cyan-500/40 transition-all space-y-3 shadow-lg"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-cyan-400">{inc.id}</span>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono font-bold">
                      RESOLVED
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 bg-dark-900 px-2 py-0.5 rounded border border-dark-750">
                      Service: <strong className="text-white">{inc.affected_service}</strong>
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-white mt-1.5">{inc.title}</h3>
                </div>

                <div className="flex items-center space-x-2 text-xs font-mono text-slate-500">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Indexed in FalkorDB</span>
                </div>
              </div>

              {/* Details grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-dark-900 border border-dark-750">
                  <span className="text-slate-400 font-mono text-[10px] uppercase font-bold block mb-1">
                    Diagnosed Root Cause:
                  </span>
                  <p className="text-slate-300 text-[11px] leading-relaxed">{inc.root_cause_summary}</p>
                </div>

                <div className="p-3 rounded-lg bg-dark-900 border border-dark-750">
                  <span className="text-emerald-400 font-mono text-[10px] uppercase font-bold block mb-1">
                    Validated Resolution:
                  </span>
                  <p className="text-slate-300 text-[11px] leading-relaxed">{inc.resolution_strategy}</p>
                </div>
              </div>

              {inc.transferrable_fix && (
                <div className="p-2.5 rounded-lg bg-blue-950/20 border border-blue-500/20 text-xs flex items-center justify-between">
                  <div className="flex items-center space-x-2 font-mono text-[11px]">
                    <span className="text-slate-400">Transferrable Fix:</span>
                    <span className="text-emerald-400 font-bold">{inc.transferrable_fix}</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    Status: Verified In Production
                  </span>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Modal: Record Resolved Postmortem */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-dark-850 border border-dark-700 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-dark-700">
              <div className="flex items-center space-x-2">
                <History className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">Record Incident into FalkorDB Memory</h3>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSavePostmortem} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Incident Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Redis Connection Pool Starvation in Auth Service"
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg p-2.5 text-white font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Affected Service</label>
                <select
                  value={newService}
                  onChange={e => setNewService(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg p-2.5 text-white font-mono focus:outline-none focus:border-cyan-500"
                >
                  <option value="auth-service">auth-service</option>
                  <option value="checkout-service">checkout-service</option>
                  <option value="payment-service">payment-service</option>
                  <option value="order-service">order-service</option>
                  <option value="search-service">search-service</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Root Cause Summary</label>
                <textarea
                  required
                  rows={2}
                  placeholder="What was the underlying root cause identified in the graph?"
                  value={newRootCause}
                  onChange={e => setNewRootCause(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg p-2.5 text-white font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Resolution Strategy</label>
                <textarea
                  required
                  rows={2}
                  placeholder="What operational action cured the outage?"
                  value={newResolution}
                  onChange={e => setNewResolution(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg p-2.5 text-white font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Transferrable Fix (Action Rule)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CONFIG_UPDATE: pool_max_size=2000"
                  value={newFix}
                  onChange={e => setNewFix(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg p-2.5 text-white font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="pt-3 flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-lg bg-dark-800 text-slate-400 hover:text-white font-mono text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-xs font-semibold shadow-md shadow-cyan-600/25"
                >
                  {isSaving ? 'Indexing in FalkorDB...' : 'Commit to Graph Memory'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
