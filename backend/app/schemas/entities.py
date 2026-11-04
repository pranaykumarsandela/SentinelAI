from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# --- Tenant Schemas ---
class TenantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class TenantCreate(TenantBase):
    pass


class TenantRead(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    is_active: bool


# --- Agent Schemas ---
class AgentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    model_provider: str = Field(default="mock")
    model_name: str = Field(default="mock-sentinel-v1")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    system_prompt: Optional[str] = None


class AgentCreate(AgentBase):
    tenant_id: str


class AgentRead(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    created_at: datetime
    is_active: bool


# --- Policy Schemas ---
class PolicyRuleCreate(BaseModel):
    rule_type: str = "TOOL_RESTRICTION"
    target: str
    parameters: Optional[Dict[str, Any]] = None
    action: str = "REQUIRE_APPROVAL"


class PolicyRuleRead(PolicyRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str


class SecurityPolicyBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    is_default: bool = False
    prompt_injection_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    jailbreak_block_level: str = "MEDIUM"
    pii_action: str = "REDACT"
    require_tool_approval: bool = True


class SecurityPolicyCreate(SecurityPolicyBase):
    tenant_id: str
    rules: Optional[List[PolicyRuleCreate]] = []


class SecurityPolicyRead(SecurityPolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    created_at: datetime
    rules: List[PolicyRuleRead] = []


# --- Gateway Execution Schemas ---
class GatewayExecuteRequest(BaseModel):
    agent_id: str
    prompt: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    is_mock: bool = True  # Defaults to true; explicitly flags mock executions
    metadata: Optional[Dict[str, Any]] = None


class SecurityViolationItem(BaseModel):
    event_type: str
    severity: str
    confidence_score: float
    detector_name: str
    action_taken: str
    details: Optional[Dict[str, Any]] = None


class GatewayExecuteResponse(BaseModel):
    trace_id: str
    agent_id: str
    status: str  # SUCCESS, BLOCKED, PENDING_APPROVAL, ERROR
    output: Optional[str] = None
    sanitized_input: str
    is_mock: bool
    total_tokens: int
    total_latency_ms: float
    estimated_cost_usd: float
    violations: List[SecurityViolationItem] = []
    approval_id: Optional[str] = None


# --- Trace Schemas ---
class TraceSpanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    span_type: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    latency_ms: float
    tokens: int
    status: str
    created_at: datetime


class ExecutionTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    agent_id: str
    session_id: Optional[str] = None
    input_prompt: str
    sanitized_input: Optional[str] = None
    output_response: Optional[str] = None
    sanitized_output: Optional[str] = None
    status: str
    is_mock: bool
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_latency_ms: float
    estimated_cost_usd: float
    provider: Optional[str] = None
    model_name: Optional[str] = None
    fallback_occurred: Optional[bool] = False
    started_at: datetime
    completed_at: Optional[datetime] = None
    spans: List[TraceSpanRead] = []


# --- Approval Schemas ---
class ApprovalRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: str
    tool_name: str
    tool_arguments: Optional[Dict[str, Any]] = None
    risk_level: str
    status: str
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApprovalReviewAction(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    reviewer_id: str
    reviewer_notes: Optional[str] = None


