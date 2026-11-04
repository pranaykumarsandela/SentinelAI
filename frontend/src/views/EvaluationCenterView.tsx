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
  Award,
  TrendingDown,
} from 'lucide-react';
import { EvaluationRunItem, RegressionComparisonReport } from '../types';
import { api } from '../api/client';
import { EmptyState } from '../components/EmptyState';

export const EvaluationCenterView: React.FC = () => {
  const [runs, setRuns] = useState<EvaluationRunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningRagas, setRunningRagas] = useState(false);
  const [runningSecurity, setRunningSecurity] = useState(false);
  const [activeReport, setActiveReport] = useState<any | null>(null);

  // Regression Comparison State
  const [baselineRunId, setBaselineRunId] = useState<string>('');
  const [candidateRunId, setCandidateRunId] = useState<string>('');
  const [comparisonResult, setComparisonResult] = useState<RegressionComparisonReport | null>(null);
  const [comparing, setComparing] = useState(false);

  const loadRuns = async () => {
    try {
      setLoading(true);
      const data = await api.getEvaluationRuns();
      const items = (data as any)?.items || (Array.isArray(data) ? data : []);
      setRuns(items);
      if (items.length >= 2 && !baselineRunId && !candidateRunId) {
        setBaselineRunId(items[items.length - 1].id);
        setCandidateRunId(items[0].id);
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
            Evaluation Center & Regression Suite
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Automated RAGAS retrieval evaluations and adversarial security robustness benchmarks. Zero fabricated scores.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRunRagas}
            disabled={runningRagas || runningSecurity}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white disabled:opacity-50 transition-colors shadow-sm"
          >
            {runningRagas ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            Execute RAGAS Benchmark
          </button>
          <button
            onClick={handleRunSecurity}
            disabled={runningRagas || runningSecurity}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white disabled:opacity-50 transition-colors shadow-sm"
          >
            {runningSecurity ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Shield className="w-3.5 h-3.5" />}
            Execute Security Benchmark
          </button>
          <button
            onClick={loadRuns}
            disabled={loading}
            className="p-1.5 rounded-lg bg-gray-900 border border-gray-800 text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Latest Evaluation Scorecards */}
      {runs.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 block mb-1">
              Latest Faithfulness
            </span>
            <div className="text-xl font-bold font-mono text-white">
              {runs[0].faithfulness_score !== null ? `${(runs[0].faithfulness_score * 100).toFixed(1)}%` : 'N/A'}
            </div>
            <span className="text-[10px] text-gray-500">RAG claim groundedness</span>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 block mb-1">
              Latest Security Precision
            </span>
            <div className="text-xl font-bold font-mono text-emerald-400">
              {runs[0].security_precision !== null ? `${(runs[0].security_precision * 100).toFixed(1)}%` : 'N/A'}
            </div>
            <span className="text-[10px] text-gray-500">TP / (TP + FP)</span>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 block mb-1">
              Latest Security Recall
            </span>
            <div className="text-xl font-bold font-mono text-blue-400">
              {runs[0].security_recall !== null ? `${(runs[0].security_recall * 100).toFixed(1)}%` : 'N/A'}
            </div>
            <span className="text-[10px] text-gray-500">TP / (TP + FN)</span>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 block mb-1">
              Latest F1 Score
            </span>
            <div className="text-xl font-bold font-mono text-purple-400">
              {runs[0].security_f1 !== null ? `${(runs[0].security_f1 * 100).toFixed(1)}%` : 'N/A'}
            </div>
            <span className="text-[10px] text-gray-500">Harmonic mean</span>
          </div>
        </div>
      )}

      {/* Regression Comparison Section */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-800 pb-3">
          <div>
            <h3 className="text-xs font-semibold text-white flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-purple-400" />
              Differential Regression Comparison Engine
            </h3>
            <p className="text-[11px] text-gray-400 mt-0.5">
              Verify that candidate prompt updates or model changes do not cause security or retrieval regressions.
            </p>
          </div>

          <button
            onClick={handleCompare}
            disabled={comparing || !baselineRunId || !candidateRunId || baselineRunId === candidateRunId}
            className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors flex items-center gap-1.5"
          >
            {comparing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <GitCompare className="w-3.5 h-3.5" />}
            Compare Runs
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-[11px] text-gray-400 mb-1">Baseline Run (Reference)</label>
            <select
              value={baselineRunId}
              onChange={(e) => setBaselineRunId(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1.5 text-xs text-gray-200 font-mono"
            >
              <option value="">Select baseline run...</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.dataset_name} ({r.id.slice(0, 8)}) - {new Date(r.started_at).toLocaleTimeString()}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] text-gray-400 mb-1">Candidate Run (Evaluation)</label>
            <select
              value={candidateRunId}
              onChange={(e) => setCandidateRunId(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1.5 text-xs text-gray-200 font-mono"
            >
              <option value="">Select candidate run...</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.dataset_name} ({r.id.slice(0, 8)}) - {new Date(r.started_at).toLocaleTimeString()}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Comparison Report Output */}
        {comparisonResult && (
          <div className="p-4 bg-gray-950 border border-gray-800 rounded-xl space-y-3 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-gray-800 text-[11px] font-mono">
              <span className="text-gray-400">Dataset: <strong className="text-white">{comparisonResult.dataset_name}</strong></span>
              <span className={`px-2 py-0.5 rounded font-bold ${comparisonResult.total_regressions === 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'}`}>
                {comparisonResult.total_regressions === 0 ? 'PASSED: NO REGRESSIONS' : `${comparisonResult.total_regressions} REGRESSIONS DETECTED`}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-mono text-[11px]">
              <div className="p-2 bg-gray-900 rounded border border-gray-800">
                <span className="text-gray-500 text-[10px] block">FAITHFULNESS DELTA</span>
                <span className={comparisonResult.faithfulness_delta?.trend === 'IMPROVED' ? 'text-emerald-400' : 'text-gray-300'}>
                  {comparisonResult.faithfulness_delta?.absolute_delta !== null ? `${comparisonResult.faithfulness_delta.absolute_delta > 0 ? '+' : ''}${comparisonResult.faithfulness_delta.absolute_delta}` : 'N/A'}
                </span>
              </div>
              <div className="p-2 bg-gray-900 rounded border border-gray-800">
                <span className="text-gray-500 text-[10px] block">SECURITY PRECISION DELTA</span>
                <span className={comparisonResult.security_precision_delta?.trend === 'IMPROVED' ? 'text-emerald-400' : 'text-gray-300'}>
                  {comparisonResult.security_precision_delta?.absolute_delta !== null ? `${comparisonResult.security_precision_delta.absolute_delta > 0 ? '+' : ''}${comparisonResult.security_precision_delta.absolute_delta}` : 'N/A'}
                </span>
              </div>
              <div className="p-2 bg-gray-900 rounded border border-gray-800">
                <span className="text-gray-500 text-[10px] block">SECURITY RECALL DELTA</span>
                <span className={comparisonResult.security_recall_delta?.trend === 'IMPROVED' ? 'text-emerald-400' : 'text-gray-300'}>
                  {comparisonResult.security_recall_delta?.absolute_delta !== null ? `${comparisonResult.security_recall_delta.absolute_delta > 0 ? '+' : ''}${comparisonResult.security_recall_delta.absolute_delta}` : 'N/A'}
                </span>
              </div>
              <div className="p-2 bg-gray-900 rounded border border-gray-800">
                <span className="text-gray-500 text-[10px] block">RECOMMENDATION</span>
                <span className="text-white font-sans text-xs font-semibold">{comparisonResult.recommendation}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Historical Evaluation Runs Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <span className="text-xs font-semibold text-white">Persisted Evaluation Runs ({runs.length})</span>
          <span className="text-[11px] text-gray-400 font-mono">100% Calculated Authenticity</span>
        </div>

        {runs.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No evaluation runs recorded. Click "Execute RAGAS Benchmark" or "Execute Security Benchmark" above.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-950/70 text-gray-400 uppercase text-[10px] font-semibold border-b border-gray-800">
                <tr>
                  <th className="py-2.5 px-3">Run ID</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Dataset</th>
                  <th className="py-2.5 px-3">Samples</th>
                  <th className="py-2.5 px-3">Faithfulness</th>
                  <th className="py-2.5 px-3">Precision</th>
                  <th className="py-2.5 px-3">Recall</th>
                  <th className="py-2.5 px-3">F1</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 font-mono">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="py-2 px-3 text-blue-400 font-bold">{r.id.slice(0, 8)}...</td>
                    <td className="py-2 px-3 text-gray-300 font-semibold">{r.run_type}</td>
                    <td className="py-2 px-3 text-gray-400 text-[11px] truncate max-w-xs">{r.dataset_name}</td>
                    <td className="py-2 px-3 text-gray-300">
                      {r.passed_samples}/{r.total_samples}
                    </td>
                    <td className="py-2 px-3 text-gray-300">
                      {r.faithfulness_score !== null ? `${(r.faithfulness_score * 100).toFixed(0)}%` : 'N/A'}
                    </td>
                    <td className="py-2 px-3 text-gray-300">
                      {r.security_precision !== null ? `${(r.security_precision * 100).toFixed(0)}%` : 'N/A'}
                    </td>
                    <td className="py-2 px-3 text-gray-300">
                      {r.security_recall !== null ? `${(r.security_recall * 100).toFixed(0)}%` : 'N/A'}
                    </td>
                    <td className="py-2 px-3 text-gray-300">
                      {r.security_f1 !== null ? `${(r.security_f1 * 100).toFixed(0)}%` : 'N/A'}
                    </td>
                    <td className="py-2 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        {r.status}
                      </span>
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
