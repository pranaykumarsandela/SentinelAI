import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid_str() -> str:
    return str(uuid.uuid4())


class ExecutionStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ERROR = "ERROR"


class SpanType(str, enum.Enum):
    GUARD_INPUT = "GUARD_INPUT"
    RETRIEVAL = "RETRIEVAL"
    LLM_CALL = "LLM_CALL"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    GUARD_OUTPUT = "GUARD_OUTPUT"


class SecurityEventType(str, enum.Enum):
    PROMPT_INJECTION = "PROMPT_INJECTION"
    JAILBREAK_ATTEMPT = "JAILBREAK_ATTEMPT"
    PII_DETECTED = "PII_DETECTED"
    UNAUTHORIZED_TOOL = "UNAUTHORIZED_TOOL"
    DATA_LEAK = "DATA_LEAK"
    APPROVAL_BYPASS = "APPROVAL_BYPASS"
    MALICIOUS_INSTRUCTION = "MALICIOUS_INSTRUCTION"
    INPUT_LENGTH_VIOLATION = "INPUT_LENGTH_VIOLATION"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    INDIRECT_PROMPT_INJECTION = "INDIRECT_PROMPT_INJECTION"


class SecuritySeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"


class RuleType(str, enum.Enum):
    TOOL_RESTRICTION = "TOOL_RESTRICTION"
    PROMPT_DENYLIST = "PROMPT_DENYLIST"
    REGEX_PATTERN = "REGEX_PATTERN"


class RuleAction(str, enum.Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


class EvaluationStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IngestionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --- Database Models ---

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    agents: Mapped[List["Agent"]] = relationship("Agent", back_populates="tenant", cascade="all, delete-orphan")
    policies: Mapped[List["SecurityPolicy"]] = relationship("SecurityPolicy", back_populates="tenant", cascade="all, delete-orphan")
    traces: Mapped[List["ExecutionTrace"]] = relationship("ExecutionTrace", back_populates="tenant", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    retrieval_events: Mapped[List["RetrievalEvent"]] = relationship("RetrievalEvent", back_populates="tenant", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_provider: Mapped[str] = mapped_column(String(50), default="mock")
    model_name: Mapped[str] = mapped_column(String(100), default="mock-sentinel-v1")
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="agents")
    traces: Mapped[List["ExecutionTrace"]] = relationship("ExecutionTrace", back_populates="agent", cascade="all, delete-orphan")
    evaluations: Mapped[List["EvaluationRun"]] = relationship("EvaluationRun", back_populates="agent", cascade="all, delete-orphan")


class SecurityPolicy(Base):
    __tablename__ = "security_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Policy thresholds
    prompt_injection_threshold: Mapped[float] = mapped_column(Float, default=0.75)
    jailbreak_block_level: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    pii_action: Mapped[str] = mapped_column(String(20), default="REDACT")  # BLOCK, REDACT, FLAG
    require_tool_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="policies")
    rules: Mapped[List["PolicyRule"]] = relationship("PolicyRule", back_populates="policy", cascade="all, delete-orphan")


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_policies.id", ondelete="CASCADE"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), default=RuleType.TOOL_RESTRICTION.value)
    target: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    action: Mapped[str] = mapped_column(String(30), default=RuleAction.REQUIRE_APPROVAL.value)

    policy: Mapped["SecurityPolicy"] = relationship("SecurityPolicy", back_populates="rules")


class ExecutionTrace(Base):
    __tablename__ = "execution_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    input_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sanitized_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String(30), default=ExecutionStatus.SUCCESS.value)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)  # Mandatory Data Integrity flag
    
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="traces")
    agent: Mapped["Agent"] = relationship("Agent", back_populates="traces")
    spans: Mapped[List["TraceSpan"]] = relationship("TraceSpan", back_populates="trace", cascade="all, delete-orphan")
    security_events: Mapped[List["SecurityEvent"]] = relationship("SecurityEvent", back_populates="trace", cascade="all, delete-orphan")
    approval_requests: Mapped[List["ApprovalRequest"]] = relationship("ApprovalRequest", back_populates="trace", cascade="all, delete-orphan")


class TraceSpan(Base):
    __tablename__ = "trace_spans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    trace_id: Mapped[str] = mapped_column(String(36), ForeignKey("execution_traces.id", ondelete="CASCADE"), nullable=False)
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    span_type: Mapped[str] = mapped_column(String(30), default=SpanType.LLM_CALL.value)
    
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="OK")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    trace: Mapped["ExecutionTrace"] = relationship("ExecutionTrace", back_populates="spans")


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("execution_traces.id", ondelete="CASCADE"), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    event_type: Mapped[str] = mapped_column(String(50), default=SecurityEventType.PROMPT_INJECTION.value)
    severity: Mapped[str] = mapped_column(String(20), default=SecuritySeverity.HIGH.value)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    detector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(50), default="DETERMINISTIC_HEURISTIC")
    
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    action_taken: Mapped[str] = mapped_column(String(20), default="BLOCKED")  # BLOCKED, REDACTED, LOGGED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    trace: Mapped[Optional["ExecutionTrace"]] = relationship("ExecutionTrace", back_populates="security_events")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("execution_traces.id", ondelete="CASCADE"), nullable=True)
    
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_arguments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="HIGH")
    
    status: Mapped[str] = mapped_column(String(20), default=ApprovalStatus.PENDING.value)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewer_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    trace: Mapped[Optional["ExecutionTrace"]] = relationship("ExecutionTrace", back_populates="approval_requests")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(20), default="v1.0")
    run_type: Mapped[str] = mapped_column(String(30), default="SECURITY")  # RAG, SECURITY, FULL
    model_identifier: Mapped[str] = mapped_column(String(100), default="mock-sentinel-v1")
    prompt_version: Mapped[str] = mapped_column(String(20), default="v1")
    
    total_samples: Mapped[int] = mapped_column(Integer, default=0)
    passed_samples: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=EvaluationStatus.RUNNING.value)
    
    # RAG Metrics
    faithfulness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    context_precision_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    context_recall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Security Metrics (Confusion Matrix & Derivatives)
    security_precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    security_recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    security_f1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    security_fpr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    security_robustness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confusion_matrix: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {TP, FP, TN, FN}
    
    errors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="evaluations")
    results: Mapped[List["EvaluationResult"]] = relationship("EvaluationResult", back_populates="evaluation_run", cascade="all, delete-orphan")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    evaluation_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    
    sample_id: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="GENERAL")
    input_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_behavior: Mapped[str] = mapped_column(String(100), nullable=False)
    actual_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    evaluation_run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="results")


# --- RAG Subsystem Models ---

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # PDF, TXT, MARKDOWN, DOCX
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    
    status: Mapped[str] = mapped_column(String(20), default=IngestionStatus.PENDING.value)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    doc_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_char: Mapped[int] = mapped_column(Integer, default=0)
    end_char: Mapped[int] = mapped_column(Integer, default=0)
    
    qdrant_point_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class RetrievalEvent(Base):
    __tablename__ = "retrieval_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    is_relevant: Mapped[bool] = mapped_column(Boolean, default=True)
    grader_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    groundedness_verdict: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # GROUNDED, UNGROUNDED, INSUFFICIENT_EVIDENCE
    
    retrieved_chunks: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Stores retrieved chunk IDs, documents, scores
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="retrieval_events")
