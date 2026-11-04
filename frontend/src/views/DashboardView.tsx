import React, { useState, useEffect } from 'react';
import {
  Activity,
  ShieldCheck,
  ShieldAlert,
  Clock,
  Cpu,
  BarChart3,
  Bot,
  Layers,
  ArrowUpRight,
  TrendingDown,
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
  AreaChart,
  Area,
} from 'recharts';
import { DashboardMetrics, TimeseriesPoint, ExecutionTraceItem } from '../types';
import { MetricCard } from '../components/MetricCard';
import { EmptyState } from '../components/EmptyState';
import { api } from '../api/client';

interface DashboardViewProps {
  metrics: DashboardMetrics | null;
  loading: boolean;
  onNavigateToRunner: () => void;
  onNavigateToTrace?: (traceId: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  metrics,
  loading,
  onNavigateToRunner,
  onNavigateToTrace,
}) => {
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [recentTraces, setRecentTraces] = useState<ExecutionTraceItem[]>([]);
  const [loadingExtras, setLoadingExtras] = useState(false);

  useEffect(() => {
    const fetchExtras = async () => {
      try {
        setLoadingExtras(true);
        const [tsData, tracesData] = await Promise.all([
          api.getDashboardTimeseries('all', 1).catch(() => []),
          api.getTraces(undefined, undefined, undefined, 6).catch(() => []),
        ]);
        setTimeseries(tsData || []);
        setRecentTraces(tracesData || []);
      } finally {
        setLoadingExtras(false);
      }
    };
    fetchExtras();
  }, [metrics]);

  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <Activity className="w-6 h-6 animate-spin text-blue-500 mr-2" />
        <span className="text-sm">Loading verified database metrics...</span>
      </div>
    );
  }

  if (!metrics || metrics.is_fresh_install) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-white">Overview Dashboard</h1>
          <p className="text-xs text-gray-400 mt-1">Authentic database telemetry and security health.</p>
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
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            Overview Dashboard
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Real-time execution analytics from PostgreSQL/SQLite & Qdrant telemetry.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400 bg-gray-900 border border-gray-800 px-3 py-1.5 rounded-lg">
          <span>Partitions:</span>
          <strong className="text-emerald-400 font-mono">{metrics.live_requests} Live</strong>
          <span className="text-gray-600">/</span>
          <strong className="text-amber-400 font-mono">{metrics.mock_requests} Mock</strong>
        </div>
      </div>

      {/* Primary Metric Cards Grid */}
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

      {/* Secondary Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          title="Token Consumption"
          value={metrics.total_tokens.toLocaleString()}
          subtitle={`${metrics.prompt_tokens.toLocaleString()} prompt / ${metrics.completion_tokens.toLocaleString()} completion`}
          icon={<Cpu className="w-4 h-4 text-purple-400" />}
        />
        <MetricCard
          title="Security Interceptions"
          value={metrics.blocked_requests}
          subtitle="Direct injection, jailbreaks, PII"
          icon={<ShieldAlert className="w-4 h-4 text-rose-400" />}
          badge={metrics.blocked_requests > 0 ? 'INTERCEPTED' : 'CLEAN'}
          badgeColor={metrics.blocked_requests > 0 ? 'red' : 'green'}
        />
        <MetricCard
          title="Pending Approvals"
          value={metrics.pending_approvals}
          subtitle="Human review queue"
          icon={<Clock className="w-4 h-4 text-blue-400" />}
          badge={metrics.pending_approvals > 0 ? 'ACTION REQUIRED' : 'UP TO DATE'}
          badgeColor={metrics.pending_approvals > 0 ? 'amber' : 'green'}
        />
      </div>

      {/* Visual Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Real Time-series Request Volume */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Execution Activity Over Time</h3>
              <p className="text-xs text-gray-400">Authentic hourly request volume from database timestamps</p>
            </div>
            <Activity className="w-4 h-4 text-blue-400" />
          </div>
          <div className="h-64">
            {timeseries.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeseries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="colorBlocked" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#EF4444" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                  <XAxis dataKey="timestamp" stroke="#6b7280" fontSize={10} tickLine={false} />
                  <YAxis stroke="#6b7280" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '8px' }}
                    labelStyle={{ color: '#f3f4f6' }}
                  />
                  <Area type="monotone" dataKey="request_count" stroke="#3B82F6" fillOpacity={1} fill="url(#colorRequests)" name="Total Requests" />
                  <Area type="monotone" dataKey="blocked_count" stroke="#EF4444" fillOpacity={1} fill="url(#colorBlocked)" name="Blocked Requests" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-gray-500">
                No timeseries records accumulated yet.
              </div>
            )}
          </div>
        </div>

        {/* Status Distribution */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Execution Status</h3>
              <p className="text-xs text-gray-400">Aggregated from execution_traces</p>
            </div>
            <BarChart3 className="w-4 h-4 text-gray-500" />
          </div>
          <div className="h-64">
            {statusChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {statusChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '8px' }}
                  />
                  <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '11px' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-gray-500">
                No execution records available.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Latency Percentiles Bar Chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Latency Distribution Percentiles</h3>
            <p className="text-xs text-gray-400">Actual milliseconds calculated from trace spans</p>
          </div>
          <Clock className="w-4 h-4 text-amber-400" />
        </div>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={latencyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis dataKey="metric" stroke="#6b7280" fontSize={11} tickLine={false} />
              <YAxis stroke="#6b7280" fontSize={11} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '8px' }}
                labelStyle={{ color: '#f3f4f6' }}
                formatter={(value: any) => [`${value} ms`, 'Latency']}
              />
              <Bar dataKey="latency" fill="#F59E0B" radius={[4, 4, 0, 0]} barSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Executions Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Recent Agent Executions</h3>
            <p className="text-xs text-gray-400">Authentic records from PostgreSQL/SQLite</p>
          </div>
        </div>

        {recentTraces.length === 0 ? (
          <div className="py-8 text-center text-xs text-gray-500">
            No executions recorded yet. Execute a query in Agent Sandbox to generate traces.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-950/60 text-gray-400 uppercase text-[10px] font-semibold border-b border-gray-800">
                <tr>
                  <th className="py-2.5 px-3">Trace ID</th>
                  <th className="py-2.5 px-3">Agent</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Tokens</th>
                  <th className="py-2.5 px-3">Latency</th>
                  <th className="py-2.5 px-3">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {recentTraces.map((tr) => (
                  <tr key={tr.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="py-2 px-3 font-mono text-gray-300">
                      {onNavigateToTrace ? (
                        <button
                          onClick={() => onNavigateToTrace(tr.id)}
                          className="hover:text-blue-400 underline underline-offset-2 flex items-center gap-1"
                        >
                          {tr.id.slice(0, 8)}...
                          <ArrowUpRight className="w-3 h-3" />
                        </button>
                      ) : (
                        `${tr.id.slice(0, 8)}...`
                      )}
                    </td>
                    <td className="py-2 px-3 font-medium text-gray-200">{tr.agent_id}</td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          tr.status === 'SUCCESS'
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            : tr.status === 'BLOCKED'
                            ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                            : tr.status === 'PENDING_APPROVAL'
                            ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                            : 'bg-gray-500/15 text-gray-400 border border-gray-500/30'
                        }`}
                      >
                        {tr.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-mono text-gray-300">{tr.total_tokens.toLocaleString()}</td>
                    <td className="py-2 px-3 font-mono text-gray-400">{tr.total_latency_ms.toFixed(1)} ms</td>
                    <td className="py-2 px-3 text-gray-400 font-mono text-[11px]">
                      {new Date(tr.started_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
