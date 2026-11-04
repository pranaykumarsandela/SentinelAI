import React, { useState, useEffect } from 'react';
import {
  Bot,
  Plus,
  Activity,
  Play,
  Settings,
  Shield,
  CheckCircle,
  AlertCircle,
  X,
  Send,
  Sliders,
} from 'lucide-react';
import { AgentItem, GatewayExecutionResponse } from '../types';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { EmptyState } from '../components/EmptyState';

interface AgentManagementViewProps {
  onNavigateToTrace?: (traceId: string) => void;
}

export const AgentManagementView: React.FC<AgentManagementViewProps> = ({ onNavigateToTrace }) => {
  const { user, hasPermission } = useAuth();
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Agent Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [modelProvider, setModelProvider] = useState('mock');
  const [modelName, setModelName] = useState('mock-sentinel-v1');
  const [temperature, setTemperature] = useState(0.2);
  const [systemPrompt, setSystemPrompt] = useState(
    'You are Sentinel Enterprise Agent. Adhere strictly to enterprise security policies and tool execution guardrails.'
  );
  const [creating, setCreating] = useState(false);

  // Test Drawer
  const [selectedAgent, setSelectedAgent] = useState<AgentItem | null>(null);
  const [testPrompt, setTestPrompt] = useState('Explain our enterprise data encryption standard.');
  const [testRole, setTestRole] = useState('user');
  const [useRag, setUseRag] = useState(true);
  const [isMock, setIsMock] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [testResult, setTestResult] = useState<GatewayExecutionResponse | null>(null);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getAgents();
      setAgents(data || []);
      if (data && data.length > 0 && !selectedAgent) {
        setSelectedAgent(data[0]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch registered agents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleCreateAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hasPermission('admin')) {
      alert('Only administrators can register production AI agents.');
      return;
    }
    try {
      setCreating(true);
      const newAgent = await api.createAgent({
        tenant_id: 'default_tenant',
        name,
        description: description || undefined,
        model_provider: modelProvider,
        model_name: modelName,
        temperature,
        system_prompt: systemPrompt,
      });
      setAgents([newAgent, ...agents]);
      setShowCreateModal(false);
      setName('');
      setDescription('');
    } catch (err: any) {
      alert(`Agent registration failed: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const handleExecuteTest = async () => {
    if (!selectedAgent) return;
    try {
      setExecuting(true);
      setTestResult(null);
      const resp = await api.executeAgent({
        agent_id: selectedAgent.id,
        prompt: testPrompt,
        role: testRole,
        use_rag: useRag,
        is_mock: isMock,
      });
      setTestResult(resp);
    } catch (err: any) {
      alert(`Execution failed: ${err.message}`);
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Bot className="w-5 h-5 text-blue-400" />
            Agent Management & Orchestration
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Register, inspect, and test enterprise AI agents enforced with LangGraph guardrails.
          </p>
        </div>

        {hasPermission('admin') && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            Register Agent
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-gray-500">
          <Activity className="w-5 h-5 animate-spin mr-2 text-blue-500" />
          <span className="text-xs">Loading agents from database...</span>
        </div>
      ) : error ? (
        <div className="p-4 bg-rose-950/40 border border-rose-500/30 rounded-xl text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      ) : agents.length === 0 ? (
        <EmptyState
          title="No AI Agents Registered"
          description="Register your first enterprise agent to enable LangGraph state-machine orchestration, guardrails, and RAG grounding."
          actionLabel={hasPermission('admin') ? 'Register Agent' : undefined}
          onAction={hasPermission('admin') ? () => setShowCreateModal(true) : undefined}
          icon={<Bot className="w-8 h-8 text-blue-400" />}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Agents List Cards */}
          <div className="lg:col-span-2 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {agents.map((ag) => {
                const isSelected = selectedAgent?.id === ag.id;
                return (
                  <div
                    key={ag.id}
                    onClick={() => setSelectedAgent(ag)}
                    className={`cursor-pointer p-4 rounded-xl border transition-all ${
                      isSelected
                        ? 'bg-blue-950/30 border-blue-500/50 shadow-lg shadow-blue-900/10'
                        : 'bg-gray-900/80 border-gray-800 hover:border-gray-700'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-xs">
                          <Bot className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-semibold text-white">{ag.name}</div>
                          <div className="text-[10px] text-gray-400 font-mono">{ag.id}</div>
                        </div>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-gray-800 text-gray-300">
                        {ag.model_provider}
                      </span>
                    </div>

                    <p className="text-[11px] text-gray-400 mt-2 line-clamp-2">
                      {ag.description || ag.system_prompt || 'Standard security agent.'}
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-gray-500 mt-3 pt-2 border-t border-gray-800/80 font-mono">
                      <span>Model: {ag.model_name}</span>
                      <span>Temp: {ag.temperature}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Test Playground Drawer */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <Play className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-semibold text-white">Agent Execution Playground</h3>
              </div>
              {selectedAgent && (
                <span className="text-[10px] font-mono text-blue-400 bg-blue-950/50 px-2 py-0.5 rounded border border-blue-800/40">
                  {selectedAgent.name}
                </span>
              )}
            </div>

            <div>
              <label className="block text-[11px] font-medium text-gray-300 mb-1">User Prompt</label>
              <textarea
                value={testPrompt}
                onChange={(e) => setTestPrompt(e.target.value)}
                rows={3}
                placeholder="Enter query or adversarial prompt..."
                className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="block text-[10px] text-gray-400 mb-1">Caller Role</label>
                <select
                  value={testRole}
                  onChange={(e) => setTestRole(e.target.value)}
                  className="w-full px-2 py-1.5 bg-gray-950 border border-gray-800 rounded text-xs text-gray-200"
                >
                  <option value="user">User</option>
                  <option value="support_agent">Support Agent</option>
                  <option value="supervisor">Supervisor</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] text-gray-400 mb-1">Environment</label>
                <div className="flex items-center gap-1.5 pt-1">
                  <input
                    type="checkbox"
                    id="mockCheck"
                    checked={isMock}
                    onChange={(e) => setIsMock(e.target.checked)}
                    className="rounded bg-gray-950 border-gray-800 text-blue-600"
                  />
                  <label htmlFor="mockCheck" className="text-[11px] text-gray-300 cursor-pointer">
                    Mock Mode (Safe)
                  </label>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="ragCheck"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
                className="rounded bg-gray-950 border-gray-800 text-blue-600"
              />
              <label htmlFor="ragCheck" className="text-xs text-gray-300 cursor-pointer">
                Retrieve grounding context from RAG
              </label>
            </div>

            <button
              onClick={handleExecuteTest}
              disabled={executing || !selectedAgent || !testPrompt}
              className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-2"
            >
              {executing ? (
                <>
                  <Activity className="w-3.5 h-3.5 animate-spin" />
                  Running through StateGraph...
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  Execute Agent Query
                </>
              )}
            </button>

            {/* Test Execution Result */}
            {testResult && (
              <div className="mt-4 p-3 bg-gray-950 border border-gray-800 rounded-lg space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      testResult.status === 'SUCCESS'
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : testResult.status === 'BLOCKED'
                        ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                        : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                    }`}
                  >
                    {testResult.status}
                  </span>
                  <span className="font-mono text-[10px] text-gray-400">
                    {testResult.total_latency_ms.toFixed(1)} ms | {testResult.total_tokens} tokens
                  </span>
                </div>

                {testResult.violations && testResult.violations.length > 0 && (
                  <div className="p-2 bg-rose-950/40 border border-rose-900/50 rounded text-rose-300 text-[11px]">
                    <div className="font-semibold text-rose-400">Threat Detected:</div>
                    <div>{testResult.violations[0].category || testResult.violations[0].event_type} ({testResult.violations[0].detector_name})</div>
                  </div>
                )}

                <div className="text-gray-300 text-xs font-mono bg-gray-900 p-2 rounded max-h-32 overflow-y-auto whitespace-pre-wrap">
                  {testResult.output || '(No response text produced)'}
                </div>

                {onNavigateToTrace && testResult.trace_id && (
                  <button
                    onClick={() => onNavigateToTrace(testResult.trace_id)}
                    className="text-[11px] text-blue-400 hover:underline flex items-center gap-1"
                  >
                    Inspect Full Span Waterfall &rarr;
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal: Create Agent */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-lg w-full space-y-4">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Bot className="w-4 h-4 text-blue-400" />
                Register New Enterprise Agent
              </h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateAgent} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Agent Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Sentinel Security Auditor"
                  className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Description</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Enforces cryptographic and tool execution standards"
                  className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-300 mb-1">Model Provider</label>
                  <select
                    value={modelProvider}
                    onChange={(e) => setModelProvider(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200"
                  >
                    <option value="mock">Deterministic Mock (Compliant)</option>
                    <option value="groq">Groq (Llama-3 / Mixtral)</option>
                    <option value="openai">OpenAI (GPT-4o / Mini)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-300 mb-1">Model Identifier</label>
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 font-mono"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs text-gray-300 mb-1">
                  <span>Temperature</span>
                  <span className="font-mono text-gray-400">{temperature}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">System Prompt Directives</label>
                <textarea
                  rows={3}
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !name}
                  className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                >
                  {creating ? 'Registering...' : 'Register Agent'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
