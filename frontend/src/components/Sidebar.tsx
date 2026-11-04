import React from 'react';
import {
  LayoutDashboard,
  ShieldAlert,
  CheckSquare,
  Bot,
  Activity,
  BookOpen,
  LineChart,
} from 'lucide-react';

export type NavTab =
  | 'dashboard'
  | 'security'
  | 'approvals'
  | 'agent-runner'
  | 'traces'
  | 'knowledge'
  | 'evaluation';

interface SidebarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  pendingApprovalsCount: number;
  threatsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  pendingApprovalsCount,
  threatsCount,
}) => {
  const navItems: Array<{ id: NavTab; label: string; icon: React.ReactNode; badge?: number; badgeColor?: string }> = [
    {
      id: 'dashboard',
      label: 'Telemetry Dashboard',
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      id: 'security',
      label: 'Security Firewall',
      icon: <ShieldAlert className="w-4 h-4" />,
      badge: threatsCount,
      badgeColor: 'bg-rose-500/20 text-rose-400 border border-rose-500/30',
    },
    {
      id: 'approvals',
      label: 'HITL Approvals',
      icon: <CheckSquare className="w-4 h-4" />,
      badge: pendingApprovalsCount,
      badgeColor: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
    },
    {
      id: 'agent-runner',
      label: 'Agent Sandbox',
      icon: <Bot className="w-4 h-4" />,
    },
    {
      id: 'traces',
      label: 'Trace Explorer',
      icon: <Activity className="w-4 h-4" />,
    },
    {
      id: 'knowledge',
      label: 'Document Knowledge',
      icon: <BookOpen className="w-4 h-4" />,
    },
    {
      id: 'evaluation',
      label: 'Continuous Evaluation',
      icon: <LineChart className="w-4 h-4" />,
    },
  ];

  return (
    <aside className="w-64 border-r border-gray-800 bg-gray-950 flex flex-col justify-between shrink-0 h-[calc(100vh-4rem)]">
      <div className="p-4 space-y-1">
        <div className="px-3 py-2 text-[11px] font-semibold tracking-wider uppercase text-gray-500">
          Core Subsystems
        </div>
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-900'
              }`}
            >
              <div className="flex items-center gap-3">
                {item.icon}
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span className={`text-[11px] px-1.5 py-0.5 rounded-full font-bold ${item.badgeColor}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="p-4 border-t border-gray-900 bg-gray-950/40">
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-lg p-3 text-xs text-gray-400">
          <div className="flex items-center justify-between mb-1">
            <span className="text-gray-300 font-medium">Data Integrity</span>
            <span className="text-emerald-400 text-[10px] font-semibold">ENFORCED</span>
          </div>
          <p className="text-[11px] leading-relaxed text-gray-400">
            Metrics sourced strictly from database tables. No hardcoded statistics.
          </p>
        </div>
      </div>
    </aside>
  );
};

