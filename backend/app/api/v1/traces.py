from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.models.entities import ExecutionTrace, TraceSpan
from backend.app.schemas.entities import ExecutionTraceRead
from backend.app.observability.langfuse_exporter import langfuse_exporter

router = APIRouter(prefix="/traces", tags=["Observability & Traces"])


@router.get("", response_model=List[ExecutionTraceRead])
async def list_traces(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    status: Optional[str] = Query(None, description="Filter by status: SUCCESS, BLOCKED, PENDING_APPROVAL, FAILED"),
    is_mock: Optional[bool] = Query(None, description="Filter by mock vs live executions"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List persisted execution traces in reverse chronological order.
    Returns authentic database records conforming to the Mandatory Data Integrity Policy.
    """
    query = (
        select(ExecutionTrace)
        .options(selectinload(ExecutionTrace.spans))
        .order_by(desc(ExecutionTrace.started_at))
        .limit(limit)
        .offset(offset)
    )

    if agent_id:
        query = query.where(ExecutionTrace.agent_id == agent_id)
    if tenant_id:
        query = query.where(ExecutionTrace.tenant_id == tenant_id)
    if status:
        query = query.where(ExecutionTrace.status == status)
    if is_mock is not None:
        query = query.where(ExecutionTrace.is_mock == is_mock)

    result = await db.execute(query)
    traces = result.scalars().all()
    return traces


@router.get("/{trace_id}", response_model=ExecutionTraceRead)
async def get_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve complete execution trace including all child execution spans."""
    query = (
        select(ExecutionTrace)
        .options(selectinload(ExecutionTrace.spans))
        .where(ExecutionTrace.id == trace_id)
    )
    result = await db.execute(query)
    trace = result.scalars().first()

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution trace '{trace_id}' not found.",
        )
    return trace


@router.get("/{trace_id}/export")
async def export_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Export trace in OpenTelemetry / Langfuse compatible JSON schema.
    Suitable for external observability collectors.
    """
    query = (
        select(ExecutionTrace)
        .options(selectinload(ExecutionTrace.spans))
        .where(ExecutionTrace.id == trace_id)
    )
    result = await db.execute(query)
    trace = result.scalars().first()

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution trace '{trace_id}' not found.",
        )

    return langfuse_exporter.format_trace_for_export(trace, trace.spans)
