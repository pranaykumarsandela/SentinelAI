import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import (
    ExecutionTrace,
    TraceSpan,
    ApprovalRequest,
    SecurityEvent,
    ExecutionStatus,
    SpanType,
    SecurityEventType,
    SecuritySeverity,
)
from backend.app.schemas.entities import (
    GatewayExecuteRequest,
    GatewayExecuteResponse,
    SecurityViolationItem,
)
from backend.app.security.input_guard import input_security_guard, SecurityVerdict
from backend.app.security.tool_registry import tool_registry
from backend.app.security.tool_policy_engine import tool_policy_engine
from backend.app.security.approval_engine import approval_engine
from backend.app.security.output_guard import output_guard
from backend.app.security.event_recorder import security_event_recorder
from backend.app.rag.hybrid_retriever import hybrid_retriever
from backend.app.rag.prompt_injection_guard import indirect_injection_guard
from backend.app.services.llm_provider import get_llm_provider, BaseLLMProvider
from backend.app.observability.logger import sentinel_logger


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrchestratorState(TypedDict):
    request_id: str
    trace_id: str
    tenant_id: str
    agent_id: str
    session_id: Optional[str]
    role: str
    user_id: str
    input_prompt: str
    sanitized_input: str
    system_prompt: Optional[str]
    use_rag: bool
    is_mock: bool
    model_name: Optional[str]
    simulate_tool_call: Optional[str]

    step_count: int
    max_steps: int

    corpus_chunks: List[Dict[str, Any]]
    retrieved_chunks: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]

    tool_calls: List[Dict[str, Any]]
    authorized_tools: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]

    approval_requests: List[Dict[str, Any]]
    pending_approval_id: Optional[str]

    raw_output: str
    final_response: str
    status: str

    violations: List[Dict[str, Any]]
    security_events: List[Dict[str, Any]]

    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_latency_ms: float
    estimated_cost_usd: float

    spans: List[Dict[str, Any]]
    error: Optional[str]


# --- Graph Nodes ---

def node_guard_input(state: OrchestratorState) -> Dict[str, Any]:
    """Inspects user input through deterministic & heuristic security firewall."""
    start_t = time.perf_counter()
    spans = list(state.get("spans", []))
    violations = list(state.get("violations", []))
    sec_events = list(state.get("security_events", []))

    input_text = state["input_prompt"]
    inspection = input_security_guard.inspect_input(input_text)
    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
    is_blocked = (inspection.verdict == SecurityVerdict.BLOCK)

    span = {
        "id": str(uuid.uuid4()),
        "name": "GUARD_INPUT",
        "span_type": SpanType.GUARD_INPUT.value,
        "input_data": {"input_prompt": input_text},
        "output_data": {
            "verdict": inspection.verdict.value,
            "blocked": is_blocked,
            "violations": [v.model_dump() for v in inspection.violations],
        },
        "latency_ms": latency_ms,
        "tokens": 0,
        "status": "ERROR" if is_blocked else "OK",
        "created_at": utc_now(),
    }
    spans.append(span)

    if is_blocked:
        for v in inspection.violations:
            violation_entry = {
                "event_type": v.category,
                "severity": v.severity,
                "confidence_score": float(v.confidence),
                "detector_name": v.detector_name,
                "action_taken": "BLOCKED",
                "details": v.details,
            }
            violations.append(violation_entry)
            sec_events.append({
                "trace_id": state["trace_id"],
                "request_id": state["request_id"],
                "agent_id": state["agent_id"],
                "event_type": violation_entry["event_type"],
                "severity": violation_entry["severity"],
                "confidence_score": violation_entry["confidence_score"],
                "detector_name": violation_entry["detector_name"],
                "action": "BLOCKED",
                "details": violation_entry["details"],
            })

        sentinel_logger.warning(
            f"Input blocked by Security Guard: {inspection.violations}",
            extra={"trace_id": state["trace_id"], "agent_id": state["agent_id"]},
        )

        return {
            "spans": spans,
            "violations": violations,
            "security_events": sec_events,
            "status": ExecutionStatus.BLOCKED.value,
            "sanitized_input": inspection.sanitized_input,
            "final_response": "Security Violation: Request blocked by SentinelAI Input Firewall.",
        }

    return {
        "spans": spans,
        "violations": violations,
        "security_events": sec_events,
        "sanitized_input": inspection.sanitized_input,
    }


