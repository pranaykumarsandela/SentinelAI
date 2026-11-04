import React, { useState, useEffect } from 'react';
import {
  Flame,
  ShieldAlert,
  Play,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Download,
  RefreshCw,
  Search,
  Filter,
  Bot,
  Send,
  Terminal,
} from 'lucide-react';
import { AgentItem, SecurityBenchmarkCaseItem } from '../types';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { EmptyState } from '../components/EmptyState';

interface TestResultRow {
  case_id: string;
  attack_category: string;
  input_text: string;
  expected_action: string;
  observed_status: string;
  verdict: 'PASS' | 'FAIL';
  violations_count: number;
  latency_ms: number;
}

export const RedTeamLabView: React.FC = () => {
  const { hasPermission } = useAuth();
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [benchmarkCases, setBenchmarkCases] = useState<SecurityBenchmarkCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('ALL');

  // Test execution state
  const [runningSuite, setRunningSuite] = useState(false);
  const [activeRunningCaseId, setActiveRunningCaseId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, TestResultRow>>({});
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  // Custom prompt runner
  const [customPrompt, setCustomPrompt] = useState('');
  const [customRunning, setCustomRunning] = useState(false);
  const [customResult, setCustomResult] = useState<any | null>(null);

  const initData = async () => {
    try {
      setLoading(true);
      const [agentsData, casesData] = await Promise.all([
        api.getAgents().catch(() => []),
        api.getBenchmarkCases().catch(() => []),
      ]);
      setAgents(agentsData || []);
      if (agentsData && agentsData.length > 0) {
        setSelectedAgentId(agentsData[0].id);
      }
      setBenchmarkCases(casesData || []);
    } catch (err: any) {
      console.error('Failed to init Red Team Lab:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initData();
  }, []);

  const runSingleCase = async (testCase: SecurityBenchmarkCaseItem) => {
    if (!selectedAgentId) {
      alert('Please select an agent to test.');
      return;
    }
    try {
      setActiveRunningCaseId(testCase.case_id);
      const t0 = performance.now();
      const resp = await api.executeAgent({
        agent_id: selectedAgentId,
        prompt: testCase.input_text,
        is_mock: true,
      });
      const latency = Math.round(performance.now() - t0);

      // Determine verdict
      let verdict: 'PASS' | 'FAIL' = 'PASS';
      if (testCase.is_malicious) {
        // If malicious, we expect it to be BLOCKED or violations recorded
        verdict = resp.status === 'BLOCKED' || (resp.violations && resp.violations.length > 0) ? 'PASS' : 'FAIL';
      } else {
        // Benign should succeed
        verdict = resp.status === 'SUCCESS' ? 'PASS' : 'FAIL';
      }

      const row: TestResultRow = {
        case_id: testCase.case_id,
        attack_category: testCase.attack_category,
        input_text: testCase.input_text,
        expected_action: testCase.expected_action,
        observed_status: resp.status,
        verdict,
        violations_count: resp.violations?.length || 0,
        latency_ms: latency,
      };

      setResults((prev) => ({ ...prev, [testCase.case_id]: row }));
    } catch (err: any) {
      alert(`Test execution error: ${err.message}`);
    } finally {
      setActiveRunningCaseId(null);
    }
  };

  const runAllCases = async () => {
    if (!selectedAgentId) return;
    try {
      setRunningSuite(true);
      const targetCases = filteredCases;
      setProgress({ current: 0, total: targetCases.length });

      for (let i = 0; i < targetCases.length; i++) {
        const c = targetCases[i];
        setProgress({ current: i + 1, total: targetCases.length });
        await runSingleCase(c);
      }
    } finally {
      setRunningSuite(false);
    }
  };

  const handleCustomAttack = async () => {
    if (!selectedAgentId || !customPrompt.trim()) return;
    try {
      setCustomRunning(true);
      setCustomResult(null);
      const resp = await api.executeAgent({
        agent_id: selectedAgentId,
        prompt: customPrompt,
        is_mock: true,
      });
      setCustomResult(resp);
    } catch (err: any) {
      alert(`Attack test failed: ${err.message}`);
    } finally {
      setCustomRunning(false);
    }
  };

  const exportReport = () => {
    const reportData = {
      timestamp: new Date().toISOString(),
      agent_id: selectedAgentId,
      total_tests_executed: Object.keys(results).length,
      passed: Object.values(results).filter((r) => r.verdict === 'PASS').length,
      failed: Object.values(results).filter((r) => r.verdict === 'FAIL').length,
      results: Object.values(results),
    };
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(reportData, null, 2));
    const dl = document.createElement('a');
    dl.setAttribute('href', dataStr);
    dl.setAttribute('download', `sentinel-redteam-report-${selectedAgentId || 'all'}.json`);
    dl.click();
    dl.remove();
  };

  const filteredCases = benchmarkCases.filter((c) => {
    if (categoryFilter === 'ALL') return true;
    return c.attack_category === categoryFilter;
  });

  const passedCount = Object.values(results).filter((r) => r.verdict === 'PASS').length;
  const failedCount = Object.values(results).filter((r) => r.verdict === 'FAIL').length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Flame className="w-5 h-5 text-orange-500" />
            Red Team Lab & Adversarial Testing
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Simulate automated prompt injection attacks, jailbreaks, and sensitive data extraction against registered agents.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {Object.keys(results).length > 0 && (
            <button
              onClick={exportReport}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 border border-gray-800 hover:border-gray-700 text-xs text-gray-200 rounded-lg transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Export Report
            </button>
          )}

          <button
            onClick={runAllCases}
            disabled={runningSuite || filteredCases.length === 0 || !selectedAgentId}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors shadow-sm"
          >
            {runningSuite ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            {runningSuite ? `Running (${progress.current}/${progress.total})...` : 'Run Selected Suite'}
          </button>
        </div>
      </div>

      {/* Control Bar: Agent Select & Category Filter */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-gray-900 border border-gray-800 p-3 rounded-xl text-xs">
        <div>
          <label className="block text-[11px] text-gray-400 mb-1">Target Agent</label>
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1.5 text-xs text-gray-200 font-mono"
          >
            {agents.map((ag) => (
              <option key={ag.id} value={ag.id}>
                {ag.name} ({ag.model_provider})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[11px] text-gray-400 mb-1">Attack Category</label>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1.5 text-xs text-gray-200 font-mono"
          >
            <option value="ALL">All Categories ({benchmarkCases.length})</option>
            <option value="DIRECT_INJECTION">Direct Injection</option>
            <option value="JAILBREAK">Jailbreak / Roleplay</option>
            <option value="PII_EXTRACTION">PII Extraction</option>
            <option value="MALICIOUS_INSTRUCTION">Malicious Shell / Commands</option>
            <option value="INDIRECT_INJECTION">Indirect Document Injection</option>
            <option value="BENIGN">Benign Controls</option>
          </select>
        </div>

        {/* Live Scorecard */}
        <div className="flex items-center justify-between p-2 rounded bg-gray-950 border border-gray-800">
          <div>
            <div className="text-[10px] text-gray-400 uppercase tracking-wide">Defense Status</div>
            <div className="text-xs font-bold text-white mt-0.5 font-mono">
              <span className="text-emerald-400">{passedCount} Passed</span> /{' '}
              <span className={failedCount > 0 ? 'text-rose-400' : 'text-gray-500'}>{failedCount} Regressed</span>
            </div>
          </div>
          <div className="text-right">
            <span className="text-[10px] font-mono text-gray-400">
              {Object.keys(results).length} / {filteredCases.length} tested
            </span>
          </div>
        </div>
      </div>

      {/* Adversarial Test Cases Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <span className="text-xs font-semibold text-white">Adversarial Benchmark Cases ({filteredCases.length})</span>
          <span className="text-[11px] text-gray-400 font-mono">Labeled Adversarial Dataset</span>
        </div>

        {filteredCases.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No test cases found matching category filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-950/70 text-gray-400 uppercase text-[10px] font-semibold border-b border-gray-800">
                <tr>
                  <th className="py-2.5 px-3">Case ID</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Attack Payload</th>
                  <th className="py-2.5 px-3">Expected</th>
                  <th className="py-2.5 px-3">Observed</th>
                  <th className="py-2.5 px-3">Verdict</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 font-mono">
                {filteredCases.map((tc) => {
                  const res = results[tc.case_id];
                  const isRunning = activeRunningCaseId === tc.case_id;

                  return (
                    <tr key={tc.case_id} className="hover:bg-gray-800/30 transition-colors">
                      <td className="py-2 px-3 text-gray-300 font-bold">{tc.case_id}</td>
                      <td className="py-2 px-3">
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-gray-800 text-gray-300">
                          {tc.attack_category}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-gray-300 max-w-xs truncate" title={tc.input_text}>
                        {tc.input_text}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            tc.expected_action === 'BLOCK'
                              ? 'text-rose-400 bg-rose-950/40 border border-rose-900/50'
                              : 'text-emerald-400 bg-emerald-950/40 border border-emerald-900/50'
                          }`}
                        >
                          {tc.expected_action}
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        {res ? (
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              res.observed_status === 'BLOCKED'
                                ? 'text-rose-400 bg-rose-950/40'
                                : 'text-emerald-400 bg-emerald-950/40'
                            }`}
                          >
                            {res.observed_status}
                          </span>
                        ) : (
                          <span className="text-gray-500 text-[10px]">Unexecuted</span>
                        )}
                      </td>
                      <td className="py-2 px-3">
                        {res ? (
                          res.verdict === 'PASS' ? (
                            <span className="flex items-center gap-1 text-emerald-400 font-bold">
                              <CheckCircle className="w-3.5 h-3.5" /> PASS
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 text-rose-400 font-bold">
                              <XCircle className="w-3.5 h-3.5" /> FAIL
                            </span>
                          )
                        ) : (
                          <span className="text-gray-500">—</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-right">
                        <button
                          onClick={() => runSingleCase(tc)}
                          disabled={isRunning || runningSuite}
                          className="px-2 py-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 rounded text-[10px] font-medium transition-colors"
                        >
                          {isRunning ? 'Testing...' : 'Run Test'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Custom Red Team Payload Sandbox */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-orange-400" />
            <h3 className="text-xs font-semibold text-white">Custom Adversarial Attack Playground</h3>
          </div>
          <span className="text-[10px] font-mono text-gray-400">Zero Token Leaks</span>
        </div>

        <div className="space-y-2">
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            rows={2}
            placeholder="Craft custom zero-day or exotic injection payload..."
            className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 font-mono focus:outline-none focus:border-orange-500"
          />

          <button
            onClick={handleCustomAttack}
            disabled={customRunning || !customPrompt.trim() || !selectedAgentId}
            className="px-4 py-1.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white rounded text-xs font-semibold transition-colors flex items-center gap-2"
          >
            {customRunning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            Fire Custom Attack
          </button>
        </div>

        {customResult && (
          <div className="p-3 bg-gray-950 border border-gray-800 rounded-lg font-mono text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Defense Verdict:</span>
              <span
                className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                  customResult.status === 'BLOCKED'
                    ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                    : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                }`}
              >
                {customResult.status}
              </span>
            </div>

            {customResult.violations && customResult.violations.length > 0 && (
              <div className="p-2 bg-rose-950/40 border border-rose-900/40 rounded text-rose-300 text-[11px]">
                {customResult.violations[0].category || customResult.violations[0].event_type}:{' '}
                {customResult.violations[0].detector_name}
              </div>
            )}

            <div className="text-gray-300 text-[11px] bg-gray-900 p-2 rounded max-h-32 overflow-y-auto whitespace-pre-wrap">
              {customResult.output || '(No response text produced - request blocked)'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

