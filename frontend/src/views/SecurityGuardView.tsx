import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Filter,
  Eye,
  Lock,
  Search,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { SecurityEventItem } from '../types';
import { api } from '../api/client';
import { EmptyState } from '../components/EmptyState';

export const SecurityGuardView: React.FC = () => {
  const [events, setEvents] = useState<SecurityEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<SecurityEventItem | null>(null);
  const [actionFilter, setActionFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const loadEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getSecurityEvents(100);
      setEvents(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch security events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const filteredEvents = events.filter((ev) => {
    const matchesAction = actionFilter === 'ALL' || ev.action_taken === actionFilter;
    const matchesSearch =
      searchQuery === '' ||
      ev.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ev.detector_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (ev.trace_id && ev.trace_id.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesAction && matchesSearch;
  });

  const getSeverityBadge = (severity: string) => {
    const s = severity.toUpperCase();
    if (s === 'CRITICAL') return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
    if (s === 'HIGH') return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    if (s === 'MEDIUM') return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
  };

  const getActionBadge = (action: string) => {
    const a = action.toUpperCase();
    if (a === 'BLOCKED') return 'bg-rose-900/40 text-rose-300 border-rose-800';
    if (a === 'REDACTED') return 'bg-purple-900/40 text-purple-300 border-purple-800';
    if (a === 'FLAG') return 'bg-amber-900/40 text-amber-300 border-amber-800';
    return 'bg-emerald-900/40 text-emerald-300 border-emerald-800';
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-rose-500" />
            AI Security Firewall & Audit Log
          </h1>
          <p className="text-sm text-gray-400">
            Real-time record of all intercepted prompt injections, jailbreaks, PII exposures, and unauthorized tool calls.
          </p>
        </div>
        <button
          onClick={loadEvents}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs font-medium text-gray-300 hover:text-white hover:border-gray-700 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          Refresh Audit Log
        </button>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-gray-900/80 border border-gray-800 p-3 rounded-xl">
        <div className="flex items-center gap-2 w-full sm:w-72 relative">
          <Search className="w-4 h-4 text-gray-500 absolute left-3" />
          <input
            type="text"
            placeholder="Search events, detectors, trace IDs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-gray-500" />
          <div className="flex bg-gray-950 border border-gray-800 rounded-lg p-0.5 text-xs">
            {['ALL', 'BLOCKED', 'REDACTED', 'FLAG'].map((act) => (
              <button
                key={act}
                onClick={() => setActionFilter(act)}
                className={`px-3 py-1 rounded-md font-medium transition-colors ${
                  actionFilter === act ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {act}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Events Table / Content */}
      {loading && events.length === 0 ? (
        <div className="flex items-center justify-center p-12 text-gray-500">
          <RefreshCw className="w-5 h-5 animate-spin mr-2 text-blue-500" />
          Loading audit records...
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800 text-rose-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Error loading security events: {error}</span>
        </div>
      ) : filteredEvents.length === 0 ? (
        <EmptyState
          title={events.length === 0 ? "No Security Incidents Detected" : "No Matching Security Incidents"}
          description={
            events.length === 0
              ? "All inbound prompts and agent outputs have passed safety policies cleanly. When an attack is blocked or flagged, it will be permanently recorded here."
              : "No security events match the current filter or search criteria."
          }
          icon={<ShieldCheck className="w-8 h-8 text-emerald-400" />}
        />
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-950 text-gray-400 uppercase tracking-wider text-[10px] border-b border-gray-800">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Threat Category</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Detector & Method</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 font-mono text-gray-300">
                {filteredEvents.map((ev) => (
                  <tr key={ev.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="py-3 px-4 text-gray-400 font-sans">
                      {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="py-3 px-4 font-semibold text-white">
                      {ev.event_type}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${getSeverityBadge(ev.severity)}`}>
                        {ev.severity}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-sans text-gray-300">
                      <div>{ev.detector_name}</div>
                      <div className="text-[10px] text-gray-500 font-mono">{ev.detection_method}</div>
                    </td>
                    <td className="py-3 px-4">
                      {(ev.confidence_score * 100).toFixed(0)}%
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${getActionBadge(ev.action_taken)}`}>
                        {ev.action_taken}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-sans">
                      <button
                        onClick={() => setSelectedEvent(ev)}
                        className="p-1 rounded hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
                        title="View Incident Diagnostics"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-800 rounded-xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <Lock className="w-5 h-5 text-rose-400" />
                <h3 className="text-base font-semibold text-white">Incident Diagnostics</h3>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-gray-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2 bg-gray-950 p-3 rounded-lg border border-gray-800">
                <div>
                  <span className="text-gray-500 block">Incident ID</span>
                  <span className="font-mono text-gray-300">{selectedEvent.id}</span>
                </div>
                <div>
                  <span className="text-gray-500 block">Trace ID</span>
                  <span className="font-mono text-gray-300">{selectedEvent.trace_id || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-gray-500 block">Threat Category</span>
                  <span className="font-semibold text-rose-400">{selectedEvent.event_type}</span>
                </div>
                <div>
                  <span className="text-gray-500 block">Enforced Action</span>
                  <span className="font-semibold text-white">{selectedEvent.action_taken}</span>
                </div>
              </div>

              <div>
                <span className="text-gray-400 font-semibold mb-1 block">Sanitized Evidence / Diagnostic Payload</span>
                <pre className="p-3 bg-gray-950 border border-gray-800 rounded-lg text-gray-300 overflow-x-auto text-[11px] max-h-48">
                  {JSON.stringify(selectedEvent.details, null, 2) || '// No diagnostic parameters'}
                </pre>
                <p className="text-[10px] text-gray-500 mt-1">
                  * Sensitive data like credentials, PANs, and emails are pre-redacted before database persistence.
                </p>
              </div>
            </div>

            <div className="pt-3 border-t border-gray-800 flex justify-end">
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-xs font-medium transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

