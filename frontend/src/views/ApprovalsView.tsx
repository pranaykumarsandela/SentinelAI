import React, { useState, useEffect } from 'react';
import {
  CheckSquare,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  UserCheck,
  Shield,
} from 'lucide-react';
import { ApprovalRequestItem } from '../types';
import { api } from '../api/client';
import { EmptyState } from '../components/EmptyState';

export const ApprovalsView: React.FC = () => {
  const [approvals, setApprovals] = useState<ApprovalRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [rejectionNotes, setRejectionNotes] = useState<Record<string, string>>({});
  const [rejectingId, setRejectingId] = useState<string | null>(null);

  const loadApprovals = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getPendingApprovals();
      setApprovals(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch approval requests');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApprovals();
  }, []);

  const handleReview = async (id: string, action: 'APPROVE' | 'REJECT') => {
    try {
      setActionInProgress(id);
      const notes = rejectionNotes[id];
      await api.reviewApproval(id, action, 'supervisor-admin', notes);
      // Remove from pending list
      setApprovals((prev) => prev.filter((a) => a.id !== id));
      setRejectingId(null);
    } catch (err: any) {
      alert(`Approval review failed: ${err.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <CheckSquare className="w-5 h-5 text-amber-500" />
            Human-In-The-Loop (HITL) Authorization Queue
          </h1>
          <p className="text-sm text-gray-400">
            Critical external tool actions and mutations require explicit supervisor authorization before backend execution.
          </p>
        </div>
        <button
          onClick={loadApprovals}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs font-medium text-gray-300 hover:text-white hover:border-gray-700 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          Refresh Queue
        </button>
      </div>

      {loading && approvals.length === 0 ? (
        <div className="flex items-center justify-center p-12 text-gray-500">
          <RefreshCw className="w-5 h-5 animate-spin mr-2 text-blue-500" />
          Checking pending approval queue...
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800 text-rose-400 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          <span>Error loading approvals: {error}</span>
        </div>
      ) : approvals.length === 0 ? (
        <EmptyState
          title="Approval Queue Clean (0 Pending Actions)"
          description="There are currently no privileged agent operations awaiting human review. Sensitive operations (like financial refunds or database admin commands) are automatically routed here."
          icon={<UserCheck className="w-8 h-8 text-emerald-400" />}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {approvals.map((req) => (
            <div
              key={req.id}
              className="bg-gray-900 border border-amber-900/40 rounded-xl p-5 shadow-sm space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gray-800 pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-lg">
                    <Shield className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-white flex items-center gap-2">
                      <span>Tool: {req.tool_name}</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-900/40 text-amber-300 border border-amber-800">
                        RISK: {req.risk_level}
                      </span>
                    </h3>
                    <span className="text-xs text-gray-500">
                      Request ID: <span className="font-mono text-gray-400">{req.id}</span> • Trace:{' '}
                      <span className="font-mono text-gray-400">{req.trace_id}</span>
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  <Clock className="w-3.5 h-3.5 text-gray-500" />
                  <span>Requested: {new Date(req.requested_at).toLocaleTimeString()}</span>
                </div>
              </div>

              {/* Arguments breakdown */}
              <div>
                <span className="text-xs font-semibold text-gray-300 mb-1.5 block">
                  Proposed Invocation Arguments:
                </span>
                <pre className="p-3 bg-gray-950 border border-gray-800 rounded-lg text-xs font-mono text-emerald-400 overflow-x-auto">
                  {JSON.stringify(req.tool_arguments, null, 2)}
                </pre>
              </div>

              {/* Rejection input prompt if user clicked reject */}
              {rejectingId === req.id && (
                <div className="bg-gray-950 p-3 rounded-lg border border-rose-900/60 space-y-2">
                  <label className="text-xs font-medium text-rose-300 block">
                    Specify Rejection Reason (Required for audit trail):
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Unverified customer claim or excessive refund amount"
                    value={rejectionNotes[req.id] || ''}
                    onChange={(e) =>
                      setRejectionNotes({ ...rejectionNotes, [req.id]: e.target.value })
                    }
                    className="w-full bg-gray-900 border border-gray-800 rounded px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-rose-500"
                  />
                  <div className="flex justify-end gap-2 pt-1">
                    <button
                      onClick={() => setRejectingId(null)}
                      className="px-3 py-1 text-xs text-gray-400 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleReview(req.id, 'REJECT')}
                      disabled={!rejectionNotes[req.id]?.trim() || actionInProgress === req.id}
                      className="px-3 py-1 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white rounded text-xs font-semibold"
                    >
                      Confirm Rejection
                    </button>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              {rejectingId !== req.id && (
                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    onClick={() => setRejectingId(req.id)}
                    disabled={actionInProgress === req.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-800 text-rose-400 hover:bg-rose-950/40 text-xs font-medium transition-colors"
                  >
                    <XCircle className="w-4 h-4" />
                    Reject Action
                  </button>
                  <button
                    onClick={() => handleReview(req.id, 'APPROVE')}
                    disabled={actionInProgress === req.id}
                    className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm transition-colors"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Authorize Execution
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

