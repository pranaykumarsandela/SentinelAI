export type UserRole = 'admin' | 'supervisor' | 'analyst' | 'viewer';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  token?: string;
}

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

export interface TimeseriesPoint {
  timestamp: string;
  request_count: number;
  blocked_count: number;
  avg_latency_ms: number;
  total_tokens: number;
}

export interface SecurityEventItem {
  id: string;
  trace_id: string | null;
  request_id: string | null;
  agent_id: string | null;
  event_type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  confidence_score: number;
  detector_name: string;
  detection_method: string;
  action_taken: 'BLOCK' | 'REDACT' | 'FLAG' | 'ALLOW';
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
  status: 'SUCCESS' | 'BLOCKED' | 'PENDING_APPROVAL' | 'FAILED';
  is_mock: boolean;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_latency_ms: number;
  estimated_cost_usd: number;
  provider?: string | null;
  model_name?: string | null;
  fallback_occurred?: boolean;
  started_at: string;
  completed_at: string | null;
  spans?: TraceSpanItem[];
}

export interface DocumentChunkItem {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  page_number: number | null;
  start_char: number;
  end_char: number;
}

export interface DocumentItem {
  id: string;
  tenant_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  content_hash: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  chunk_count?: number;
  total_chunks?: number;
  total_tokens?: number;
  created_at: string;
  chunks?: DocumentChunkItem[];
}

export interface CitationItem {
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number: number | null;
  relevant_source_text: string;
}

export interface RAGQueryResponse {
  query: string;
  rewritten_query: string;
  retrieval_grade: string;
  groundedness_verdict: string;
  answer: string;
  citations: CitationItem[];
  step_count: number;
  retry_count: number;
  retrieval_event_id?: string;
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
  is_active?: boolean;
}

export interface GatewayExecutionResponse {
  trace_id: string;
  agent_id: string;
  status: 'SUCCESS' | 'BLOCKED' | 'PENDING_APPROVAL' | 'FAILED';
  output: string | null;
  sanitized_input: string;
  is_mock: boolean;
  total_tokens: number;
  total_latency_ms: number;
  estimated_cost_usd: number;
  violations: Array<{
    category?: string;
    event_type?: string;
    severity: string;
    confidence: number;
    confidence_score?: number;
    detector_name: string;
    detection_method?: string;
    action_taken?: string;
    details: Record<string, any> | null;
    remediation?: string;
  }>;
  approval_id: string | null;
}

export interface EvaluationRunItem {
  id: string;
  run_type: 'RAG' | 'SECURITY' | 'FULL';
  dataset_name: string;
  agent_id: string | null;
  is_mock: boolean;
  total_samples: number;
  passed_samples: number;
  failed_samples: number;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  faithfulness_score: number | null;
  relevance_score: number | null;
  context_precision_score: number | null;
  context_recall_score: number | null;
  security_precision: number | null;
  security_recall: number | null;
  security_f1: number | null;
  security_fpr: number | null;
  security_robustness_score: number | null;
  confusion_matrix: {
    true_positives: number;
    false_positives: number;
    true_negatives: number;
    false_negatives: number;
  } | null;
  started_at: string;
  completed_at: string | null;
}

export interface MetricDelta {
  baseline_value: number | null;
  candidate_value: number | null;
  absolute_delta: number | null;
  percentage_change: number | null;
  trend: 'IMPROVED' | 'REGRESSED' | 'UNCHANGED' | 'NOT_APPLICABLE';
}

export interface TestCaseRegressionItem {
  sample_id: string;
  category: string;
  input_prompt: string;
  baseline_status: string;
  candidate_status: string;
  status_change: 'NEW_REGRESSION' | 'NEW_FIX' | 'PERSISTENT_FAILURE';
}

export interface RegressionComparisonReport {
  baseline_run_id: string;
  candidate_run_id: string;
  dataset_name: string;
  is_dataset_compatible: boolean;
  model_configuration_changes: Record<string, any>;
  faithfulness_delta: MetricDelta;
  relevance_delta: MetricDelta;
  context_precision_delta: MetricDelta;
  context_recall_delta: MetricDelta;
  security_precision_delta: MetricDelta;
  security_recall_delta: MetricDelta;
  security_fpr_delta: MetricDelta;
  security_robustness_delta: MetricDelta;
  total_regressions: number;
  total_fixes: number;
  regressed_cases: TestCaseRegressionItem[];
  fixed_cases: TestCaseRegressionItem[];
  recommendation: string;
}

export interface ToolDefinitionItem {
  name: string;
  description: string;
  allowed_roles: string[];
  permission_level: 'READ_ONLY' | 'READ_WRITE' | 'ADMIN';
  requires_approval: boolean;
  timeout_seconds: number;
  max_executions_per_session: number;
  input_schema: Record<string, any>;
}

export interface SecurityBenchmarkCaseItem {
  case_id: string;
  input_text: string;
  attack_category: string;
  is_malicious: boolean;
  expected_action: string;
  description: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string | null;
  category: 'SECURITY' | 'APPROVAL' | 'EXECUTION';
  event_type: string;
  severity: string;
  actor: string;
  action: string;
  description: string;
  details: Record<string, any>;
}

export interface SystemSettingsItem {
  project_name: string;
  version: string;
  environment: string;
  debug: boolean;
  host: string;
  port: number;
  database_dialect: string;
  default_llm_provider: string;
  default_llm_model: string;
  gemini_configured?: boolean;
  groq_configured: boolean;
  openai_configured: boolean;
  langfuse_configured: boolean;
  qdrant_in_memory: boolean;
  qdrant_host: string;
  qdrant_port: number;
  data_integrity_policy: string;
  fail_closed_mode: boolean;
  max_input_length: number;
  prompt_injection_threshold: number;
}

export interface ProviderStatusItem {
  provider: string;
  display_name: string;
  is_configured: boolean;
  configured_model: string;
  supports_tools: boolean;
  supports_structured: boolean;
  supports_streaming: boolean;
}

export interface ProviderHealthCheckItem {
  provider: string;
  model: string;
  connected: boolean;
  status: 'HEALTHY' | 'UNREACHABLE' | 'NOT_CONFIGURED';
  latency_ms: number | null;
  message: string;
  timestamp: number;
}

export interface TaskRouteItem {
  provider: string;
  model: string;
}

export interface ModelRouterConfig {
  default_provider: string;
  default_model: string;
  task_routing: Record<string, TaskRouteItem>;
  fallback_chains: Record<string, TaskRouteItem[]>;
}

export interface DashboardProviderMetric {
  provider: string;
  requests: number;
  total_tokens: number;
  avg_latency_ms: number;
  errors: number;
  fallbacks: number;
}

export interface LLMBenchmarkResultItem {
  provider: string;
  model: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  success_rate: number;
  avg_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  total_prompt_tokens: number | null;
  total_completion_tokens: number | null;
  total_tokens: number | null;
  faithfulness_score: number | null;
  relevancy_score: number | null;
  total_cost_usd: number | null;
  pricing_data: Record<string, any> | null;
}

export interface LLMBenchmarkRunDetails {
  id: string;
  dataset_name: string;
  dataset_version: string;
  prompt_version: string;
  total_samples: number;
  status: string;
  pricing_source: string | null;
  pricing_version: string | null;
  started_at: string | null;
  completed_at: string | null;
  results: LLMBenchmarkResultItem[];
}
