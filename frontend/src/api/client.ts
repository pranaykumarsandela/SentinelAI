import {
  DashboardMetrics,
  SecurityEventItem,
  ApprovalRequestItem,
  ExecutionTraceItem,
  DocumentItem,
  AgentItem,
  GatewayExecutionResponse,
  EvaluationRunItem,
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
      }
    } catch {
      // fallback to status text
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export const api = {
  // Health
  getHealth: () => fetchJson<{ success: boolean; data: any }>(`${BASE_URL}/health`),

  // Dashboard Metrics
  getDashboardMetrics: (isMock?: boolean) => {
    const url = isMock !== undefined ? `${BASE_URL}/dashboard/metrics?is_mock=${isMock}` : `${BASE_URL}/dashboard/metrics`;
    return fetchJson<DashboardMetrics>(url);
  },

  // Security Events
  getSecurityEvents: (limit = 100) => fetchJson<SecurityEventItem[]>(`${BASE_URL}/security/events?limit=${limit}`),

  // Approvals
  getPendingApprovals: () => fetchJson<ApprovalRequestItem[]>(`${BASE_URL}/approvals/pending`),
  reviewApproval: (id: string, action: 'APPROVE' | 'REJECT', reviewerId = 'supervisor-1', reviewerNotes?: string) =>
    fetchJson<{ success: boolean; request_id: string; status: string }>(`${BASE_URL}/approvals/${id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        reviewer_id: reviewerId,
        reviewer_notes: reviewerNotes,
      }),
    }),

  // Agents
  getAgents: () => fetchJson<AgentItem[]>(`${BASE_URL}/agents`),
  createAgent: (agent: Partial<AgentItem> & { tenant_id: string; name: string }) =>
    fetchJson<AgentItem>(`${BASE_URL}/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(agent),
    }),
  executeAgent: (data: {
    agent_id: string;
    prompt: string;
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
        is_mock: data.is_mock ?? true,
      }),
    });
  },

  // Traces
  getTraces: (limit = 50, isMock?: boolean) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (isMock !== undefined) params.append('is_mock', String(isMock));
    return fetchJson<ExecutionTraceItem[]>(`${BASE_URL}/traces?${params.toString()}`);
  },
  getTrace: (id: string) => fetchJson<ExecutionTraceItem>(`${BASE_URL}/traces/${id}`),
  exportTrace: (id: string) => fetchJson<any>(`${BASE_URL}/traces/${id}/export`),

  // Documents (RAG)
  getDocuments: () => fetchJson<DocumentItem[]>(`${BASE_URL}/documents`),
  uploadDocument: (file: File, tenantId = 'default_tenant') => {
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
  queryRAG: (query: string, tenantId = 'default_tenant', topK = 3) =>
    fetchJson<any>(`${BASE_URL}/rag/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, tenant_id: tenantId, top_k: topK }),
    }),

  // Evaluations
  getEvaluationRuns: () => fetchJson<EvaluationRunItem[]>(`${BASE_URL}/evaluations/runs`),
  runRagasEvaluation: (datasetVersion = 'v1.0') =>
    fetchJson<{ run_id: string; status: string; metric_summary: any }>(`${BASE_URL}/evaluations/ragas/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_version: datasetVersion }),
    }),
  runSecurityBenchmark: (datasetVersion = 'v1.0') =>
    fetchJson<{ run_id: string; status: string; confusion_matrix: any }>(`${BASE_URL}/evaluations/security/benchmark`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_version: datasetVersion }),
    }),
  compareEvaluations: (baselineRunId: string, candidateRunId: string) =>
    fetchJson<any>(`${BASE_URL}/evaluations/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ baseline_run_id: baselineRunId, candidate_run_id: candidateRunId }),
    }),
};
