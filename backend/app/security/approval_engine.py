from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import ApprovalRequest, ApprovalStatus
from backend.app.security.tool_registry import tool_registry


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class ApprovalSecurityError(Exception):
    """Custom exception for unauthorized or invalid approval actions."""
    pass


class HumanApprovalEngine:
    """
    Server-Side Human-In-The-Loop (HITL) Workflow & Authorization Engine.
    Enforces that high-risk actions cannot execute without valid, unexpired supervisor authorization.
    """

    APPROVER_ROLES = {"supervisor", "admin"}
    DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes

    async def create_request(
        self,
        session: AsyncSession,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        trace_id: Optional[str] = None,
        risk_level: str = "HIGH",
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> ApprovalRequest:
        """Creates a pending approval request with strict expiration timestamp."""
        now = utc_now()
        expires_at = now + timedelta(seconds=timeout_seconds)

        req = ApprovalRequest(
            trace_id=trace_id,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            risk_level=risk_level,
            status=ApprovalStatus.PENDING.value,
            requested_at=now,
            expires_at=expires_at,
        )
        session.add(req)
        await session.commit()
        await session.refresh(req)
        return req

    async def get_request(
        self,
        session: AsyncSession,
        approval_id: str
    ) -> Optional[ApprovalRequest]:
        """Retrieves an approval request and auto-evaluates expiration."""
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        res = await session.execute(stmt)
        req = res.scalar_one_or_none()

        if req and req.status == ApprovalStatus.PENDING.value:
            # Check expiration safely across SQLite and PostgreSQL
            exp = ensure_utc(req.expires_at)
            if exp and utc_now() > exp:
                req.status = ApprovalStatus.EXPIRED.value
                await session.commit()
                await session.refresh(req)

        return req

    async def review_request(
        self,
        session: AsyncSession,
        approval_id: str,
        reviewer_id: str,
        reviewer_role: str,
        action: str,  # APPROVE, REJECT
        notes: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Reviews a pending approval request.
        Requires reviewer role authorization (supervisor or admin).
        Enforces timeout expiration checks.
        """
        req = await self.get_request(session, approval_id)
        if not req:
            raise ApprovalSecurityError(f"Approval request '{approval_id}' not found.")

        # 1. Approver Role Authorization Check
        if reviewer_role.lower() not in self.APPROVER_ROLES:
            raise ApprovalSecurityError(
                f"Unauthorized approver role '{reviewer_role}'. Required roles: {list(self.APPROVER_ROLES)}"
            )

        # 2. Status Validation Check
        if req.status == ApprovalStatus.EXPIRED.value:
            raise ApprovalSecurityError("Cannot review approval request: action has EXPIRED.")

        if req.status != ApprovalStatus.PENDING.value:
            raise ApprovalSecurityError(f"Cannot review request: current status is '{req.status}'.")

        now = utc_now()
        req.reviewed_at = now
        req.reviewer_id = reviewer_id
        req.reviewer_role = reviewer_role

        if action.upper() == "APPROVE":
            req.status = ApprovalStatus.APPROVED.value
        elif action.upper() == "REJECT":
            req.status = ApprovalStatus.REJECTED.value
            req.rejection_reason = notes or "Rejected by supervisor policy review."
        else:
            raise ApprovalSecurityError(f"Invalid review action '{action}'. Supported: APPROVE, REJECT")

        await session.commit()
        await session.refresh(req)
        return req

    async def execute_approved_action(
        self,
        session: AsyncSession,
        approval_id: str
    ) -> Dict[str, Any]:
        """
        Executes a previously approved tool action.
        Guarantees server-side enforcement:
        A rejected, pending, or expired action can NEVER execute.
        """
        req = await self.get_request(session, approval_id)
        if not req:
            raise ApprovalSecurityError(f"Approval request '{approval_id}' does not exist.")

        # Strict server-side enforcement
        if req.status != ApprovalStatus.APPROVED.value:
            raise ApprovalSecurityError(
                f"Refusing execution: Approval status is '{req.status}' (must be 'APPROVED')."
            )

        handler = tool_registry.get_handler(req.tool_name)
        if not handler:
            raise ApprovalSecurityError(f"Handler for tool '{req.tool_name}' not registered.")

        # Transition to EXECUTED
        req.status = ApprovalStatus.EXECUTED.value
        await session.commit()

        # Execute handler
        result = await handler(req.tool_arguments or {})
        return {
            "approval_id": approval_id,
            "tool_name": req.tool_name,
            "execution_status": "EXECUTED",
            "result": result
        }

    async def list_pending(
        self,
        session: AsyncSession,
        limit: int = 50
    ) -> List[ApprovalRequest]:
        """Lists pending approval requests, updating expired entries."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.PENDING.value)
            .order_by(desc(ApprovalRequest.requested_at))
            .limit(limit)
        )
        res = await session.execute(stmt)
        requests = list(res.scalars().all())

        now = utc_now()
        active = []
        for r in requests:
            exp = ensure_utc(r.expires_at)
            if exp and now > exp:
                r.status = ApprovalStatus.EXPIRED.value
                session.add(r)
            else:
                active.append(r)
        await session.commit()
        return active

    async def list_all(
        self,
        session: AsyncSession,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ApprovalRequest], int]:
        """Lists all approval requests with status filter and pagination."""
        stmt = select(ApprovalRequest).order_by(desc(ApprovalRequest.requested_at))
        if status and status.upper() != "ALL":
            stmt = stmt.where(ApprovalRequest.status == status.upper())

        count_res = await session.execute(stmt)
        total = len(count_res.scalars().all())

        paginated = stmt.offset(offset).limit(limit)
        res = await session.execute(paginated)
        return list(res.scalars().all()), total


approval_engine = HumanApprovalEngine()
