import asyncio
import jsonschema
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import SecurityEventType, SecuritySeverity, ApprovalStatus
from backend.app.security.tool_registry import tool_registry, ToolDefinition
from backend.app.security.approval_engine import approval_engine
from backend.app.security.event_recorder import security_event_recorder


class PolicyEngineUnavailableError(Exception):
    """Raised when the security policy engine is offline or in maintenance."""
    pass


class ToolPolicyViolationError(Exception):
    """Raised when a tool invocation violates security policies."""
    pass


class ToolPolicyEngine:
    """
    Centralized Tool Policy & Authorization Engine.
    Guarantees:
    - Never allow direct LLM-to-tool execution that bypasses authorization.
    - Role-based and attribute-based tool permissions.
    - Strict argument schema validation.
    - Enforcement of Human-In-The-Loop (HITL) approval states.
    - Fail-Closed security: if the policy engine is unavailable, all mutations abort immediately.
    """

    def __init__(self):
        self._execution_counters: Dict[str, int] = {}
        self.is_available: bool = True  # Can be toggled for fail-closed tests

    def set_availability(self, available: bool) -> None:
        """Simulates engine availability for testing fail-closed resilience."""
        self.is_available = available

    async def authorize_and_execute(
        self,
        session: AsyncSession,
        tool_name: str,
        arguments: Dict[str, Any],
        user_role: str = "user",
        session_id: str = "default_session",
        agent_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main tool gateway authorization checkpoint.
        Every tool call must pass through this method.
        """
        # 1. Fail-Closed Check
        if not self.is_available:
            await security_event_recorder.record_event(
                session=session,
                trace_id=trace_id,
                agent_id=agent_id,
                event_type=SecurityEventType.POLICY_VIOLATION.value,
                severity=SecuritySeverity.CRITICAL.value,
                detection_method="FAIL_CLOSED_GATEWAY",
                action_taken="BLOCKED",
                details={"reason": "Policy engine unavailable; failing closed."}
            )
            raise PolicyEngineUnavailableError(
                "Security policy engine is unavailable. Failing closed to protect resources."
            )

        # 2. Tool Existence Check
        tool_def = tool_registry.get_tool(tool_name)
        if not tool_def:
            await security_event_recorder.record_event(
                session=session,
                trace_id=trace_id,
                agent_id=agent_id,
                event_type=SecurityEventType.UNAUTHORIZED_TOOL.value,
                severity=SecuritySeverity.HIGH.value,
                detection_method="REGISTRY_VERIFICATION",
                action_taken="BLOCKED",
                details={"tool_name": tool_name, "reason": "Unregistered tool name."}
            )
            raise ToolPolicyViolationError(f"Tool '{tool_name}' is not registered in the system.")

        # 3. Role Authorization Check
        if user_role.lower() not in [r.lower() for r in tool_def.allowed_roles]:
            await security_event_recorder.record_event(
                session=session,
                trace_id=trace_id,
                agent_id=agent_id,
                event_type=SecurityEventType.UNAUTHORIZED_TOOL.value,
                severity=SecuritySeverity.HIGH.value,
                detection_method="ROLE_AUTHORIZATION",
                action_taken="BLOCKED",
                details={
                    "tool_name": tool_name,
                    "user_role": user_role,
                    "allowed_roles": tool_def.allowed_roles
                }
            )
            raise ToolPolicyViolationError(
                f"Role '{user_role}' is not authorized to execute tool '{tool_name}'. "
                f"Allowed roles: {tool_def.allowed_roles}"
            )

        # 4. Schema Validation
        try:
            jsonschema.validate(instance=arguments, schema=tool_def.input_schema)
        except jsonschema.ValidationError as ve:
            await security_event_recorder.record_event(
                session=session,
                trace_id=trace_id,
                agent_id=agent_id,
                event_type=SecurityEventType.POLICY_VIOLATION.value,
                severity=SecuritySeverity.MEDIUM.value,
                detection_method="JSONSCHEMA_VALIDATOR",
                action_taken="BLOCKED",
                details={"tool_name": tool_name, "validation_error": ve.message}
            )
            raise ToolPolicyViolationError(f"Invalid parameters for tool '{tool_name}': {ve.message}")

        # 5. Rate / Count Limit Check
        counter_key = f"{session_id}:{tool_name}"
        current_count = self._execution_counters.get(counter_key, 0)
        if current_count >= tool_def.max_execution_count:
            raise ToolPolicyViolationError(
                f"Execution limit exceeded for tool '{tool_name}' ({current_count} >= {tool_def.max_execution_count})."
            )

        # 6. Human Approval Check
        if tool_def.approval_required:
            if not approval_id:
                # Intercept execution and create pending ApprovalRequest
                approval_req = await approval_engine.create_request(
                    session=session,
                    tool_name=tool_name,
                    tool_arguments=arguments,
                    trace_id=trace_id,
                    risk_level="HIGH"
                )
                return {
                    "status": "PENDING_APPROVAL",
                    "approval_id": approval_req.id,
                    "tool_name": tool_name,
                    "message": "Action requires human approval before execution. Request logged in HITL queue."
                }
            else:
                # Validate provided approval
                req = await approval_engine.get_request(session, approval_id)
                if not req:
                    # Record approval bypass attempt
                    await security_event_recorder.record_event(
                        session=session,
                        trace_id=trace_id,
                        agent_id=agent_id,
                        event_type=SecurityEventType.APPROVAL_BYPASS.value,
                        severity=SecuritySeverity.CRITICAL.value,
                        detection_method="HITL_VALIDATION",
                        action_taken="BLOCKED",
                        details={"approval_id": approval_id, "reason": "Non-existent approval ID supplied."}
                    )
                    raise ToolPolicyViolationError(f"Invalid approval ID '{approval_id}'. Execution blocked.")

                if req.status != ApprovalStatus.APPROVED.value:
                    await security_event_recorder.record_event(
                        session=session,
                        trace_id=trace_id,
                        agent_id=agent_id,
                        event_type=SecurityEventType.APPROVAL_BYPASS.value,
                        severity=SecuritySeverity.CRITICAL.value,
                        detection_method="HITL_VALIDATION",
                        action_taken="BLOCKED",
                        details={"approval_id": approval_id, "actual_status": req.status}
                    )
                    raise ToolPolicyViolationError(
                        f"Refusing tool execution: Approval '{approval_id}' status is '{req.status}', expected 'APPROVED'."
                    )

                # Approved! Transition to executed and run
                exec_result = await approval_engine.execute_approved_action(session, approval_id)
                self._execution_counters[counter_key] = current_count + 1
                return {
                    "status": "SUCCESS",
                    "execution_mode": "APPROVED_HITL",
                    "approval_id": approval_id,
                    "result": exec_result["result"]
                }

        # 7. Execute Standard Tool
        handler = tool_registry.get_handler(tool_name)
        if not handler:
            raise ToolPolicyViolationError(f"No executable handler registered for '{tool_name}'.")

        try:
            # Enforce execution timeout
            result = await asyncio.wait_for(
                handler(arguments),
                timeout=tool_def.max_execution_time_sec
            )
            self._execution_counters[counter_key] = current_count + 1
            return {
                "status": "SUCCESS",
                "execution_mode": "DIRECT_AUTHORIZED",
                "result": result
            }
        except asyncio.TimeoutError:
            raise ToolPolicyViolationError(
                f"Tool '{tool_name}' timed out after {tool_def.max_execution_time_sec} seconds."
            )


tool_policy_engine = ToolPolicyEngine()
