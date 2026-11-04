import React, { useState, useEffect } from 'react';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Sidebar, NavTab } from './components/Sidebar';
import { DashboardView } from './views/DashboardView';
import { AgentManagementView } from './views/AgentManagementView';
import { SecurityCenterView } from './views/SecurityCenterView';
import { RAGExplorerView } from './views/RAGExplorerView';
import { TraceExplorerView } from './views/TraceExplorerView';
import { ToolMonitoringView } from './views/ToolMonitoringView';
import { ApprovalsView } from './views/ApprovalsView';
import { EvaluationCenterView } from './views/EvaluationCenterView';
import { RedTeamLabView } from './views/RedTeamLabView';
import { AuditLogsView } from './views/AuditLogsView';
import { SettingsView } from './views/SettingsView';
import { AuthView } from './views/AuthView';
import { DashboardMetrics } from './types';
import { api } from './api/client';

const AppContent: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [systemHealth, setSystemHealth] = useState('CONNECTING');
  const [isMockFilter, setIsMockFilter] = useState<boolean | undefined>(undefined);
  const [targetedTraceId, setTargetedTraceId] = useState<string | null>(null);

  const refreshAll = async () => {
    try {
      setLoadingMetrics(true);
      const [healthData, metricsData] = await Promise.all([
        api.getHealth().catch(() => ({ status: 'OFFLINE' })),
        api.getDashboardMetrics('all', isMockFilter).catch(() => null),
      ]);

      if (healthData && (healthData as any).status) {
        setSystemHealth((healthData as any).status);
      }
      if (metricsData) {
        setMetrics(metricsData);
      }
    } finally {
      setLoadingMetrics(false);
    }
  };

  useEffect(() => {
    refreshAll();
  }, [isMockFilter]);

  const handleNavigateToTrace = (traceId: string) => {
    setTargetedTraceId(traceId);
    setCurrentTab('traces');
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col font-sans">
      <Navbar
        systemHealth={systemHealth}
        isMockFilter={isMockFilter}
        onToggleMockFilter={(val) => setIsMockFilter(val)}
        onRefresh={refreshAll}
        isRefreshing={loadingMetrics}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          currentTab={currentTab}
          onSelectTab={(tab) => {
            setCurrentTab(tab);
            if (tab !== 'traces') {
              setTargetedTraceId(null);
            }
          }}
          pendingApprovalsCount={metrics?.pending_approvals || 0}
          threatsCount={metrics?.blocked_requests || 0}
        />

        <main className="flex-1 overflow-y-auto p-5 md:p-7 bg-gray-950">
          <div className="max-w-7xl mx-auto">
            {currentTab === 'dashboard' && (
              <DashboardView
                metrics={metrics}
                loading={loadingMetrics}
                onNavigateToRunner={() => setCurrentTab('agents')}
                onNavigateToTrace={handleNavigateToTrace}
              />
            )}
            {currentTab === 'agents' && (
              <AgentManagementView onNavigateToTrace={handleNavigateToTrace} />
            )}
            {currentTab === 'security' && <SecurityCenterView />}
            {currentTab === 'rag' && <RAGExplorerView />}
            {currentTab === 'traces' && (
              <TraceExplorerView initialTraceId={targetedTraceId} />
            )}
            {currentTab === 'tools' && <ToolMonitoringView />}
            {currentTab === 'approvals' && <ApprovalsView />}
            {currentTab === 'evaluations' && <EvaluationCenterView />}
            {currentTab === 'red-team' && <RedTeamLabView />}
            {currentTab === 'audit' && <AuditLogsView />}
            {currentTab === 'settings' && <SettingsView />}
            {currentTab === 'auth' && <AuthView />}
          </div>
        </main>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
