import React, { useState, useEffect } from 'react';
import {
  Wrench,
  ShieldCheck,
  ShieldAlert,
  Play,
  Activity,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Lock,
  Clock,
  Terminal,
} from 'lucide-react';
import { ToolDefinitionItem } from '../types';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { EmptyState } from '../components/EmptyState';

export const ToolMonitoringView: React.FC = () => {
  const { user } = useAuth();
  const [tools, setTools] = useState<ToolDefinitionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tool execution testing sandbox
  const [selectedTool, setSelectedTool] = useState<ToolDefinitionItem | null>(null);
  const [callerRole, setCallerRole] = useState<string>(user.role);
  const [toolArgumentsJson, setToolArgumentsJson] = useState('{\n  "order_id": "ORD-1001",\n  "amount": 25.50\n}');
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<any | null>(null);

  const fetchTools = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getTools();
      setTools(data || []);
      if (data && data.length > 0 && !selectedTool) {
        setSelectedTool(data[0]);
        updateDefaultArgs(data[0]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch registered tools');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTools();
  }, []);

  const updateDefaultArgs = (tool: ToolDefinitionItem) => {
    if (tool.name === 'check_order_status') {
      setToolArgumentsJson('{\n  "order_id": "ORD-1001"\n}');
    } else if (tool.name === 'request_refund') {
      setToolArgumentsJson('{\n  "order_id": "ORD-1001",\n  "amount": 45.00,\n  "reason": "Damaged goods on arrival"\n}');
    } else if (tool.name === 'search_documents') {
      setToolArgumentsJson('{\n  "query": "data retention policy"\n}');
    } else if (tool.name === 'retrieve_document') {
      setToolArgumentsJson('{\n  "document_id": "doc_001"\n}');
    } else if (tool.name === 'create_support_ticket') {
      setToolArgumentsJson('{\n  "customer_email": "client@enterprise.com",\n  "subject": "API connectivity issue",\n  "priority": "HIGH"\n}');
    } else {
      setToolArgumentsJson('{}');
    }
  };

  const handleSelectTool = (tool: ToolDefinitionItem) => {
    setSelectedTool(tool);
    setExecutionResult(null);
    updateDefaultArgs(tool);
  };

  const handleExecuteTool = async () => {
    if (!selectedTool) return;
    try {
      setExecuting(true);
      setExecutionResult(null);
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(toolArgumentsJson);
      } catch {
        alert('Invalid JSON in tool arguments.');
        return;
      }

      const res = await api.executeTool({
        tool_name: selectedTool.name,
        arguments: parsedArgs,
        user_role: callerRole,
      });
      setExecutionResult(res);
    } catch (err: any) {
      setExecutionResult({
        status: 'FORBIDDEN',
        message: err.message || 'Policy violation blocked execution.',
      });
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Wrench className="w-5 h-5 text-blue-400" />
            Centralized Tool Registry & Policy Monitoring
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Enforces server-side tool authorization, schema validation, allowed roles, and Human-in-the-Loop review triggers.
          </p>
        </div>

        <button
          onClick={fetchTools}
          disabled={loading}
          className="p-1.5 bg-gray-900 border border-gray-800 text-gray-400 hover:text-white rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-blue-500" />
          Loading tool registry from backend...
        </div>
      ) : error ? (
        <div className="p-4 bg-rose-950/40 border border-rose-500/30 rounded-xl text-rose-300 text-xs">
          {error}
        </div>
      ) : tools.length === 0 ? (
        <EmptyState
          title="No Tools Registered"
          description="The tool registry currently reports 0 registered tools."
          icon={<Wrench className="w-8 h-8 text-blue-400" />}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Tools List (2 cols) */}
          <div className="lg:col-span-2 space-y-3">
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-gray-800 flex items-center justify-between">
                <span className="text-xs font-semibold text-white">Registered Enterprise Tools ({tools.length})</span>
                <span className="text-[11px] text-gray-400 font-mono">Server-side Enforced</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-gray-950/70 text-gray-400 uppercase text-[10px] font-semibold border-b border-gray-800">
                    <tr>
                      <th className="py-2.5 px-3">Tool Name</th>
                      <th className="py-2.5 px-3">Risk Tier</th>
                      <th className="py-2.5 px-3">Allowed Roles</th>
                      <th className="py-2.5 px-3">Approval Gate</th>
                      <th className="py-2.5 px-3">Timeout</th>
                      <th className="py-2.5 px-3 text-right">Select</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60 font-mono">
                    {tools.map((t) => {
                      const isSelected = selectedTool?.name === t.name;
                      return (
                        <tr
                          key={t.name}
                          onClick={() => handleSelectTool(t)}
                          className={`cursor-pointer transition-colors ${
                            isSelected ? 'bg-blue-950/30 text-white' : 'hover:bg-gray-800/30 text-gray-300'
                          }`}
                        >
                          <td className="py-2.5 px-3 font-semibold text-blue-400">
                            {t.name}
                          </td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                t.permission_level === 'ADMIN'
                                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                                  : t.permission_level === 'READ_WRITE'
                                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                              }`}
                            >
                              {t.permission_level}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-gray-400 text-[11px]">
                            {t.allowed_roles.join(', ')}
                          </td>
                          <td className="py-2.5 px-3">
                            {t.requires_approval ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/60 text-amber-300 border border-amber-800/50">
                                REQUIRED (HITL)
                              </span>
                            ) : (
                              <span className="text-gray-500 text-[11px]">Automatic</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-gray-400 text-[11px]">
                            {t.timeout_seconds}s
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSelectTool(t);
                              }}
                              className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                                isSelected ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                              }`}
                            >
                              Test
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {selectedTool && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between text-xs text-gray-400 font-mono">
                  <span className="font-semibold text-white">{selectedTool.name} Input Schema</span>
                  <span>Max {selectedTool.max_executions_per_session} calls/session</span>
                </div>
                <pre className="p-3 bg-gray-950 border border-gray-800 rounded-lg text-[11px] font-mono text-gray-300 overflow-x-auto max-h-40">
                  {JSON.stringify(selectedTool.input_schema || {}, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* Tool Policy & Authorization Sandbox (1 col) */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-semibold text-white">Policy Enforcement Sandbox</h3>
              </div>
              {selectedTool && (
                <span className="text-[10px] font-mono text-blue-400 bg-blue-950 px-2 py-0.5 rounded border border-blue-900">
                  {selectedTool.name}
                </span>
              )}
            </div>

            <div>
              <label className="block text-[11px] font-medium text-gray-300 mb-1">Simulated Caller Role</label>
              <select
                value={callerRole}
                onChange={(e) => setCallerRole(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-gray-950 border border-gray-800 rounded text-xs text-gray-200 font-mono"
              >
                <option value="user">User (Lowest Privilege)</option>
                <option value="support_agent">Support Agent</option>
                <option value="supervisor">Supervisor</option>
                <option value="admin">Administrator (Full Privilege)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-gray-300 mb-1">Tool Arguments (JSON)</label>
              <textarea
                value={toolArgumentsJson}
                onChange={(e) => setToolArgumentsJson(e.target.value)}
                rows={5}
                className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <button
              onClick={handleExecuteTool}
              disabled={executing || !selectedTool}
              className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-2"
            >
              {executing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Evaluating Server-Side Policies...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  Evaluate & Execute Tool
                </>
              )}
            </button>

            {/* Execution Result */}
            {executionResult && (
              <div className="p-3 bg-gray-950 border border-gray-800 rounded-lg space-y-2 text-xs">
                <div className="flex items-center justify-between font-mono text-[11px]">
                  <span className="text-gray-400">Status:</span>
                  <span
                    className={`font-bold px-1.5 py-0.5 rounded ${
                      executionResult.status === 'SUCCESS' || executionResult.execution_status === 'EXECUTED'
                        ? 'bg-emerald-500/15 text-emerald-400'
                        : executionResult.status === 'PENDING_APPROVAL' || executionResult.approval_id
                        ? 'bg-amber-500/15 text-amber-400'
                        : 'bg-rose-500/15 text-rose-400'
                    }`}
                  >
                    {executionResult.status || executionResult.execution_status}
                  </span>
                </div>

                {executionResult.approval_id && (
                  <div className="p-2 bg-amber-950/40 border border-amber-800/40 rounded text-amber-300 text-[11px]">
                    <div className="font-semibold text-amber-400">HITL Approval Required:</div>
                    <div>Created approval ID: <span className="font-mono">{executionResult.approval_id}</span></div>
                  </div>
                )}

                <div className="p-2 bg-gray-900 rounded font-mono text-gray-300 text-[11px] max-h-36 overflow-y-auto whitespace-pre-wrap">
                  {JSON.stringify(executionResult, null, 2)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
