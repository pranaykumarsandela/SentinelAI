import React, { useState } from 'react';
import { Shield, RefreshCw, UserCheck, ChevronDown, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { UserRole } from '../types';

interface NavbarProps {
  systemHealth: string;
  isMockFilter?: boolean;
  onToggleMockFilter?: (val?: boolean) => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  systemHealth,
  isMockFilter,
  onToggleMockFilter,
  onRefresh,
  isRefreshing,
}) => {
  const { user, switchRole } = useAuth();
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);

  const roles: Array<{ id: UserRole; label: string; desc: string }> = [
    { id: 'admin', label: 'Administrator', desc: 'Full policy, agent, and system configuration control' },
    { id: 'supervisor', label: 'Supervisor', desc: 'Can authorize and reject HITL tool executions' },
    { id: 'analyst', label: 'Threat Analyst', desc: 'Can execute red team tests and inspect security incidents' },
    { id: 'viewer', label: 'Read-only Auditor', desc: 'Read-only access across telemetry and audit trails' },
  ];

  return (
    <header className="h-16 border-b border-gray-800 bg-gray-950/90 backdrop-blur sticky top-0 z-30 px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-600/10 border border-blue-500/20 rounded-lg text-blue-500 flex items-center justify-center">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-base tracking-tight text-white">SentinelAI</span>
            <span className="px-1.5 py-0.2 bg-blue-500/10 border border-blue-500/30 text-blue-400 text-[10px] font-semibold rounded">
              ENTERPRISE v0.1.0
            </span>
          </div>
          <span className="text-[11px] text-gray-400 block -mt-0.5">Agent Security & Evaluation Platform</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Mock Filter Toggle */}
        {onToggleMockFilter && (
          <div className="flex items-center bg-gray-900 border border-gray-800 rounded-lg p-0.5 text-xs">
            <button
              onClick={() => onToggleMockFilter(undefined)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                isMockFilter === undefined
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              All Data
            </button>
            <button
              onClick={() => onToggleMockFilter(false)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                isMockFilter === false
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Live Only
            </button>
            <button
              onClick={() => onToggleMockFilter(true)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                isMockFilter === true
                  ? 'bg-amber-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Mock Telemetry
            </button>
          </div>
        )}

        {/* Health Indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs">
          <span className={`w-2 h-2 rounded-full ${systemHealth === 'HEALTHY' || systemHealth === 'OPERATIONAL' ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
          <span className="text-gray-300 font-medium font-mono text-[11px]">Engine: {systemHealth}</span>
        </div>

        {/* Role Switcher Dropdown */}
        <div className="relative">
          <button
            onClick={() => setRoleMenuOpen(!roleMenuOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 hover:border-gray-700 text-xs text-gray-200 transition-colors"
          >
            <UserCheck className="w-3.5 h-3.5 text-blue-400" />
            <span className="capitalize font-medium">{user.role}</span>
            <ChevronDown className="w-3 h-3 text-gray-400" />
          </button>

          {roleMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-gray-900 border border-gray-800 rounded-xl shadow-2xl p-1 z-50">
              <div className="px-3 py-2 border-b border-gray-800">
                <div className="text-[10px] font-semibold tracking-wider uppercase text-gray-400">Switch Active Role</div>
                <div className="text-xs text-gray-400">Simulate role-based UI permissions</div>
              </div>
              <div className="p-1 space-y-0.5">
                {roles.map((r) => {
                  const isCurrent = user.role === r.id;
                  return (
                    <button
                      key={r.id}
                      onClick={() => {
                        switchRole(r.id);
                        setRoleMenuOpen(false);
                      }}
                      className={`w-full text-left p-2 rounded-lg text-xs transition-colors flex items-start justify-between ${
                        isCurrent ? 'bg-blue-600/15 text-blue-300 border border-blue-500/20' : 'text-gray-300 hover:bg-gray-800'
                      }`}
                    >
                      <div>
                        <div className="font-medium text-gray-100 flex items-center gap-1.5">
                          {r.label}
                          {isCurrent && <Check className="w-3 h-3 text-blue-400 inline" />}
                        </div>
                        <div className="text-[10px] text-gray-400 leading-tight mt-0.5">{r.desc}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Refresh Button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg bg-gray-900 border border-gray-800 text-gray-400 hover:text-white hover:border-gray-700 transition-colors disabled:opacity-50"
            title="Refresh authentic data"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-blue-400' : ''}`} />
          </button>
        )}
      </div>
    </header>
  );
};
