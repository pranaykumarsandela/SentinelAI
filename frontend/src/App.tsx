import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar, NavTab } from './components/Sidebar';
import { DashboardView } from './views/DashboardView';
import { SecurityGuardView } from './views/SecurityGuardView';
import { ApprovalsView } from './views/ApprovalsView';
import { AgentRunnerView } from './views/AgentRunnerView';
import { TraceExplorerView } from './views/TraceExplorerView';
import { KnowledgeBaseView } from './views/KnowledgeBaseView';
import { EvaluationView } from './views/EvaluationView';
import { DashboardMetrics } from './types';
import { api } from './api/client';

export const App: React.FC = () => {
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
        api.getHealth().catch(() => ({ success: false, data: { status: 'OFFLINE' } })),
        api.getDashboardMetrics(isMockFilter).catch(() => null),
      ]);

      if (healthData && healthData.data?.status) {
        setSystemHealth(healthData.data.status);
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

        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-gray-950">
          <div className="max-w-7xl mx-auto">
            {currentTab === 'dashboard' && (
              <DashboardView
                metrics={metrics}
                loading={loadingMetrics}
                onNavigateToRunner={() => setCurrentTab('agent-runner')}
              />
            )}
            {currentTab === 'security' && <SecurityGuardView />}
            {currentTab === 'approvals' && <ApprovalsView />}
            {currentTab === 'agent-runner' && (
              <AgentRunnerView
                onNavigateToTrace={handleNavigateToTrace}
                onRefreshMetrics={refreshAll}
              />
            )}
            {currentTab === 'traces' && (
              <TraceExplorerView initialTraceId={targetedTraceId} />
            )}
            {currentTab === 'knowledge' && <KnowledgeBaseView />}
            {currentTab === 'evaluation' && <EvaluationView />}
          </div>
        </main>
      </div>
    </div>
  );
};

export default App;