def route_after_input(state: OrchestratorState) -> str:
    if state.get("status") == ExecutionStatus.BLOCKED.value:
        return "node_finalize"
    return "node_retrieve_context"


def node_retrieve_context(state: OrchestratorState) -> Dict[str, Any]:
    """Retrieves grounding context if RAG is requested, enforcing context injection guards."""
    start_t = time.perf_counter()
    spans = list(state.get("spans", []))
    violations = list(state.get("violations", []))
    sec_events = list(state.get("security_events", []))
    retrieved_chunks: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []

    if state.get("use_rag") and state.get("corpus_chunks"):
        query = state.get("sanitized_input") or state["input_prompt"]
        results = hybrid_retriever.retrieve(
            query=query,
            corpus_chunks=state.get("corpus_chunks", []),
            tenant_id=state.get("tenant_id", "default_tenant"),
            top_k=3,
        )

        for res in results:
            text = res.get("content", "")
            # Apply Indirect Prompt Injection Guard
            inj_res = indirect_injection_guard.inspect_chunk(text)
            sanitized_text = inj_res.sanitized_text
            
            if inj_res.is_suspicious:
                for pat in inj_res.matched_patterns:
                    violation_entry = {
                        "event_type": SecurityEventType.INDIRECT_PROMPT_INJECTION.value,
                        "severity": SecuritySeverity.HIGH.value,
                        "confidence_score": inj_res.score,
                        "detector_name": "IndirectPromptInjectionGuard",
                        "action_taken": "FLAG",
                        "details": {"pattern": pat, "document": res.get("filename")},
                    }
                    violations.append(violation_entry)
                    sec_events.append({
                        "trace_id": state["trace_id"],
                        "request_id": state["request_id"],
                        "agent_id": state["agent_id"],
                        "event_type": violation_entry["event_type"],
                        "severity": violation_entry["severity"],
                        "confidence_score": violation_entry["confidence_score"],
                        "detector_name": violation_entry["detector_name"],
                        "action": "FLAG",
                        "details": violation_entry["details"],
                    })

            c_id = res.get("chunk_id") or res.get("id") or "chunk_1"
            chunk_info = {
                "chunk_id": c_id,
                "document_id": res.get("document_id"),
                "filename": res.get("filename", "Document"),
                "page_number": res.get("page_number"),
                "content": sanitized_text,
                "score": res.get("relevance_score", 0.0),
            }
            retrieved_chunks.append(chunk_info)
            citations.append({
                "chunk_id": c_id,
                "document_id": res.get("document_id"),
                "filename": res.get("filename", "Document"),
                "page_number": res.get("page_number"),
                "relevant_source_text": sanitized_text[:180],
            })

    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
    spans.append({
        "id": str(uuid.uuid4()),
        "name": "RETRIEVE_CONTEXT",
        "span_type": SpanType.RETRIEVAL.value,
        "input_data": {"query": state.get("sanitized_input") or state["input_prompt"], "use_rag": state.get("use_rag")},
        "output_data": {"chunks_retrieved": len(retrieved_chunks)},
        "latency_ms": latency_ms,
        "tokens": 0,
        "status": "OK",
        "created_at": utc_now(),
    })

    return {
        "spans": spans,
        "violations": violations,
        "security_events": sec_events,
        "retrieved_chunks": retrieved_chunks,
        "citations": citations,
    }


async def node_llm_plan(state: OrchestratorState) -> Dict[str, Any]:
    """Generates next agent action (response or tool invocation plan) via LLM Provider."""
    start_t = time.perf_counter()
    spans = list(state.get("spans", []))

    provider = get_llm_provider(
        model_name=state.get("model_name"),
        is_mock=state.get("is_mock", True),
    )

    prompt = state.get("sanitized_input") or state["input_prompt"]
    system_prompt = state.get("system_prompt") or "You are SentinelAI Enterprise Agent. Answer faithfully and safely."
    
    if state.get("retrieved_chunks"):
        context_block = "\n\n".join(
            [f"[Source: {c['filename']}]\n{c['content']}" for c in state["retrieved_chunks"]]
        )
        prompt = f"Grounding Context:\n{context_block}\n\nUser Question:\n{prompt}"

    available_tools = tool_registry.list_tools()
    
    llm_resp = await provider.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        tools=available_tools,
        simulate_tool_call=state.get("simulate_tool_call"),
    )

    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
    spans.append({
        "id": str(uuid.uuid4()),
        "name": "LLM_PLAN",
        "span_type": SpanType.LLM_CALL.value,
        "input_data": {"prompt_chars": len(prompt)},
        "output_data": {
            "has_tool_calls": len(llm_resp.tool_calls) > 0,
            "tool_calls": llm_resp.tool_calls,
            "tokens": llm_resp.total_tokens,
        },
        "latency_ms": latency_ms,
        "tokens": llm_resp.total_tokens,
        "status": "OK",
        "created_at": utc_now(),
    })

    return {
        "spans": spans,
        "tool_calls": llm_resp.tool_calls,
        "raw_output": llm_resp.content,
        "prompt_tokens": state.get("prompt_tokens", 0) + llm_resp.prompt_tokens,
        "completion_tokens": state.get("completion_tokens", 0) + llm_resp.completion_tokens,
        "total_tokens": state.get("total_tokens", 0) + llm_resp.total_tokens,
    }


