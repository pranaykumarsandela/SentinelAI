from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.models.entities import Agent, Tenant
from backend.app.schemas.entities import (
    AgentCreate,
    AgentRead,
    GatewayExecuteRequest,
    GatewayExecuteResponse,
)
from backend.app.agent.orchestrator import agent_orchestrator

router = APIRouter(prefix="/agents", tags=["Agents & Orchestration"])


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_in: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new enterprise AI agent."""
    tenant = await db.get(Tenant, agent_in.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{agent_in.tenant_id}' not found.",
        )

    agent = Agent(
        tenant_id=agent_in.tenant_id,
        name=agent_in.name,
        description=agent_in.description,
        model_provider=agent_in.model_provider,
        model_name=agent_in.model_name,
        temperature=agent_in.temperature,
        system_prompt=agent_in.system_prompt,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("", response_model=List[AgentRead])
async def list_agents(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    db: AsyncSession = Depends(get_db),
):
    """List registered AI agents."""
    query = select(Agent).order_by(desc(Agent.created_at))
    if tenant_id:
        query = query.where(Agent.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details for a specific AI agent."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found.",
        )
    return agent


@router.post("/execute", response_model=GatewayExecuteResponse)
async def execute_agent(
    request: GatewayExecuteRequest,
    role: str = Query("user", description="Caller role: user, supervisor, admin"),
    use_rag: bool = Query(False, description="Whether to retrieve grounding context from RAG"),
    simulate_tool_call: Optional[str] = Query(None, description="Deterministic tool call simulation for testing"),
    db: AsyncSession = Depends(get_db),
):
    """
    Main Gateway Execution endpoint.
    Passes query through:
    1. Input Security Guard (deterministic + heuristic)
    2. RAG Context Retrieval & Injection Guard (if requested)
    3. LLM Plan & Tool Invocation
    4. Tool Policy Engine & Permission Enforcement
    5. HITL Approval Check (creates pending approval if required)
    6. Safe Server-side Tool Execution
    7. Output Guardrails (PII redaction, secret protection, groundedness)
    8. Complete Trace & Span Database Persistence
    """
    agent = await db.get(Agent, request.agent_id)
    tenant_id = agent.tenant_id if agent else "default_tenant"
    system_prompt = agent.system_prompt if agent else None

    response = await agent_orchestrator.execute(
        db=db,
        request=request,
        tenant_id=tenant_id,
        role=role,
        system_prompt=system_prompt,
        use_rag=use_rag,
        simulate_tool_call=simulate_tool_call,
    )
    return response


@router.post("/{agent_id}/chat", response_model=GatewayExecuteResponse)
async def chat_with_agent(
    agent_id: str,
    prompt: str = Query(..., description="User message"),
    session_id: Optional[str] = Query(None, description="Session ID"),
    is_mock: bool = Query(True, description="Enforce deterministic mock provider conforming to Data Integrity Policy"),
    role: str = Query("user", description="Caller role: user, supervisor, admin"),
    use_rag: bool = Query(False, description="Enable grounding with RAG"),
    db: AsyncSession = Depends(get_db),
):
    """Convenience endpoint to chat with a designated agent."""
    req = GatewayExecuteRequest(
        agent_id=agent_id,
        prompt=prompt,
        session_id=session_id,
        is_mock=is_mock,
    )
    return await execute_agent(
        request=req,
        role=role,
        use_rag=use_rag,
        db=db,
    )
