from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.common import APIResponse
from backend.app.schemas.security import ToolExecuteRequest, ToolExecuteResponse
from backend.app.security.tool_registry import tool_registry, ToolDefinition
from backend.app.security.tool_policy_engine import (
    tool_policy_engine,
    ToolPolicyViolationError,
    PolicyEngineUnavailableError,
)

tools_router = APIRouter(prefix="/tools", tags=["Tools"])


@tools_router.get("", response_model=APIResponse[List[ToolDefinition]])
async def list_registered_tools():
    """Lists all registered tools, schemas, allowed roles, and risk tiers."""
    tools = tool_registry.list_tools()
    return APIResponse(
        success=True,
        data=tools
    )


@tools_router.post("/execute", response_model=APIResponse[ToolExecuteResponse])
async def execute_tool(
    payload: ToolExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a tool through the Centralized Tool Policy & Authorization Engine.
    Enforces role validation, input schemas, rate limits, and HITL approvals.
    """
    try:
        result = await tool_policy_engine.authorize_and_execute(
            session=db,
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            user_role=payload.user_role,
            session_id=payload.session_id,
            agent_id=payload.agent_id,
            trace_id=payload.trace_id,
            approval_id=payload.approval_id,
        )
        return APIResponse(
            success=True,
            message="Tool authorized and executed successfully" if result["status"] == "SUCCESS" else result.get("message", "Pending authorization"),
            data=ToolExecuteResponse(**result)
        )
    except ToolPolicyViolationError as pe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe)
        )
    except PolicyEngineUnavailableError as pue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(pue)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {str(e)}"
        )