def route_after_plan(state: OrchestratorState) -> str:
    if state.get("tool_calls"):
        return "node_authorize_tools"
    return "node_guard_output"


def node_authorize_tools(state: OrchestratorState) -> Dict[str, Any]:
    """Interceps tool calls and verifies permissions via ToolPolicyEngine."""
    start_t = time.perf_counter()
    spans = list(state.get("spans", []))
    violations = list(state.get("violations", []))
    sec_events = list(state.get("security_events", []))
    approval_requests = list(state.get("approval_requests", []))
    authorized_tools: List[Dict[str, Any]] = []

    pending_approval_id = None
    execution_status = state.get("status", ExecutionStatus.SUCCESS.value)
    final_resp = state.get("raw_output", "")

    for tc in state.get("tool_calls", []):
        tool_name = tc.get("name", "")
        args = tc.get("arguments", {})
        if isinstance(args, str):
            try:
                import json
                args = json.loads(args)
            except Exception:
                args = {"raw": args}

        eval_res = tool_policy_engine.evaluate_tool_call(
            tool_name=tool_name,
            arguments=args,
            user_role=state.get("role", "user"),
            user_id=state.get("user_id", "user_default"),
        )

        if eval_res.is_blocked:
            violation_entry = {
                "event_type": SecurityEventType.UNAUTHORIZED_TOOL.value,
                "severity": SecuritySeverity.HIGH.value,
                "confidence_score": 1.0,
                "detector_name": "ToolPolicyEngine",
                "action_taken": "BLOCK",
                "details": {"tool": tool_name, "reason": eval_res.reason},
            }
            violations.append(violation_entry)
            sec_events.append({
                "trace_id": state["trace_id"],
                "request_id": state["request_id"],
                "agent_id": state["agent_id"],
                "event_type": violation_entry["event_type"],
                "severity": violation_entry["severity"],
                "confidence_score": 1.0,
                "detector_name": "ToolPolicyEngine",
                "action": "BLOCK",
                "details": violation_entry["details"],
            })
            execution_status = ExecutionStatus.BLOCKED.value
            final_resp = f"Security Violation: Invocation of tool '{tool_name}' was blocked: {eval_res.reason}"
            break

        if eval_res.requires_approval:
            approval_id = str(uuid.uuid4())
            pending_approval_id = approval_id
            execution_status = ExecutionStatus.PENDING_APPROVAL.value
            approval_requests.append({
                "id": approval_id,
                "trace_id": state["trace_id"],
                "tool_name": tool_name,
                "tool_arguments": args,
                "risk_level": "HIGH",
                "status": "PENDING",
                "requested_by": state.get("user_id", "user_default"),
                "requested_at": utc_now(),
            })
            final_resp = (
                f"Action Paused: Tool '{tool_name}' requires human supervisor approval "
                f"before execution (Approval ID: {approval_id})."
            )
            break

        # Tool authorized
        authorized_tools.append({"id": tc.get("id"), "name": tool_name, "arguments": args})

    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
    spans.append({
        "id": str(uuid.uuid4()),
        "name": "AUTHORIZE_TOOLS",
        "span_type": SpanType.TOOL_EXECUTION.value,
        "input_data": {"tool_calls": state.get("tool_calls", [])},
        "output_data": {
            "authorized_count": len(authorized_tools),
            "status": execution_status,
        },
        "latency_ms": latency_ms,
        "tokens": 0,
        "status": "OK" if execution_status != ExecutionStatus.BLOCKED.value else "ERROR",
        "created_at": utc_now(),
    })

    return {
        "spans": spans,
        "violations": violations,
        "security_events": sec_events,
        "authorized_tools": authorized_tools,
        "approval_requests": approval_requests,
        "pending_approval_id": pending_approval_id,
        "status": execution_status,
        "final_response": final_resp,
    }


