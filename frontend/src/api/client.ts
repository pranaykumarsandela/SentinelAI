import {
  DashboardMetrics,
  TimeseriesPoint,
  SecurityEventItem,
  ApprovalRequestItem,
  ExecutionTraceItem,
  DocumentItem,
  AgentItem,
  GatewayExecutionResponse,
  EvaluationRunItem,
  RegressionComparisonReport,
  ToolDefinitionItem,
  SecurityBenchmarkCaseItem,
  AuditLogEntry,
  SystemSettingsItem,
  RAGQueryResponse,
} from '../types';

const BASE_URL = '/api/v1';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const errObj = await res.json();
      if (errObj.detail) {
        errorDetail = typeof errObj.detail === 'string' ? errObj.detail : JSON.stringify(errObj.detail);
      } else if (errObj.message) {
        errorDetail = errObj.message;
      }
    } catch {
      // fallback to status text
    }
    throw new Error(errorDetail);
  }
  const body = await res.json();
  // Unwrap APIResponse wrapper if present: { success: boolean, data: T }
  if (body && typeof body === 'object' && 'success' in body && 'data' in body) {
    return body.data as T;
  }
  return body as T;
}

export const api = {
  // 1. Health
  getHealth: () => fetchJson<{ status: string; version: string; subsystems: Record<string, string> }>(`${BASE_URL}/health`),

  // 2. Dashboard Analytics & Real Time-series
  getDashboardMetrics: (environment = 'all', isMock?: boolean) => {
    const params = new URLSearchParams({ environment });
    if (isMock !== undefined) params.append('is_mock', String(isMock));
    return fetchJson<DashboardMetrics>(`${BASE_URL}/dashboard/metrics?${params.toString()}`);
  },
  getDashboardTimeseries: (environment = 'all', bucketHours = 1) => {
    const params = new URLSearchParams({ environment, bucket_hours: String(bucketHours) });
    return fetchJson<TimeseriesPoint[]>(`${BASE_URL}/dashboard/timeseries?${params.toString()}`);
  },

  // 3. Agents Management
  getAgents: (tenantId?: string) => {
    const params = new URLSearchParams();
    if (tenantId) params.append('tenant_id', tenantId);
    return fetchJson<AgentItem[]>(`${BASE_URL}/agents${params.toString() ? `?${params.toString()}` : ''}`);
  },
  createAgent: (agent: {
    tenant_id: string;
    name: string;
    description?: string;
    model_provider?: string;
    model_name?: string;
    temperature?: number;
    system_prompt?: string;
  }) =>
    fetchJson<AgentItem>(`${BASE_URL}/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(agent),
    }),
  getAgent: (id: string) => fetchJson<AgentItem>(`${BASE_URL}/agents/${id}`),
  executeAgent: (data: {
    agent_id: string;
    prompt: string;
    session_id?: string;
    is_mock?: boolean;
    role?: string;
    use_rag?: boolean;
    simulate_tool_call?: string;
  }) => {
    const params = new URLSearchParams();
    if (data.role) params.append('role', data.role);
    if (data.use_rag !== undefined) params.append('use_rag', String(data.use_rag));
    if (data.simulate_tool_call) params.append('simulate_tool_call', data.simulate_tool_call);

    const qs = params.toString() ? `?${params.toString()}` : '';
    return fetchJson<GatewayExecutionResponse>(`${BASE_URL}/agents/execute${qs}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_id: data.agent_id,
        prompt: data.prompt,
        session_id: data.session_id,
        is_mock: data.is_mock ?? true,
      }),
    });
  },

  // 4. Security Center & Real-time Inspection
  getSecurityEvents: (eventType?: string, severity?: string, page = 1, pageSize = 20) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (eventType && eventType !== 'ALL') params.append('event_type', eventType);
    if (severity && severity !== 'ALL') params.append('severity', severity);
    return fetchJson<{ items: SecurityEventItem[]; total: number; page: number; page_size: number }>(
      `${BASE_URL}/security/events?${params.toString()}`
    );
  },
  inspectInput: (payload: { text: string; pii_action?: string; prompt_injection_threshold?: number; max_length?: number }) =>
    fetchJson<any>(`${BASE_URL}/security/inspect-input`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  inspectOutput: (payload: { output_text: string; source_context_chunks?: string[]; require_grounding?: boolean }) =>
    fetchJson<any>(`${BASE_URL}/security/inspect-output`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // 5. RAG Explorer & Knowledge Base
  getDocuments: (tenantId = 'e2e_tenant', page = 1, pageSize = 50) => {
    const params = new URLSearchParams({ tenant_id: tenantId, page: String(page), page_size: String(pageSize) });
    return fetchJson<{ items: DocumentItem[]; total: number; page: number; page_size: number }>(
      `${BASE_URL}/documents?${params.toString()}`
    );
  },
  getDocument: (id: string, includeChunks = true) =>
    fetchJson<DocumentItem>(`${BASE_URL}/documents/${id}?include_chunks=${includeChunks}`),
  uploadDocument: (file: File, tenantId = 'e2e_tenant') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tenant_id', tenantId);
    return fetchJson<DocumentItem>(`${BASE_URL}/documents/upload`, {
      method: 'POST',
      body: formData,
    });
  },
  deleteDocument: (id: string) =>
    fetchJson<{ success: boolean; document_id: string }>(`${BASE_URL}/documents/${id}`, {
      method: 'DELETE',
    }),
  queryRAG: (query: string, tenantId = 'e2e_tenant', maxRetries = 2) =>
    fetchJson<RAGQueryResponse>(`${BASE_URL}/rag/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, tenant_id: tenantId, max_retries: maxRetries }),
    }),

  // 6. Execution Traces & Timeline
  getTraces: (agentId?: string, status?: string, isMock?: boolean, limit = 50, offset = 0) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (agentId) params.append('agent_id', agentId);
    if (status && status !== 'ALL') params.append('status', status);
    if (isMock !== undefined) params.append('is_mock', String(isMock));
    return fetchJson<ExecutionTraceItem[]>(`${BASE_URL}/traces?${params.toString()}`);
  },
  getTrace: (id: string) => fetchJson<ExecutionTraceItem>(`${BASE_URL}/traces/${id}`),
  exportTrace: (id: string) => fetchJson<any>(`${BASE_URL}/traces/${id}/export`),

  // 7. Tool Monitoring
  getTools: () => fetchJson<ToolDefinitionItem[]>(`${BASE_URL}/tools`),
  executeTool: (payload: {
    tool_name: string;
    arguments: Record<string, any>;
    user_role: string;
    agent_id?: string;
  }) =>
    fetchJson<any>(`${BASE_URL}/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // 8. Human Approvals Center
  getApprovals: (status?: string, page = 1, pageSize = 50) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status && status !== 'ALL') params.append('status', status);
    return fetchJson<{ items: ApprovalRequestItem[]; total: number; page: number; page_size: number }>(
      `${BASE_URL}/approvals?${params.toString()}`
    );
  },
  getPendingApprovals: (limit = 50) => fetchJson<ApprovalRequestItem[]>(`${BASE_URL}/approvals/pending?limit=${limit}`),
  getApproval: (id: string) => fetchJson<ApprovalRequestItem>(`${BASE_URL}/approvals/${id}`),
  reviewApproval: (
    id: string,
    action: 'APPROVE' | 'REJECT',
    reviewerId = 'supervisor-1',
    reviewerRole = 'supervisor',
    notes?: string
  ) =>
    fetchJson<ApprovalRequestItem>(`${BASE_URL}/approvals/${id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        reviewer_id: reviewerId,
        reviewer_role: reviewerRole,
        notes: notes || '',
      }),
    }),

  // 9. Evaluation Center
  getEvaluationRuns: (runType?: string, page = 1, pageSize = 50) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (runType && runType !== 'ALL') params.append('run_type', runType);
    return fetchJson<{ items: EvaluationRunItem[]; total: number; page: number; page_size: number }>(
      `${BASE_URL}/evaluations/runs?${params.toString()}`
    );
  },
  getEvaluationRun: (id: string) => fetchJson<EvaluationRunItem>(`${BASE_URL}/evaluations/runs/${id}`),
  runRagasEvaluation: (datasetVersion = 'v1.0', isMock = true) =>
    fetchJson<EvaluationRunItem>(`${BASE_URL}/evaluations/ragas/run?dataset_version=${datasetVersion}&is_mock=${isMock}`, {
      method: 'POST',
    }),
  runSecurityBenchmark: (datasetVersion = 'v1.0', isMock = true) =>
    fetchJson<EvaluationRunItem>(`${BASE_URL}/evaluations/security/benchmark?dataset_version=${datasetVersion}&is_mock=${isMock}`, {
      method: 'POST',
    }),
  compareEvaluations: (baselineRunId: string, candidateRunId: string) =>
    fetchJson<RegressionComparisonReport>(`${BASE_URL}/evaluations/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ baseline_run_id: baselineRunId, candidate_run_id: candidateRunId }),
    }),

  // 10. Red Team Lab
  getBenchmarkCases: () => fetchJson<SecurityBenchmarkCaseItem[]>(`${BASE_URL}/evaluations/benchmarks/cases`),

  // 11. Audit Logs
  getAuditLogs: (category?: string, page = 1, pageSize = 25) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (category && category !== 'ALL') params.append('category', category);
    return fetchJson<{ items: AuditLogEntry[]; total: number; page: number; page_size: number }>(
      `${BASE_URL}/audit/logs?${params.toString()}`
    );
  },

  // 12. Settings
  getSettings: () => fetchJson<SystemSettingsItem>(`${BASE_URL}/settings`),
  updateSettings: (payload: Partial<SystemSettingsItem>) =>
    fetchJson<SystemSettingsItem>(`${BASE_URL}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
};
