from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.models.entities import SecurityEvent
from backend.app.schemas.common import APIResponse, PaginatedResponse
from backend.app.schemas.security import (
    InputInspectRequest,
    OutputInspectRequest,
    SecurityEventRead,
)
from backend.app.security.input_guard import input_security_guard, InputInspectionResult
from backend.app.security.output_guard import output_guard, OutputInspectionResult

security_router = APIRouter(prefix="/security", tags=["Security Firewall"])


@security_router.post("/inspect-input", response_model=APIResponse[InputInspectionResult])
async def inspect_input(payload: InputInspectRequest):
    """
    Real-time deterministic pre-execution guardrail inspection.
    Scans for Prompt Injection, Jailbreaks, PII, Obfuscated Code, and Length Violations.
    """
    result = input_security_guard.inspect_input(
        text=payload.text,
        pii_action=payload.pii_action,
        prompt_injection_threshold=payload.prompt_injection_threshold,
        max_length=payload.max_length,
    )
    return APIResponse(
        success=True,
        message="Input inspected successfully",
        data=result
    )


@security_router.post("/inspect-output", response_model=APIResponse[OutputInspectionResult])
async def inspect_output(payload: OutputInspectRequest):
    """
    Egress output validation and sensitive data scrubbing.
    Verifies PII redaction, citation authenticity, and claim groundedness.
    """
    expected_set = set(payload.expected_document_ids) if payload.expected_document_ids else None
    result = output_guard.inspect_output(
        output_text=payload.output_text,
        source_context_chunks=payload.source_context_chunks,
        expected_document_ids=expected_set,
        cited_document_ids=payload.cited_document_ids,
        require_grounding=payload.require_grounding,
    )
    return APIResponse(
        success=True,
        message="Output inspected successfully",
        data=result
    )


@security_router.get("/events", response_model=APIResponse[PaginatedResponse[SecurityEventRead]])
async def list_security_events(
    event_type: Optional[str] = Query(None, description="Filter by event category"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists real persisted security incidents and policy violations.
    Zero fabricated records.
    """
    offset = (page - 1) * page_size
    query = select(SecurityEvent)

    if event_type:
        query = query.where(SecurityEvent.event_type == event_type)
    if severity:
        query = query.where(SecurityEvent.severity == severity)

    # Count
    count_res = await db.execute(query)
    total = len(count_res.scalars().all())

    # Paginate
    paged_query = query.order_by(desc(SecurityEvent.created_at)).offset(offset).limit(page_size)
    res = await db.execute(paged_query)
    events = list(res.scalars().all())

    items = [SecurityEventRead.model_validate(e) for e in events]
    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size < total)
        )
    )
