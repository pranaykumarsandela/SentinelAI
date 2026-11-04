import React from 'react';
import {
  LayoutDashboard,
  ShieldAlert,
  CheckSquare,
  Bot,
  Activity,
  BookOpen,
  LineChart,
  Flame,
  Wrench,
  FileText,
  Settings,
  KeyRound,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export type NavTab =
  | 'dashboard'
  | 'agents'
  | 'security'
  | 'rag'
  | 'traces'
  | 'tools'
  | 'approvals'
  | 'evaluations'
  | 'red-team'
  | 'audit'
  | 'settings'
  | 'auth';

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
  const { user } = useAuth();

  const sections: Array<{
    title: string;
    items: Array<{
      id: NavTab;
      label: string;
      icon: React.ReactNode;
      badge?: number;
      badgeColor?: string;
    }>;
  }> = [
    {
      title: 'Operations',
      items: [
        {
          id: 'dashboard',
          label: 'Overview Dashboard',
          icon: <LayoutDashboard className="w-4 h-4" />,
        },
        {
          id: 'agents',
          label: 'Agent Management',
          icon: <Bot className="w-4 h-4" />,
        },
        {
          id: 'traces',
          label: 'Execution Traces',
          icon: <Activity className="w-4 h-4" />,
        },
      ],
    },
    {
      title: 'Security & Firewalls',
      items: [
        {
          id: 'security',
          label: 'Security Center',
          icon: <ShieldAlert className="w-4 h-4" />,
          badge: threatsCount,
          badgeColor: 'bg-rose-500/20 text-rose-400 border border-rose-500/30',
        },
        {
          id: 'approvals',
          label: 'Human Approvals',
          icon: <CheckSquare className="w-4 h-4" />,
          badge: pendingApprovalsCount,
          badgeColor: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
        },
        {
          id: 'red-team',
          label: 'Red Team Lab',
          icon: <Flame className="w-4 h-4 text-orange-400" />,
        },
      ],
    },
    {
      title: 'Intelligence & RAG',
      items: [
        {
          id: 'rag',
          label: 'RAG Explorer',
          icon: <BookOpen className="w-4 h-4" />,
        },
        {
          id: 'tools',
          label: 'Tool Monitoring',
          icon: <Wrench className="w-4 h-4" />,
        },
      ],
    },
    {
      title: 'Governance & Auditing',
      items: [
        {
          id: 'evaluations',
          label: 'Evaluation Center',
          icon: <LineChart className="w-4 h-4" />,
        },
        {
          id: 'audit',
          label: 'Audit Logs',
          icon: <FileText className="w-4 h-4" />,
        },
      ],
    },
    {
      title: 'Configuration',
      items: [
        {
          id: 'auth',
          label: 'Authentication',
          icon: <KeyRound className="w-4 h-4" />,
        },
        {
          id: 'settings',
          label: 'Settings',
          icon: <Settings className="w-4 h-4" />,
        },
      ],
    },
  ];

  return (
    <aside className="w-64 border-r border-gray-800 bg-gray-950 flex flex-col justify-between shrink-0 h-[calc(100vh-4rem)]">
      <div className="p-3 space-y-4 overflow-y-auto">
        {sections.map((sec, idx) => (
          <div key={idx} className="space-y-1">
            <div className="px-3 py-1 text-[10px] font-semibold tracking-wider uppercase text-gray-500">
              {sec.title}
            </div>
            {sec.items.map((item) => {
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelectTab(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-900/60'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    {item.icon}
                    <span>{item.label}</span>
                  </div>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${item.badgeColor}`}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* User profile & role footer */}
      <div className="p-3 border-t border-gray-900 bg-gray-950/80">
        <button
          onClick={() => onSelectTab('auth')}
          className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-gray-900/60 transition-colors text-left"
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-md bg-blue-900/30 border border-blue-700/40 flex items-center justify-center text-blue-400 shrink-0">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div className="truncate">
              <div className="text-xs font-medium text-gray-200 truncate">{user.name}</div>
              <div className="text-[10px] text-gray-400 font-mono capitalize">{user.role} role</div>
            </div>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-800 text-gray-300 uppercase shrink-0">
            {user.role.slice(0, 3)}
          </span>
        </button>
      </div>
    </aside>
  );
};
