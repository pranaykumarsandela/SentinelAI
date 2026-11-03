from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.common import APIResponse
from backend.app.schemas.security import ApprovalRequestRead, ApprovalReviewRequest
from backend.app.security.approval_engine import approval_engine, ApprovalSecurityError

approvals_router = APIRouter(prefix="/approvals", tags=["Human Approvals (HITL)"])


@approvals_router.get("/pending", response_model=APIResponse[List[ApprovalRequestRead]])
async def list_pending_approvals(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lists pending human approval requests awaiting supervisor review."""
    requests = await approval_engine.list_pending(session=db, limit=limit)
    items = [ApprovalRequestRead.model_validate(r) for r in requests]
    return APIResponse(
        success=True,
        data=items
    )


@approvals_router.get("/{approval_id}", response_model=APIResponse[ApprovalRequestRead])
async def get_approval_request(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves approval request status and details."""
    req = await approval_engine.get_request(session=db, approval_id=approval_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found."
        )
    return APIResponse(
        success=True,
        data=ApprovalRequestRead.model_validate(req)
    )


@approvals_router.post("/{approval_id}/review", response_model=APIResponse[ApprovalRequestRead])
async def review_approval_request(
    approval_id: str,
    payload: ApprovalReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a review decision (APPROVE or REJECT) for a pending tool authorization.
    Requires supervisor or admin role authorization.
    """
    try:
        reviewed_req = await approval_engine.review_request(
            session=db,
            approval_id=approval_id,
            reviewer_id=payload.reviewer_id,
            reviewer_role=payload.reviewer_role,
            action=payload.action,
            notes=payload.notes,
        )
        return APIResponse(
            success=True,
            message=f"Approval request successfully {reviewed_req.status}.",
            data=ApprovalRequestRead.model_validate(reviewed_req)
        )
    except ApprovalSecurityError as ase:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ase)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval review failed: {str(e)}"
        )
