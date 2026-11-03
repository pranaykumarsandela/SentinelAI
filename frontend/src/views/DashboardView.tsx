import React from 'react';
import {
  Activity,
  ShieldCheck,
  ShieldAlert,
  Clock,
  Coins,
  Cpu,
  TrendingUp,
  BarChart3,
  Bot,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { DashboardMetrics } from '../types';
import { MetricCard } from '../components/MetricCard';
import { EmptyState } from '../components/EmptyState';

interface DashboardViewProps {
  metrics: DashboardMetrics | null;
  loading: boolean;
  onNavigateToRunner: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  metrics,
  loading,
  onNavigateToRunner,
}) => {
  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        <Activity className="w-6 h-6 animate-spin text-blue-500 mr-2" />
        <span>Loading verified database metrics...</span>
      </div>
    );
  }

  if (!metrics || metrics.is_fresh_install) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-white">Production Telemetry Dashboard</h1>
          <p className="text-sm text-gray-400">Authentic database metrics & platform telemetry.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard title="Total Executions" value={0} subtitle="execution_traces count" />
          <MetricCard title="Success Rate" value="N/A" subtitle="Zero requests recorded" />
          <MetricCard title="Threats Blocked" value={0} subtitle="security_events count" />
          <MetricCard title="P95 Latency" value={0} unit="ms" subtitle="trace_spans percentile" />
        </div>

        <EmptyState
          title="Fresh Installation Verified (Zero Data State)"
          description="In compliance with the SentinelAI Mandatory Data Integrity Policy, all metrics originate strictly from persisted database traces. No synthetic or simulated numbers are generated for dashboard placeholders."
          actionLabel="Execute Test Query in Agent Sandbox"
          onAction={onNavigateToRunner}
          icon={<Bot className="w-8 h-8 text-blue-400" />}
        />
      </div>
    );
  }

  // Real chart data sourced strictly from DB metrics
  const statusChartData = [
    { name: 'Successful', value: metrics.successful_requests, color: '#10B981' },
    { name: 'Blocked', value: metrics.blocked_requests, color: '#EF4444' },
    { name: 'Failed', value: metrics.failed_requests, color: '#F59E0B' },
  ].filter((d) => d.value > 0);

  const latencyChartData = [
    { metric: 'Avg', latency: metrics.average_latency_ms },
    { metric: 'Median (P50)', latency: metrics.median_latency_ms },
    { metric: 'P95', latency: metrics.p95_latency_ms },
    { metric: 'P99', latency: metrics.p99_latency_ms },
  ];

  const successRateText =
    metrics.execution_success_rate !== null ? `${metrics.execution_success_rate}%` : 'N/A';
  const blockedRateText =
    metrics.blocked_request_rate !== null ? `${metrics.blocked_request_rate}%` : 'N/A';

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Production Telemetry Dashboard</h1>
          <p className="text-sm text-gray-400">
            Real-time execution analytics from PostgreSQL/SQLite & Qdrant telemetry.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">
            Partitions: <strong className="text-gray-300">{metrics.live_requests} Live</strong> /{' '}
            <strong className="text-gray-300">{metrics.mock_requests} Mock</strong>
          </span>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Requests"
          value={metrics.total_requests}
          icon={<Activity className="w-4 h-4 text-blue-400" />}
          badge={`${metrics.live_requests} Live / ${metrics.mock_requests} Mock`}
          badgeColor="blue"
        />
        <MetricCard
          title="Execution Success"
          value={successRateText}
          subtitle={`${metrics.successful_requests} successful / ${metrics.failed_requests} failed`}
          icon={<ShieldCheck className="w-4 h-4 text-emerald-400" />}
          badge={metrics.successful_requests > 0 ? 'HEALTHY' : 'PENDING'}
          badgeColor="green"
        />
        <MetricCard
          title="Security Defense"
          value={blockedRateText}
          subtitle={`${metrics.blocked_requests} requests blocked by firewall`}
          icon={<ShieldAlert className="w-4 h-4 text-rose-400" />}
          badge={metrics.blocked_requests > 0 ? 'DEFENSE ACTIVE' : 'CLEAR'}
          badgeColor={metrics.blocked_requests > 0 ? 'red' : 'gray'}
        />
        <MetricCard
          title="Latency (P95)"
          value={metrics.p95_latency_ms}
          unit="ms"
          subtitle={`Median: ${metrics.median_latency_ms} ms / Avg: ${metrics.average_latency_ms} ms`}
          icon={<Clock className="w-4 h-4 text-amber-400" />}
          badge="SPAN TELEMETRY"
          badgeColor="amber"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          title="Token Consumption"
          value={metrics.total_tokens.toLocaleString()}
          subtitle={`${metrics.prompt_tokens.toLocaleString()} in / ${metrics.completion_tokens.toLocaleString()} out`}
          icon={<Cpu className="w-4 h-4 text-purple-400" />}
        />
        <MetricCard
          title="Estimated Cost"
          value={`$${metrics.total_cost_usd.toFixed(4)}`}
          subtitle="Calculated from actual token counts"
          icon={<Coins className="w-4 h-4 text-emerald-400" />}
        />
        <MetricCard
          title="Pending Approvals"
          value={metrics.pending_approvals}
          subtitle="Human review queue"
          icon={<ShieldAlert className="w-4 h-4 text-blue-400" />}
          badge={metrics.pending_approvals > 0 ? 'ACTION REQUIRED' : 'UP TO DATE'}
          badgeColor={metrics.pending_approvals > 0 ? 'amber' : 'green'}
        />
      </div>

      {/* Visual Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latency Percentiles Bar Chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Latency Distribution Percentiles</h3>
              <p className="text-xs text-gray-400">Authentic milliseconds from trace spans</p>
            </div>
            <BarChart3 className="w-4 h-4 text-gray-500" />
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={latencyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis dataKey="metric" stroke="#6b7280" fontSize={12} tickLine={false} />
                <YAxis stroke="#6b7280" fontSize={12} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '8px' }}
                  labelStyle={{ color: '#f3f4f6' }}
                  formatter={(value: any) => [`${value} ms`, 'Latency']}
                />
                <Bar dataKey="latency" fill="#3B82F6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Execution Breakdown Pie Chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Execution Status Distribution</h3>
              <p className="text-xs text-gray-400">Aggregated from execution_traces</p>
            </div>
            <TrendingUp className="w-4 h-4 text-gray-500" />
          </div>
          <div className="h-64">
            {statusChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {statusChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '8px' }}
                  />
                  <Legend verticalAlign="bottom" height={36} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-gray-500">
                No execution records available for breakdown.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
