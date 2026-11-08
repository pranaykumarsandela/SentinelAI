from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.entities import ExecutionTrace
from backend.app.schemas.common import APIResponse, PaginatedResponse
from backend.app.observability.langfuse_service import (
    langfuse_service,
    mask_secret,
    to_langfuse_trace_id,
    LANGFUSE_SDK_AVAILABLE,
)

observability_router = APIRouter(prefix="/observability", tags=["Langfuse Observability"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class LangfuseStatusData(BaseModel):
    enabled: bool
    configured: bool
    status: str  # "HEALTHY" | "NOT_CONFIGURED" | "UNREACHABLE" | "DISABLED"
    host: str
    public_key_masked: str
    latency_ms: Optional[float] = None
    total_traces_exported: int
    total_failed_deliveries: int
    last_successful_delivery: Optional[str] = None
    message: str
    timestamp: float


class LangfuseConfigData(BaseModel):
    enabled: bool
    configured: bool
    host: str
    public_key_masked: str
    secret_key_masked: str
    timeout_seconds: float
    capture_input_output: bool
    sdk_available: bool
    sdk_version: Optional[str] = None


class LangfuseTraceItem(BaseModel):
    id: str
    langfuse_trace_id: str
    langfuse_url: Optional[str] = None
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
    started_at: datetime
    completed_at: Optional[datetime] = None


class LangfuseMetricsData(BaseModel):
    enabled: bool
    configured: bool
    is_operational: bool
    host: str
    total_traces_exported: int
    total_failed_deliveries: int
    delivery_success_rate: Optional[float] = None
    last_delivery_timestamp: Optional[str] = None
    last_error: Optional[str] = None


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@observability_router.get("/langfuse/status", response_model=APIResponse[LangfuseStatusData])
async def get_langfuse_status():
    """
    Returns live connectivity, authentication status, and export counters for Langfuse.
    Always returns structured health status without throwing uncaught exceptions.
    """
    health = await langfuse_service.health_check()
    data = LangfuseStatusData(
        enabled=health["enabled"],
        configured=health["configured"],
        status=health["status"],
        host=health["host"],
        public_key_masked=health["public_key_masked"],
        latency_ms=health.get("latency_ms"),
        total_traces_exported=langfuse_service.total_traces_exported,
        total_failed_deliveries=langfuse_service.total_failed_deliveries,
        last_successful_delivery=langfuse_service.last_successful_delivery,
        message=health["message"],
        timestamp=health["timestamp"],
    )
    return APIResponse(
        success=True,
        message=f"Langfuse observability status: {health['status']}",
        data=data,
    )


@observability_router.get("/langfuse/configuration", response_model=APIResponse[LangfuseConfigData])
async def get_langfuse_configuration():
    """
    Returns sanitized observability configuration and SDK metadata.
    Strict privacy policy: public and secret keys are always securely masked.
    """
    sdk_ver = None
    if LANGFUSE_SDK_AVAILABLE:
        try:
            import langfuse
            sdk_ver = getattr(langfuse, "__version__", "unknown")
        except Exception:
            sdk_ver = "unknown"

    data = LangfuseConfigData(
        enabled=langfuse_service.enabled,
        configured=langfuse_service.configured,
        host=langfuse_service.host,
        public_key_masked=mask_secret(langfuse_service.public_key),
        secret_key_masked=mask_secret(langfuse_service.secret_key),
        timeout_seconds=langfuse_service.timeout,
        capture_input_output=langfuse_service.capture_io,
        sdk_available=LANGFUSE_SDK_AVAILABLE,
        sdk_version=sdk_ver,
    )
    return APIResponse(
        success=True,
        message="Langfuse observability configuration retrieved successfully",
        data=data,
    )


@observability_router.post("/langfuse/test-connection", response_model=APIResponse[LangfuseStatusData])
async def test_langfuse_connection():
    """
    Triggers an immediate live authentication check against the configured Langfuse endpoint.
    Measures round-trip latency and validates API credentials.
    """
    health = await langfuse_service.health_check()
    data = LangfuseStatusData(
        enabled=health["enabled"],
        configured=health["configured"],
        status=health["status"],
        host=health["host"],
        public_key_masked=health["public_key_masked"],
        latency_ms=health.get("latency_ms"),
        total_traces_exported=langfuse_service.total_traces_exported,
        total_failed_deliveries=langfuse_service.total_failed_deliveries,
        last_successful_delivery=langfuse_service.last_successful_delivery,
        message=health["message"],
        timestamp=health["timestamp"],
    )
    is_success = (health["status"] == "HEALTHY")
    return APIResponse(
        success=is_success,
        message=health["message"],
        data=data,
    )


@observability_router.get("/langfuse/traces", response_model=APIResponse[PaginatedResponse[LangfuseTraceItem]])
async def list_langfuse_traces(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists execution traces from the PostgreSQL database, correlating each trace with
    its canonical 32-hex Langfuse trace ID and direct Langfuse dashboard deep-link.
    """
    offset = (page - 1) * page_size
    count_stmt = select(ExecutionTrace)
    count_res = await db.execute(count_stmt)
    total = len(count_res.scalars().all())

    stmt = (
        select(ExecutionTrace)
        .order_by(desc(ExecutionTrace.started_at))
        .offset(offset)
        .limit(page_size)
    )
    res = await db.execute(stmt)
    traces = res.scalars().all()

    items: List[LangfuseTraceItem] = []
    for t in traces:
        lf_id = to_langfuse_trace_id(t.id)
        lf_url = langfuse_service.get_trace_url(t.id) if langfuse_service.is_operational else None
        items.append(
            LangfuseTraceItem(
                id=t.id,
                langfuse_trace_id=lf_id,
                langfuse_url=lf_url,
                agent_id=t.agent_id,
                session_id=t.session_id,
                input_prompt=t.input_prompt,
                sanitized_input=t.sanitized_input,
                output_response=t.output_response,
                sanitized_output=t.sanitized_output,
                status=t.status,
                is_mock=t.is_mock,
                total_tokens=t.total_tokens,
                prompt_tokens=t.prompt_tokens,
                completion_tokens=t.completion_tokens,
                total_latency_ms=t.total_latency_ms,
                estimated_cost_usd=t.estimated_cost_usd,
                started_at=t.started_at,
                completed_at=t.completed_at,
            )
        )

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size < total),
        ),
    )


@observability_router.get("/langfuse/metrics", response_model=APIResponse[LangfuseMetricsData])
async def get_langfuse_metrics():
    """
    Returns authentic export and delivery metrics for the Langfuse telemetry pipeline.
    Zero fabricated numbers: derived strictly from recorded service counters.
    """
    total_exp = langfuse_service.total_traces_exported
    total_fail = langfuse_service.total_failed_deliveries
    total_attempts = total_exp + total_fail

    success_rate = None
    if total_attempts > 0:
        success_rate = round((total_exp / total_attempts) * 100, 2)

    data = LangfuseMetricsData(
        enabled=langfuse_service.enabled,
        configured=langfuse_service.configured,
        is_operational=langfuse_service.is_operational,
        host=langfuse_service.host,
        total_traces_exported=total_exp,
        total_failed_deliveries=total_fail,
        delivery_success_rate=success_rate,
        last_delivery_timestamp=langfuse_service.last_successful_delivery,
        last_error=langfuse_service.last_error,
    )
    return APIResponse(
        success=True,
        message="Langfuse observability metrics retrieved successfully",
        data=data,
    )
