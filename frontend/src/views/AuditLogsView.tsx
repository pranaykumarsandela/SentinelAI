import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  RefreshCw,
  Download,
  Filter,
  ShieldAlert,
  CheckSquare,
  Activity,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
} from 'lucide-react';
import { AuditLogEntry } from '../types';
import { api } from '../api/client';
import { EmptyState } from '../components/EmptyState';

export const AuditLogsView: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntry, setSelectedEntry] = useState<AuditLogEntry | null>(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getAuditLogs(
        categoryFilter !== 'ALL' ? categoryFilter : undefined,
        page,
        pageSize
      );
      if (res && res.items) {
        setLogs(res.items);
        setTotal(res.total);
      } else {
        setLogs([]);
        setTotal(0);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch audit records.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [page, categoryFilter]);

  const handleExportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(logs, null, 2));
    const dl = document.createElement('a');
    dl.setAttribute('href', dataStr);
    dl.setAttribute('download', `sentinel-audit-trail-${new Date().toISOString().slice(0, 10)}.json`);
    dl.click();
    dl.remove();
  };

  const getCategoryBadge = (cat: string) => {
    if (cat === 'SECURITY') return 'bg-rose-500/15 text-rose-400 border border-rose-500/30';
    if (cat === 'APPROVAL') return 'bg-amber-500/15 text-amber-400 border border-amber-500/30';
    return 'bg-blue-500/15 text-blue-400 border border-blue-500/30';
  };

  const getSeverityBadge = (sev: string) => {
    const s = sev?.toUpperCase() || 'LOW';
    if (s === 'CRITICAL') return 'text-rose-400 font-bold';
    if (s === 'HIGH') return 'text-orange-400 font-semibold';
    if (s === 'MEDIUM') return 'text-amber-400';
    return 'text-gray-400';
  };

  const filteredLogs = logs.filter((l) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      l.event_type.toLowerCase().includes(q) ||
      l.actor.toLowerCase().includes(q) ||
      l.description.toLowerCase().includes(q) ||
      l.id.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-400" />
            Consolidated Compliance Audit Logs
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Immutable, cross-subsystem event trail aggregating security threat events, human approval reviews, and agent executions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {logs.length > 0 && (
            <button
              onClick={handleExportJSON}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 border border-gray-800 hover:border-gray-700 text-xs text-gray-200 rounded-lg transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Export Audit Trail
            </button>
          )}

          <button
            onClick={fetchLogs}
            disabled={loading}
            className="p-1.5 bg-gray-900 border border-gray-800 text-gray-400 hover:text-white rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-gray-900/80 border border-gray-800 p-3 rounded-xl text-xs">
        <div className="flex items-center gap-2 w-full sm:w-80 relative">
          <Search className="w-4 h-4 text-gray-500 absolute left-3" />
          <input
            type="text"
            placeholder="Search actor, event type, or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-gray-400 text-[11px]">Subsystem:</span>
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
            className="bg-gray-950 border border-gray-800 text-gray-300 rounded px-2.5 py-1.5 text-xs font-mono"
          >
            <option value="ALL">All Subsystems</option>
            <option value="SECURITY">Security Firewalls</option>
            <option value="APPROVAL">HITL Approvals</option>
            <option value="EXECUTION">Agent Executions</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center h-48 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-blue-500" />
          Loading audit trail from database...
        </div>
      ) : filteredLogs.length === 0 ? (
        <EmptyState
          title="No Audit Records Found"
          description="The audit log is empty or no records match your filter criteria. All platform operations are automatically persisted here."
          icon={<FileText className="w-8 h-8 text-blue-400" />}
        />
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-950/70 text-gray-400 uppercase text-[10px] font-semibold border-b border-gray-800">
                <tr>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Subsystem</th>
                  <th className="py-2.5 px-3">Event Type</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Actor / Agent</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Summary Description</th>
                  <th className="py-2.5 px-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 font-mono">
                {filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="py-2 px-3 text-gray-400 text-[11px] whitespace-nowrap">
                      {log.timestamp ? new Date(log.timestamp).toLocaleString() : 'N/A'}
                    </td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCategoryBadge(log.category)}`}>
                        {log.category}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-gray-200 font-semibold">{log.event_type}</td>
                    <td className={`py-2 px-3 text-[11px] ${getSeverityBadge(log.severity)}`}>
                      {log.severity}
                    </td>
                    <td className="py-2 px-3 text-gray-300 font-medium truncate max-w-[120px]" title={log.actor}>
                      {log.actor}
                    </td>
                    <td className="py-2 px-3">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-gray-800 text-gray-300">
                        {log.action}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-gray-400 font-sans text-xs max-w-sm truncate" title={log.description}>
                      {log.description}
                    </td>
                    <td className="py-2 px-3 text-right">
                      <button
                        onClick={() => setSelectedEntry(log)}
                        className="px-2 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-[10px] font-medium transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between p-3 border-t border-gray-800 text-xs text-gray-400">
            <span>
              Showing {filteredLogs.length} of {total} audit records
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="p-1 rounded bg-gray-950 border border-gray-800 disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-mono text-gray-300">{page}</span>
              <button
                disabled={page * pageSize >= total}
                onClick={() => setPage(page + 1)}
                className="p-1 rounded bg-gray-950 border border-gray-800 disabled:opacity-40"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Details */}
      {selectedEntry && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-lg w-full space-y-4">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                Audit Record Inspection
              </h2>
              <button onClick={() => setSelectedEntry(null)} className="text-gray-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Record ID:</span>
                <span className="text-gray-200">{selectedEntry.id}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Subsystem:</span>
                <span className="text-blue-400">{selectedEntry.category}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Event Type:</span>
                <span className="text-white font-bold">{selectedEntry.event_type}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Actor:</span>
                <span className="text-gray-300">{selectedEntry.actor}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Action:</span>
                <span className="text-emerald-400 font-semibold">{selectedEntry.action}</span>
              </div>
              <div className="py-2">
                <span className="text-gray-400 block mb-1">Payload & Execution Metadata:</span>
                <pre className="p-3 bg-gray-950 border border-gray-800 rounded text-[11px] text-gray-300 max-h-48 overflow-y-auto whitespace-pre-wrap">
                  {JSON.stringify(selectedEntry.details || {}, null, 2)}
                </pre>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedEntry(null)}
                className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded text-xs font-medium"
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

