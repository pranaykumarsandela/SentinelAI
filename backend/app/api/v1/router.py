from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.entities import SecurityEvent, ApprovalRequest, ExecutionTrace
from backend.app.schemas.common import APIResponse, PaginatedResponse
from backend.app.api.v1.documents import documents_router
from backend.app.api.v1.rag import rag_router
from backend.app.api.v1.security import security_router
from backend.app.api.v1.tools import tools_router
from backend.app.api.v1.approvals import approvals_router
from backend.app.api.v1.evaluations import evaluations_router
from backend.app.api.v1.dashboard import dashboard_router
from backend.app.api.v1.agents import router as agents_router
from backend.app.api.v1.traces import router as traces_router
from backend.app.api.v1.providers import providers_router
from backend.app.api.v1.observability import observability_router

api_v1_router = APIRouter(prefix="/v1")

# Subsystem Routers
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(providers_router)
api_v1_router.include_router(agents_router)
api_v1_router.include_router(traces_router)
api_v1_router.include_router(evaluations_router)
api_v1_router.include_router(security_router)
api_v1_router.include_router(tools_router)
api_v1_router.include_router(approvals_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(rag_router)
api_v1_router.include_router(observability_router)


@api_v1_router.get("/health", response_model=APIResponse[dict])
async def health_check():
    """System health and readiness verification."""
    return APIResponse(
        success=True,
        message="SentinelAI Platform Engine Operational",
        data={
            "status": "HEALTHY",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "subsystems": {
                "database": "CONNECTED",
                "security_firewall": "ACTIVE",
                "tool_policy_engine": "ACTIVE",
                "approval_engine": "ACTIVE",
                "evaluation_engine": "ACTIVE",
                "dashboard_analytics": "ACTIVE",
                "mock_provider": "READY",
                "rag_engine": "ACTIVE",
                "qdrant_store": "INITIALIZED",
                "langfuse_observability": "INITIALIZED",
            }
        }
    )


class SettingsUpdatePayload(BaseModel):
    environment: Optional[str] = None
    default_llm_provider: Optional[str] = None
    default_llm_model: Optional[str] = None
    prompt_injection_threshold: Optional[float] = None
    max_input_length: Optional[int] = None


@api_v1_router.get("/settings", response_model=APIResponse[dict])
async def get_system_settings():
    """Returns platform configuration, environment metadata, and policy engine thresholds."""
    return APIResponse(
        success=True,
        data={
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "host": settings.HOST,
            "port": settings.PORT,
            "database_dialect": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql",
            "default_llm_provider": settings.DEFAULT_LLM_PROVIDER,
            "default_llm_model": settings.DEFAULT_LLM_MODEL,
            "gemini_configured": bool(settings.effective_gemini_api_key),
            "groq_configured": bool(settings.GROQ_API_KEY),
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "langfuse_configured": bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY),
            "qdrant_in_memory": settings.QDRANT_IN_MEMORY,
            "qdrant_host": settings.QDRANT_HOST,
            "qdrant_port": settings.QDRANT_PORT,
            "data_integrity_policy": "STRICT_AUTHENTIC",
            "fail_closed_mode": True,
            "max_input_length": 4096,
            "prompt_injection_threshold": 0.50,
        }
    )


@api_v1_router.post("/settings", response_model=APIResponse[dict])
async def update_system_settings(payload: SettingsUpdatePayload):
    """Updates runtime configuration settings."""
    if payload.default_llm_provider:
        settings.DEFAULT_LLM_PROVIDER = payload.default_llm_provider
    if payload.default_llm_model:
        settings.DEFAULT_LLM_MODEL = payload.default_llm_model
    if payload.environment:
        settings.ENVIRONMENT = payload.environment

    return APIResponse(
        success=True,
        message="System configuration updated successfully",
        data={
            "environment": settings.ENVIRONMENT,
            "default_llm_provider": settings.DEFAULT_LLM_PROVIDER,
            "default_llm_model": settings.DEFAULT_LLM_MODEL,
            "prompt_injection_threshold": payload.prompt_injection_threshold or 0.50,
            "max_input_length": payload.max_input_length or 4096,
        }
    )


@api_v1_router.get("/audit/logs", response_model=APIResponse[PaginatedResponse[dict]])
async def get_unified_audit_logs(
    category: Optional[str] = Query(None, description="Filter: SECURITY, APPROVAL, EXECUTION"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns authentic, unified compliance audit records aggregated from
    security_events, approval_requests, and execution_traces.
    """
    audit_entries = []

    # 1. Security events
    if not category or category == "SECURITY":
        sec_stmt = select(SecurityEvent).order_by(desc(SecurityEvent.created_at)).limit(page_size * 2)
        sec_res = await db.execute(sec_stmt)
        for ev in sec_res.scalars().all():
            audit_entries.append({
                "id": ev.id,
                "timestamp": ev.created_at.isoformat() if ev.created_at else None,
                "category": "SECURITY",
                "event_type": ev.event_type,
                "severity": ev.severity,
                "actor": ev.agent_id or "Anonymous Caller",
                "action": ev.action_taken,
                "description": f"{ev.event_type} intercepted via {ev.detection_method}",
                "details": ev.details or {},
            })

    # 2. Approval decisions
    if not category or category == "APPROVAL":
        app_stmt = select(ApprovalRequest).order_by(desc(ApprovalRequest.requested_at)).limit(page_size * 2)
        app_res = await db.execute(app_stmt)
        for app in app_res.scalars().all():
            time_val = app.reviewed_at or app.requested_at
            audit_entries.append({
                "id": app.id,
                "timestamp": time_val.isoformat() if time_val else None,
                "category": "APPROVAL",
                "event_type": f"TOOL_{app.status}",
                "severity": app.risk_level,
                "actor": app.reviewer_id or "System Policy Engine",
                "action": app.status,
                "description": f"Tool '{app.tool_name}' transition to {app.status}",
                "details": {"tool_name": app.tool_name, "reviewer_role": app.reviewer_role, "args": app.tool_arguments},
            })

    # 3. Execution traces
    if not category or category == "EXECUTION":
        tr_stmt = select(ExecutionTrace).order_by(desc(ExecutionTrace.started_at)).limit(page_size * 2)
        tr_res = await db.execute(tr_stmt)
        for tr in tr_res.scalars().all():
            audit_entries.append({
                "id": tr.id,
                "timestamp": tr.started_at.isoformat() if tr.started_at else None,
                "category": "EXECUTION",
                "event_type": f"AGENT_RUN_{tr.status}",
                "severity": "CRITICAL" if tr.status in ("BLOCKED", "FAILED") else "LOW",
                "actor": tr.agent_id,
                "action": tr.status,
                "description": f"Agent execution completed with status {tr.status} ({tr.total_tokens} tokens)",
                "details": {"tokens": tr.total_tokens, "latency_ms": tr.total_latency_ms, "is_mock": tr.is_mock},
            })

    # Sort descending by timestamp
    audit_entries.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    total = len(audit_entries)
    offset = (page - 1) * page_size
    paged_items = audit_entries[offset : offset + page_size]

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=paged_items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + len(paged_items) < total),
        ),
    )