def route_after_auth(state: OrchestratorState) -> str:
    if state.get("status") in (ExecutionStatus.BLOCKED.value, ExecutionStatus.PENDING_APPROVAL.value):
        return "node_finalize"
    if state.get("authorized_tools"):
        return "node_execute_tools"
    return "node_guard_output"


async def node_execute_tools(state: OrchestratorState) -> Dict[str, Any]:
    """Safely executes authorized tools in server-side isolated registry."""
    start_t = time.perf_counter()
    spans = list(state.get("spans", []))
    tool_results: List[Dict[str, Any]] = []

    for tool in state.get("authorized_tools", []):
        t_start = time.perf_counter()
        tool_name = tool["name"]
        args = tool["arguments"]

        exec_res = await tool_registry.execute_tool(tool_name, args)
        t_latency = round((time.perf_counter() - t_start) * 1000, 2)

        tool_results.append({
            "name": tool_name,
            "success": exec_res.success,
            "data": exec_res.data,
            "error": exec_res.error,
        })

        spans.append({
            "id": str(uuid.uuid4()),
            "name": f"TOOL_{tool_name}",
            "span_type": SpanType.TOOL_EXECUTION.value,
            "input_data": args,
            "output_data": {"success": exec_res.success, "data": exec_res.data, "error": exec_res.error},
            "latency_ms": t_latency,
            "tokens": 0,
            "status": "OK" if exec_res.success else "ERROR",
            "created_at": utc_now(),
        })

    # Call LLM to synthesize final response incorporating tool results
    provider = get_llm_provider(
        model_name=state.get("model_name"),
        is_mock=state.get("is_mock", True),
    )
    
    synth_prompt = (
        f"Original Request: {state['input_prompt']}\n\n"
        f"Tool Results:\n{tool_results}\n\n"
        "Synthesize a clear, helpful response for the user based strictly on these tool execution results."
    )
    
    synth_resp = await provider.generate(
        prompt=synth_prompt,
        system_prompt=state.get("system_prompt"),
    )

    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
    spans.append({
        "id": str(uuid.uuid4()),
        "name": "LLM_SYNTHESIS",
        "span_type": SpanType.LLM_CALL.value,
        "input_data": {"tool_results_count": len(tool_results)},
        "output_data": {"tokens": synth_resp.total_tokens},
        "latency_ms": latency_ms,
        "tokens": synth_resp.total_tokens,
        "status": "OK",
        "created_at": utc_now(),
    })

    return {
        "spans": spans,
        "tool_results": tool_results,
        "raw_output": synth_resp.content,
        "prompt_tokens": state.get("prompt_tokens", 0) + synth_resp.prompt_tokens,
        "completion_tokens": state.get("completion_tokens", 0) + synth_resp.completion_tokens,
        "total_tokens": state.get("total_tokens", 0) + synth_resp.total_tokens,
    }


