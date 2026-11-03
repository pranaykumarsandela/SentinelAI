from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.security.input_guard import SecurityVerdict, SecurityViolation
from backend.app.security.tool_registry import ToolPermissionLevel


class InputInspectRequest(BaseModel):
    text: str = Field(..., min_length=1)
    pii_action: str = Field(default="REDACT", pattern="^(BLOCK|REDACT|FLAG)$")
    prompt_injection_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    max_length: Optional[int] = Field(default=None, ge=1)


class OutputInspectRequest(BaseModel):
    output_text: str = Field(..., min_length=1)
    source_context_chunks: Optional[List[str]] = None
    expected_document_ids: Optional[List[str]] = None
    cited_document_ids: Optional[List[str]] = None
    require_grounding: bool = False


class SecurityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: Optional[str] = None
    request_id: Optional[str] = None
    agent_id: Optional[str] = None
    event_type: str
    severity: str
    confidence_score: float
    detector_name: str
    detection_method: str
    action_taken: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    user_role: str = Field(default="user")
    session_id: str = Field(default="default_session")
    agent_id: Optional[str] = None
    trace_id: Optional[str] = None
    approval_id: Optional[str] = None


class ToolExecuteResponse(BaseModel):
    status: str  # SUCCESS, PENDING_APPROVAL
    execution_mode: Optional[str] = None
    tool_name: Optional[str] = None
    approval_id: Optional[str] = None
    message: Optional[str] = None
    result: Optional[Any] = None


class ApprovalReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    reviewer_id: str = Field(..., min_length=1)
    reviewer_role: str = Field(..., min_length=1)
    notes: Optional[str] = None


class ApprovalRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: Optional[str] = None
    tool_name: str
    tool_arguments: Optional[Dict[str, Any]] = None
    risk_level: str
    status: str
    requested_at: datetime
    expires_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    rejection_reason: Optional[str] = None

