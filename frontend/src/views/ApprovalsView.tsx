import React, { useState, useEffect } from 'react';
import {
  CheckSquare,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  UserCheck,
  ShieldAlert,
  History,
  FileCheck,
  ChevronRight,
} from 'lucide-react';
import { ApprovalRequestItem } from '../types';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { EmptyState } from '../components/EmptyState';

export const ApprovalsView: React.FC = () => {
  const { user, hasPermission } = useAuth();
  const [activeTab, setActiveTab] = useState<'pending' | 'history'>('pending');

  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequestItem[]>([]);
  const [allApprovals, setAllApprovals] = useState<ApprovalRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [rejectionNotes, setRejectionNotes] = useState<Record<string, string>>({});
  const [rejectingId, setRejectingId] = useState<string | null>(null);

  const isAuthorizedApprover = hasPermission('supervisor');

  const loadApprovals = async () => {
    try {
      setLoading(true);
      setError(null);
      const [pendingData, allData] = await Promise.all([
        api.getPendingApprovals(50),
        api.getApprovals('ALL', 1, 50).catch(() => ({ items: [], total: 0 })),
      ]);
      setPendingApprovals(pendingData || []);
      setAllApprovals((allData as any).items || (Array.isArray(allData) ? allData : []));
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
    if (!isAuthorizedApprover) {
      alert('Only supervisors and administrators can approve or reject HITL actions.');
      return;
    }
    try {
      setActionInProgress(id);
      const notes = rejectionNotes[id];
      await api.reviewApproval(id, action, user.id, user.role, notes);
      await loadApprovals();
      setRejectingId(null);
    } catch (err: any) {
      alert(`Approval review failed: ${err.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  const getStatusBadge = (status: string) => {
    const s = status.toUpperCase();
    if (s === 'PENDING') return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
    if (s === 'APPROVED') return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
    if (s === 'EXECUTED') return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
    if (s === 'REJECTED') return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
    return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <CheckSquare className="w-5 h-5 text-amber-500" />
            Human Approval Center (HITL)
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Privileged tool mutations require supervisor authorization. Rejected or expired actions can never execute.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-0.5 text-xs flex">
            <button
              onClick={() => setActiveTab('pending')}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
                activeTab === 'pending'
                  ? 'bg-amber-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Pending Actions ({pendingApprovals.length})
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
                activeTab === 'history'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Decision History
            </button>
          </div>

          <button
            onClick={loadApprovals}
            disabled={loading}
            className="p-1.5 rounded-lg bg-gray-900 border border-gray-800 text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          </button>
        </div>
      </div>

      {!isAuthorizedApprover && (
        <div className="p-3 bg-amber-950/30 border border-amber-600/30 rounded-xl text-amber-300/80 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            You are currently signed in with the <strong className="capitalize text-white">{user.role}</strong> role. Authorization buttons are disabled. Switch to <strong>Supervisor</strong> or <strong>Administrator</strong> in the top navigation to review actions.
          </span>
        </div>
      )}

      {loading && pendingApprovals.length === 0 && allApprovals.length === 0 ? (
        <div className="flex items-center justify-center p-12 text-gray-500 text-xs">
          <RefreshCw className="w-5 h-5 animate-spin mr-2 text-blue-500" />
          Checking approval records in database...
        </div>
      ) : activeTab === 'pending' ? (
        // Tab 1: Pending Queue
        pendingApprovals.length === 0 ? (
          <EmptyState
            title="Approval Queue Clean (0 Pending Actions)"
            description="There are currently no privileged agent operations awaiting human review. Sensitive operations (e.g. financial refunds or customer account changes) will automatically route here."
            icon={<UserCheck className="w-8 h-8 text-emerald-400" />}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {pendingApprovals.map((req) => (
              <div
                key={req.id}
                className="bg-gray-900 border border-amber-900/40 rounded-xl p-5 shadow-sm space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gray-800/80 pb-3">
                  <div className="flex items-center gap-3">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />
                    <div>
                      <h3 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
                        Tool: {req.tool_name}
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-400 border border-amber-800">
                          {req.risk_level} RISK
                        </span>
                      </h3>
                      <span className="text-[11px] text-gray-400 font-mono">
                        Approval ID: {req.id} | Trace: {req.trace_id ? `${req.trace_id.slice(0, 8)}...` : 'N/A'}
                      </span>
                    </div>
                  </div>

                  <div className="text-right text-xs font-mono text-gray-400">
                    <div>Requested: {new Date(req.requested_at).toLocaleTimeString()}</div>
                    {req.expires_at && (
                      <div className="text-amber-400/90 text-[11px]">
                        Expires: {new Date(req.expires_at).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                </div>

                {/* Validated Tool Arguments */}
                <div>
                  <span className="text-[11px] font-medium text-gray-400 block mb-1">
                    Validated Tool Parameters (Inspected by Policy Engine):
                  </span>
                  <pre className="p-3 bg-gray-950 border border-gray-800 rounded-lg text-xs font-mono text-gray-200 overflow-x-auto">
                    {JSON.stringify(req.tool_arguments || {}, null, 2)}
                  </pre>
                </div>

                {/* Reject note input */}
                {rejectingId === req.id && (
                  <div className="p-3 bg-rose-950/20 border border-rose-900/40 rounded-lg space-y-2">
                    <label className="block text-xs font-medium text-rose-300">
                      Reason for Rejection (Audit Trail Record):
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Refund exceeds $50.00 customer threshold without verified receipt"
                      value={rejectionNotes[req.id] || ''}
                      onChange={(e) =>
                        setRejectionNotes({ ...rejectionNotes, [req.id]: e.target.value })
                      }
                      className="w-full px-3 py-1.5 bg-gray-950 border border-gray-800 rounded text-xs text-gray-200 focus:outline-none focus:border-rose-500 font-mono"
                    />
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-2 pt-1">
                  {rejectingId === req.id ? (
                    <>
                      <button
                        onClick={() => setRejectingId(null)}
                        className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-xs font-medium"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleReview(req.id, 'REJECT')}
                        disabled={actionInProgress === req.id || !isAuthorizedApprover}
                        className="px-4 py-1.5 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors"
                      >
                        Confirm Rejection
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => setRejectingId(req.id)}
                        disabled={actionInProgress === req.id || !isAuthorizedApprover}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-950/60 hover:bg-rose-900/60 border border-rose-800 text-rose-300 disabled:opacity-50 rounded text-xs font-medium transition-colors"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Reject Action
                      </button>
                      <button
                        onClick={() => handleReview(req.id, 'APPROVE')}
                        disabled={actionInProgress === req.id || !isAuthorizedApprover}
                        className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors shadow-sm"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Authorize & Execute
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        // Tab 2: Decision History
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-gray-800 flex items-center justify-between">
            <span className="text-xs font-semibold text-white flex items-center gap-2">
              <History className="w-4 h-4 text-blue-400" />
              Historical HITL Decision Records ({allApprovals.length})
            </span>
            <span className="text-[11px] text-gray-400 font-mono">Immutable Audit Trail</span>
          </div>

          {allApprovals.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500">
              No historical approvals recorded in database yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gray-950/70 text-gray-400 uppercase text-[10px] font-semibold border-b border-gray-800">
                  <tr>
                    <th className="py-2.5 px-3">Approval ID</th>
                    <th className="py-2.5 px-3">Tool</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Risk</th>
                    <th className="py-2.5 px-3">Reviewer</th>
                    <th className="py-2.5 px-3">Reviewed At</th>
                    <th className="py-2.5 px-3">Notes / Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60 font-mono">
                  {allApprovals.map((app) => (
                    <tr key={app.id} className="hover:bg-gray-800/30 transition-colors">
                      <td className="py-2 px-3 text-gray-300">{app.id.slice(0, 8)}...</td>
                      <td className="py-2 px-3 font-semibold text-blue-400">{app.tool_name}</td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getStatusBadge(app.status)}`}>
                          {app.status}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-gray-400 text-[11px]">{app.risk_level}</td>
                      <td className="py-2 px-3 text-gray-300">
                        {app.reviewer_id ? `${app.reviewer_id} (${app.reviewer_role})` : 'System (Auto)'}
                      </td>
                      <td className="py-2 px-3 text-gray-400 text-[11px]">
                        {app.reviewed_at ? new Date(app.reviewed_at).toLocaleString() : 'N/A'}
                      </td>
                      <td className="py-2 px-3 text-gray-400 text-[11px] max-w-xs truncate">
                        {app.rejection_reason || 'Approved unconditionally'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
