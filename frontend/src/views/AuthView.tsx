import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { UserRole } from '../types';
import { ShieldCheck, Lock, UserCheck, Key, CheckCircle, AlertTriangle } from 'lucide-react';

export const AuthView: React.FC = () => {
  const { user, login, switchRole } = useAuth();
  const [customEmail, setCustomEmail] = useState('');
  const [customName, setCustomName] = useState('');
  const [selectedRole, setSelectedRole] = useState<UserRole>(user.role);
  const [message, setMessage] = useState<string | null>(null);

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login(selectedRole, customName || undefined, customEmail || undefined);
    setMessage(`Successfully authenticated as ${selectedRole.toUpperCase()}`);
    setTimeout(() => setMessage(null), 3000);
  };

  const rolePermissions: Record<UserRole, { title: string; badge: string; perms: string[] }> = {
    admin: {
      title: 'Security Administrator',
      badge: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
      perms: [
        'Full read & write access across all subsystems',
        'Configure runtime security policy thresholds',
        'Register, modify, and delete AI agents',
        'Review and authorize all HITL tool execution requests',
        'Upload and purge corporate knowledge base documents',
        'Execute full adversarial red team suites',
      ],
    },
    supervisor: {
      title: 'Operations Supervisor',
      badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      perms: [
        'Review and authorize pending HITL tool actions',
        'Inspect execution traces and audit logs',
        'Test agent executions in sandbox environments',
        'Trigger continuous evaluation and regression runs',
        'Upload corporate knowledge documents',
        'Cannot modify global security policy thresholds',
      ],
    },
    analyst: {
      title: 'Threat & Evaluation Analyst',
      badge: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      perms: [
        'Execute red team adversarial benchmark tests',
        'Trigger RAGAS and security evaluation runs',
        'Inspect security incidents and trace span waterfall',
        'Test RAG hybrid retrieval queries',
        'Cannot approve sensitive financial/HITL actions',
        'Cannot register or delete production agents',
      ],
    },
    viewer: {
      title: 'Compliance Auditor',
      badge: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
      perms: [
        'Read-only access across telemetry and overview metrics',
        'View security incidents and compliance audit logs',
        'Inspect evaluation scores and regression reports',
        'View registered tools and system settings',
        'Cannot execute queries, tests, or modify state',
        'Cannot authorize or reject approval requests',
      ],
    },
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Key className="w-5 h-5 text-blue-400" />
          Authentication & Role-Based Access Control (RBAC)
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Manage session authorization, inspect enterprise role privileges, and simulate operator roles. Backend authorization remains authoritative.
        </p>
      </div>

      {message && (
        <div className="p-3 bg-emerald-950/50 border border-emerald-500/30 rounded-lg text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {/* Active Session Status */}
      <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="text-sm font-semibold text-white">{user.name}</div>
              <div className="text-xs text-gray-400 font-mono">{user.email}</div>
              <div className="text-[11px] text-gray-400 mt-0.5">Session ID: <span className="font-mono text-gray-400">{user.id}</span></div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className={`px-3 py-1.5 rounded-lg border text-xs font-semibold capitalize font-mono ${rolePermissions[user.role].badge}`}>
              {user.role} role
            </div>
            <div className="text-right text-xs text-gray-400">
              <div>Auth Type: <span className="text-gray-300 font-medium">Session Token</span></div>
              <div className="text-emerald-400 text-[11px] flex items-center gap-1 justify-end mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Active Session
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Switch / Authenticate Form */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-blue-400" />
            Switch Active Session Role
          </h2>
          <p className="text-xs text-gray-400">
            Select a target enterprise persona to simulate dashboard capabilities and authorization gates.
          </p>

          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Target Persona Role</label>
              <div className="grid grid-cols-2 gap-2">
                {(['admin', 'supervisor', 'analyst', 'viewer'] as UserRole[]).map((r) => (
                  <button
                    type="button"
                    key={r}
                    onClick={() => {
                      setSelectedRole(r);
                      switchRole(r);
                    }}
                    className={`p-2.5 rounded-lg border text-xs font-medium text-left capitalize transition-colors ${
                      user.role === r
                        ? 'bg-blue-600/15 border-blue-500/40 text-blue-300'
                        : 'bg-gray-950 border-gray-800 text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    <div className="font-semibold text-gray-200">{r}</div>
                    <div className="text-[10px] text-gray-400 truncate">{rolePermissions[r].title}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Custom Operator Name (Optional)</label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="e.g. Alex Morgan"
                className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Custom Operator Email (Optional)</label>
              <input
                type="email"
                value={customEmail}
                onChange={(e) => setCustomEmail(e.target.value)}
                placeholder="e.g. operator@sentinel.internal"
                className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <button
              type="submit"
              className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-2"
            >
              <Lock className="w-3.5 h-3.5" />
              Apply Credentials
            </button>
          </form>
        </div>

        {/* Permissions Breakdown */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
            <Lock className="w-4 h-4 text-emerald-400" />
            Privilege Matrix for {user.role.toUpperCase()}
          </h2>
          <div className="space-y-2">
            {rolePermissions[user.role].perms.map((perm, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs text-gray-300 bg-gray-950/60 p-2 rounded-lg border border-gray-900">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>{perm}</span>
              </div>
            ))}
          </div>

          <div className="p-3 bg-amber-950/30 border border-amber-600/20 rounded-lg text-amber-300/80 text-[11px] flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-amber-300">Server-Side Authorization Notice:</span>
              <p className="mt-0.5 text-gray-400">
                Client role selection simulates UI permissions. The FastAPI backend validates every mutating API request server-side and will strictly return 403 Forbidden if a caller attempts an unauthorized action regardless of UI state.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