def node_guard_output(state: OrchestratorState) -> Dict[str, Any]:
    """Inspects LLM output through Output Guardrails (PII redaction, secret protection)."""
    start_t = time.perf_counter()
    spans = list(state.get("spans", []))
    violations = list(state.get("violations", []))
    sec_events = list(state.get("security_events", []))

    content = state.get("raw_output") or state.get("final_response") or ""
    context_chunks = [c["content"] for c in state.get("retrieved_chunks", [])]

    out_res = output_guard.inspect_output(content, source_context_chunks=context_chunks)
    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
    is_blocked = (out_res.verdict == SecurityVerdict.BLOCK)

    spans.append({
        "id": str(uuid.uuid4()),
        "name": "GUARD_OUTPUT",
        "span_type": SpanType.GUARD_INPUT.value,
        "input_data": {"content_length": len(content)},
        "output_data": {
            "verdict": out_res.verdict.value,
            "violations_count": len(out_res.violations),
        },
        "latency_ms": latency_ms,
        "tokens": 0,
        "status": "ERROR" if is_blocked else "OK",
        "created_at": utc_now(),
    })

    if is_blocked:
        for v in out_res.violations:
            violation_entry = {
                "event_type": v.category,
                "severity": v.severity,
                "confidence_score": float(v.confidence),
                "detector_name": v.detector_name,
                "action_taken": "BLOCK",
                "details": v.details,
            }
            violations.append(violation_entry)
            sec_events.append({
                "trace_id": state["trace_id"],
                "request_id": state["request_id"],
                "agent_id": state["agent_id"],
                "event_type": violation_entry["event_type"],
                "severity": violation_entry["severity"],
                "confidence_score": float(v.confidence),
                "detector_name": violation_entry["detector_name"],
                "action": "BLOCK",
                "details": violation_entry["details"],
            })

        return {
            "spans": spans,
            "violations": violations,
            "security_events": sec_events,
            "status": ExecutionStatus.BLOCKED.value,
            "final_response": "Security Violation: Output blocked by SentinelAI Egress Guardrail.",
        }

    return {
        "spans": spans,
        "violations": violations,
        "security_events": sec_events,
        "final_response": out_res.sanitized_output,
        "status": state.get("status") or ExecutionStatus.SUCCESS.value,
    }


def node_finalize(state: OrchestratorState) -> Dict[str, Any]:
    """Finalizes metrics, token counts, and cost calculation."""
    total_tokens = state.get("total_tokens", 0)
    # Estimated cost: $0.000002 per token standard baseline for audit tracking
    estimated_cost = round(total_tokens * 0.000002, 6)
    
    total_lat = sum(s.get("latency_ms", 0.0) for s in state.get("spans", []))

    return {
        "estimated_cost_usd": estimated_cost,
        "total_latency_ms": round(total_lat, 2),
    }


def build_orchestrator_graph() -> Any:
    workflow = StateGraph(OrchestratorState)

    workflow.add_node("node_guard_input", node_guard_input)
    workflow.add_node("node_retrieve_context", node_retrieve_context)
    workflow.add_node("node_llm_plan", node_llm_plan)
    workflow.add_node("node_authorize_tools", node_authorize_tools)
    workflow.add_node("node_execute_tools", node_execute_tools)
    workflow.add_node("node_guard_output", node_guard_output)
    workflow.add_node("node_finalize", node_finalize)

    workflow.add_edge(START, "node_guard_input")
    workflow.add_conditional_edges("node_guard_input", route_after_input)
    workflow.add_edge("node_retrieve_context", "node_llm_plan")
    workflow.add_conditional_edges("node_llm_plan", route_after_plan)
    workflow.add_conditional_edges("node_authorize_tools", route_after_auth)
    workflow.add_edge("node_execute_tools", "node_guard_output")
    workflow.add_edge("node_guard_output", "node_finalize")
    workflow.add_edge("node_finalize", END)

    return workflow.compile()


compiled_orchestrator_graph = build_orchestrator_graph()


