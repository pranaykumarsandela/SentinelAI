export interface DashboardMetrics {
  total_requests: number;
  successful_requests: number;
  blocked_requests: number;
  failed_requests: number;
  pending_approvals: number;
  execution_success_rate: number | null;
  blocked_request_rate: number | null;
  average_latency_ms: number;
  median_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost_usd: number;
  live_requests: number;
  mock_requests: number;
  is_fresh_install: boolean;
}

export interface SecurityEventItem {
  id: string;
  trace_id: string | null;
  request_id: string | null;
  agent_id: string | null;
  event_type: string;
  severity: string;
  confidence_score: number;
  detector_name: string;
  detection_method: string;
  action_taken: string;
  details: Record<string, any> | null;
  created_at: string;
}

export interface ApprovalRequestItem {
  id: string;
  trace_id: string;
  tool_name: string;
  tool_arguments: Record<string, any> | null;
  risk_level: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'EXECUTED';
  requested_at: string;
  expires_at: string | null;
  reviewed_at: string | null;
  reviewer_id: string | null;
  reviewer_role: string | null;
  rejection_reason: string | null;
}

export interface TraceSpanItem {
  id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: string;
  span_type: string;
  input_data: Record<string, any> | null;
  output_data: Record<string, any> | null;
  latency_ms: number;
  tokens: number;
  status: string;
  created_at: string;
}

export interface ExecutionTraceItem {
  id: string;
  tenant_id: string;
  agent_id: string;
  session_id: string | null;
  input_prompt: string;
  sanitized_input: string | null;
  output_response: string | null;
  sanitized_output: string | null;
  status: string;
  is_mock: boolean;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_latency_ms: number;
  estimated_cost_usd: number;
  started_at: string;
  completed_at: string | null;
  spans: TraceSpanItem[];
}

export interface DocumentItem {
  id: string;
  tenant_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface AgentItem {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  model_provider: string;
  model_name: string;
  temperature: number;
  system_prompt: string | null;
  created_at: string;
  is_active: boolean;
}

export interface GatewayExecutionResponse {
  trace_id: string;
  agent_id: string;
  status: 'SUCCESS' | 'BLOCKED' | 'PENDING_APPROVAL' | 'ERROR';
  output: string | null;
  sanitized_input: string;
  is_mock: boolean;
  total_tokens: number;
  total_latency_ms: number;
  estimated_cost_usd: number;
  violations: Array<{
    event_type: string;
    severity: string;
    confidence_score: number;
    detector_name: string;
    action_taken: string;
    details: Record<string, any> | null;
  }>;
  approval_id: string | null;
}

export interface EvaluationRunItem {
  id: string;
  agent_id: string | null;
  run_type: string;
  dataset_version: string;
  sample_count: number;
  status: string;
  metric_summary: Record<string, any> | null;
  created_at: string;
  completed_at: string | null;
}

