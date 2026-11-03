import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Play,
  CheckCircle,
  AlertTriangle,
  GitCompare,
  TrendingUp,
  Shield,
  Layers,
  RefreshCw,
} from 'lucide-react';
import { EvaluationRunItem } from '../types';
import { api } from '../api/client';
import { EmptyState } from '../components/EmptyState';

export const EvaluationView: React.FC = () => {
  const [runs, setRuns] = useState<EvaluationRunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningRagas, setRunningRagas] = useState(false);
  const [runningSecurity, setRunningSecurity] = useState(false);
  const [activeReport, setActiveReport] = useState<any | null>(null);

  // Regression Comparison State
  const [baselineRunId, setBaselineRunId] = useState<string>('');
  const [candidateRunId, setCandidateRunId] = useState<string>('');
  const [comparisonResult, setComparisonResult] = useState<any | null>(null);
  const [comparing, setComparing] = useState(false);

  const loadRuns = async () => {
    try {
      setLoading(true);
      const data = await api.getEvaluationRuns();
      setRuns(data);
      if (data.length >= 2 && !baselineRunId && !candidateRunId) {
        setBaselineRunId(data[data.length - 1].id);
        setCandidateRunId(data[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load runs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, []);

  const handleRunRagas = async () => {
    try {
      setRunningRagas(true);
      const res = await api.runRagasEvaluation('v1.0');
      setActiveReport({ type: 'RAGAS', data: res });
      await loadRuns();
    } catch (err: any) {
      alert(`RAGAS Evaluation failed: ${err.message}`);
    } finally {
      setRunningRagas(false);
    }
  };

  const handleRunSecurity = async () => {
    try {
      setRunningSecurity(true);
      const res = await api.runSecurityBenchmark('v1.0');
      setActiveReport({ type: 'SECURITY', data: res });
      await loadRuns();
    } catch (err: any) {
      alert(`Security Benchmark failed: ${err.message}`);
    } finally {
      setRunningSecurity(false);
    }
  };

  const handleCompare = async () => {
    if (!baselineRunId || !candidateRunId) return;
    try {
      setComparing(true);
      const res = await api.compareEvaluations(baselineRunId, candidateRunId);
      setComparisonResult(res);
    } catch (err: any) {
      alert(`Comparison failed: ${err.message}`);
    } finally {
      setComparing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <LineChart className="w-5 h-5 text-blue-400" />
            Continuous Evaluation & Red-Teaming Benchmarks
          </h1>
          <p className="text-sm text-gray-400">
            Automated RAGAS retrieval evaluations and adversarial security robustness benchmarks. Zero fabricated scores.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRunRagas}
            disabled={runningRagas}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-xs font-semibold text-white shadow-sm transition-colors"
          >
            <Play className={`w-3.5 h-3.5 ${runningRagas ? 'animate-spin' : ''}`} />
            {runningRagas ? 'Evaluating RAGAS...' : 'Run RAGAS Benchmark'}
          </button>
          <button
            onClick={handleRunSecurity}
            disabled={runningSecurity}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-xs font-semibold text-white shadow-sm transition-colors"
          >
            <Shield className={`w-3.5 h-3.5 ${runningSecurity ? 'animate-pulse' : ''}`} />
            {runningSecurity ? 'Red-Teaming...' : 'Run Security Benchmark'}
          </button>
        </div>
      </div>

      {/* Active Benchmark Results Card */}
      {activeReport && (
        <div className="bg-gray-900 border border-blue-500/40 rounded-xl p-5 shadow-lg space-y-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              Latest Benchmark Run Output ({activeReport.type})
            </h3>
            <span className="font-mono text-xs text-gray-400">{activeReport.data.run_id}</span>
          </div>

          {activeReport.type === 'RAGAS' && activeReport.data.metric_summary && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">FAITHFULNESS</span>
                <strong className="text-white text-base">
                  {(activeReport.data.metric_summary.mean_faithfulness * 100).toFixed(1)}%
                </strong>
              </div>
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">ANSWER RELEVANCY</span>
                <strong className="text-white text-base">
                  {(activeReport.data.metric_summary.mean_answer_relevancy * 100).toFixed(1)}%
                </strong>
              </div>
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">CONTEXT PRECISION</span>
                <strong className="text-white text-base">
                  {(activeReport.data.metric_summary.mean_context_precision * 100).toFixed(1)}%
                </strong>
              </div>
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">CONTEXT RECALL</span>
                <strong className="text-white text-base">
                  {(activeReport.data.metric_summary.mean_context_recall * 100).toFixed(1)}%
                </strong>
              </div>
            </div>
          )}

          {activeReport.type === 'SECURITY' && activeReport.data.confusion_matrix && (
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">PRECISION</span>
                <strong className="text-emerald-400 text-base">
                  {(activeReport.data.confusion_matrix.precision * 100).toFixed(1)}%
                </strong>
              </div>
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">RECALL</span>
                <strong className="text-emerald-400 text-base">
                  {(activeReport.data.confusion_matrix.recall * 100).toFixed(1)}%
                </strong>
              </div>
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">F1 SCORE</span>
                <strong className="text-white text-base">
                  {(activeReport.data.confusion_matrix.f1_score * 100).toFixed(1)}%
                </strong>
              </div>
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">FALSE POSITIVE RATE</span>
                <strong className="text-amber-400 text-base">
                  {(activeReport.data.confusion_matrix.false_positive_rate * 100).toFixed(1)}%
                </strong>
              </div>
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <span className="text-gray-500 block text-[10px]">ACCURACY</span>
                <strong className="text-white text-base">
                  {(activeReport.data.confusion_matrix.accuracy * 100).toFixed(1)}%
                </strong>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Regression Comparison Engine */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <GitCompare className="w-4 h-4 text-blue-400" />
          Regression Evaluation Engine (Run A vs Run B)
        </h3>
        <p className="text-xs text-gray-400">
          Compare candidate agent configurations against a certified baseline to detect regressions in security or retrieval quality.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Baseline Run (Old)</label>
            <select
              value={baselineRunId}
              onChange={(e) => setBaselineRunId(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
            >
              <option value="">Select baseline run...</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.run_type} ({r.id.slice(0, 8)}) - {new Date(r.created_at).toLocaleTimeString()}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Candidate Run (New)</label>
            <select
              value={candidateRunId}
              onChange={(e) => setCandidateRunId(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
            >
              <option value="">Select candidate run...</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.run_type} ({r.id.slice(0, 8)}) - {new Date(r.created_at).toLocaleTimeString()}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleCompare}
              disabled={comparing || !baselineRunId || !candidateRunId || baselineRunId === candidateRunId}
              className="w-full py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-2"
            >
              <GitCompare className="w-3.5 h-3.5" />
              {comparing ? 'Comparing...' : 'Compute Regression Deltas'}
            </button>
          </div>
        </div>

        {comparisonResult && (
          <div className="mt-4 pt-4 border-t border-gray-800 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-white">Delta Results</span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  comparisonResult.regressed_test_cases?.length > 0
                    ? 'bg-rose-950 text-rose-300 border border-rose-800'
                    : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                }`}
              >
                {comparisonResult.regressed_test_cases?.length > 0
                  ? `${comparisonResult.regressed_test_cases.length} REGRESSIONS FOUND`
                  : 'ZERO REGRESSIONS'}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              {Object.entries(comparisonResult.metric_deltas || {}).map(([metric, delta]: any) => (
                <div key={metric} className="bg-gray-950 p-2.5 rounded border border-gray-800">
                  <span className="text-gray-500 block text-[10px] uppercase">{metric.replace(/_/g, ' ')}</span>
                  <strong className={delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                    {delta >= 0 ? `+${(delta * 100).toFixed(1)}%` : `${(delta * 100).toFixed(1)}%`}
                  </strong>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Historical Evaluation Runs */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">Persisted Evaluation Runs ({runs.length})</h3>
          <button
            onClick={loadRuns}
            disabled={loading}
            className="text-xs text-gray-400 hover:text-white flex items-center gap-1"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {runs.length === 0 && !loading ? (
          <EmptyState
            title="No Evaluation Runs Executed"
            description="Run a RAGAS retrieval evaluation or security robustness benchmark to generate deterministic evaluation metrics."
            icon={<LineChart className="w-8 h-8 text-blue-400" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-950 text-gray-400 uppercase tracking-wider text-[10px] border-b border-gray-800">
                <tr>
                  <th className="py-3 px-4">Run ID</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Dataset Version</th>
                  <th className="py-3 px-4">Samples</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 font-sans text-gray-300">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="py-3 px-4 font-mono text-gray-400">{r.id.slice(0, 12)}...</td>
                    <td className="py-3 px-4 font-semibold text-white">{r.run_type}</td>
                    <td className="py-3 px-4 font-mono text-gray-400">{r.dataset_version}</td>
                    <td className="py-3 px-4 font-mono text-white">{r.sample_count}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-800">
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-400">
                      {new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