class AgentOrchestrator:
    """
    Central Agent Orchestrator executing requests through the LangGraph StateGraph,
    enforcing deterministic security guardrails, tool permissions, and persistent database tracing.
    """

    def __init__(self):
        self.graph = compiled_orchestrator_graph

    async def execute(
        self,
        db: AsyncSession,
        request: GatewayExecuteRequest,
        tenant_id: str = "default_tenant",
        role: str = "user",
        user_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        use_rag: bool = False,
        simulate_tool_call: Optional[str] = None,
    ) -> GatewayExecuteResponse:
        trace_id = str(uuid.uuid4())
        req_id = request.session_id or f"req-{uuid.uuid4().hex[:8]}"
        u_id = user_id or f"user-{tenant_id}"

        corpus_chunks: List[Dict[str, Any]] = []
        if use_rag:
            from sqlalchemy import select
            from backend.app.models.entities import Document, DocumentChunk, IngestionStatus
            stmt = (
                select(DocumentChunk, Document.filename)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(Document.tenant_id == tenant_id, Document.status == IngestionStatus.COMPLETED.value)
            )
            res = await db.execute(stmt)
            for chunk, filename in res.all():
                corpus_chunks.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "filename": filename,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                })

        initial_state: OrchestratorState = {
            "request_id": req_id,
            "trace_id": trace_id,
            "tenant_id": tenant_id,
            "agent_id": request.agent_id,
            "session_id": request.session_id,
            "role": role,
            "user_id": u_id,
            "input_prompt": request.prompt,
            "sanitized_input": request.prompt,
            "system_prompt": system_prompt,
            "use_rag": use_rag,
            "is_mock": request.is_mock,
            "model_name": None,
            "simulate_tool_call": simulate_tool_call,
            "step_count": 0,
            "max_steps": 10,
            "corpus_chunks": corpus_chunks,
            "retrieved_chunks": [],
            "citations": [],
            "tool_calls": [],
            "authorized_tools": [],
            "tool_results": [],
            "approval_requests": [],
            "pending_approval_id": None,
            "raw_output": "",
            "final_response": "",
            "status": ExecutionStatus.SUCCESS.value,
            "violations": [],
            "security_events": [],
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_latency_ms": 0.0,
            "estimated_cost_usd": 0.0,
            "spans": [],
            "error": None,
        }

        # Execute LangGraph workflow
        final_state: OrchestratorState = await self.graph.ainvoke(initial_state)

        # Persist ExecutionTrace
        trace_entity = ExecutionTrace(
            id=trace_id,
            tenant_id=tenant_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            input_prompt=request.prompt,
            sanitized_input=final_state.get("sanitized_input"),
            output_response=final_state.get("raw_output") or final_state.get("final_response"),
            sanitized_output=final_state.get("final_response"),
            status=final_state.get("status", ExecutionStatus.SUCCESS.value),
            is_mock=request.is_mock,
            total_tokens=final_state.get("total_tokens", 0),
            prompt_tokens=final_state.get("prompt_tokens", 0),
            completion_tokens=final_state.get("completion_tokens", 0),
            total_latency_ms=final_state.get("total_latency_ms", 0.0),
            estimated_cost_usd=final_state.get("estimated_cost_usd", 0.0),
            started_at=utc_now(),
            completed_at=utc_now(),
        )
        db.add(trace_entity)

        # Persist Spans
        for s in final_state.get("spans", []):
            span_entity = TraceSpan(
                id=s["id"],
                trace_id=trace_id,
                name=s["name"],
                span_type=s["span_type"],
                input_data=s.get("input_data"),
                output_data=s.get("output_data"),
                latency_ms=s.get("latency_ms", 0.0),
                tokens=s.get("tokens", 0),
                status=s.get("status", "OK"),
                created_at=s.get("created_at", utc_now()),
            )
            db.add(span_entity)

        # Persist Approval Requests
        for app_req in final_state.get("approval_requests", []):
            req_entity = ApprovalRequest(
                id=app_req["id"],
                trace_id=trace_id,
                tool_name=app_req["tool_name"],
                tool_arguments=app_req["tool_arguments"],
                risk_level=app_req["risk_level"],
                status=app_req["status"],
                requested_at=app_req["requested_at"],
            )
            db.add(req_entity)

        # Persist Security Events
        for ev in final_state.get("security_events", []):
            ev_entity = SecurityEvent(
                id=str(uuid.uuid4()),
                trace_id=trace_id,
                request_id=ev.get("request_id"),
                agent_id=ev.get("agent_id"),
                event_type=ev.get("event_type"),
                severity=ev.get("severity"),
                confidence_score=ev.get("confidence_score", 1.0),
                detector_name=ev.get("detector_name"),
                action_taken=ev.get("action"),
                details=ev.get("details"),
                created_at=utc_now(),
            )
            db.add(ev_entity)

        await db.commit()

        # Format violations
        violation_items = [
            SecurityViolationItem(
                event_type=v["event_type"],
                severity=v["severity"],
                confidence_score=v["confidence_score"],
                detector_name=v["detector_name"],
                action_taken=v["action_taken"],
                details=v.get("details"),
            )
            for v in final_state.get("violations", [])
        ]

        return GatewayExecuteResponse(
            trace_id=trace_id,
            agent_id=request.agent_id,
            status=final_state.get("status", ExecutionStatus.SUCCESS.value),
            output=final_state.get("final_response"),
            sanitized_input=final_state.get("sanitized_input", request.prompt),
            is_mock=request.is_mock,
            total_tokens=final_state.get("total_tokens", 0),
            total_latency_ms=final_state.get("total_latency_ms", 0.0),
            estimated_cost_usd=final_state.get("estimated_cost_usd", 0.0),
            violations=violation_items,
            approval_id=final_state.get("pending_approval_id"),
        )


agent_orchestrator = AgentOrchestrator()
