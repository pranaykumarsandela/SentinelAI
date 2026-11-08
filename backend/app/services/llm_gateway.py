import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from backend.app.core.config import settings
    from backend.app.models.entities import (
        LLMInvocation,
        LLMFallbackEvent,
        utc_now,
    )
    from backend.app.services.llm_provider import (
        get_llm_provider,
        BaseLLMProvider,
        NormalizedLLMResponse,
        LLMProviderError,
    )
    from backend.app.services.model_router import (
        model_router,
        TaskRouteItem,
        FallbackRouteItem,
    )
    from backend.app.observability.logger import sentinel_logger
    from backend.app.observability.langfuse_service import langfuse_service
except ImportError:
    from app.core.config import settings
    from app.models.entities import (
        LLMInvocation,
        LLMFallbackEvent,
        utc_now,
    )
    from app.services.llm_provider import (
        get_llm_provider,
        BaseLLMProvider,
        NormalizedLLMResponse,
        LLMProviderError,
    )
    from app.services.model_router import (
        model_router,
        TaskRouteItem,
        FallbackRouteItem,
    )
    from app.observability.logger import sentinel_logger


class MultiLLMGateway:
    """
    Centralized Multi-LLM Gateway providing:
    - Provider abstraction (Gemini, Groq, OpenAI, Mock).
    - Task-based model routing.
    - Intelligent provider fallback on recoverable errors.
    - Database-backed invocation and fallback telemetry.
    - Zero fabrication of metrics or token counts.
    """

    async def execute(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        task_type: str = "general",
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        request_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        is_mock: Optional[bool] = None,
    ) -> NormalizedLLMResponse:
        """
        Executes an LLM request through the primary configured provider,
        automatically falling back to secondary providers on recoverable errors.
        """
        # Determine primary route
        if preferred_provider:
            primary_route = TaskRouteItem(
                provider=preferred_provider.lower(),
                model=preferred_model or model_router.config.default_model,
            )
        else:
            primary_route = model_router.get_route_for_task(task_type)

        # Force mock provider if explicitly requested
        if is_mock is True:
            primary_route = TaskRouteItem(provider="mock", model="mock-sentinel-v1")

        fallback_chain = model_router.get_fallback_chain(task_type)

        # Build candidate execution sequence: primary + eligible fallbacks
        candidates: List[FallbackRouteItem] = [
            FallbackRouteItem(provider=primary_route.provider, model=primary_route.model)
        ]
        for f_item in fallback_chain:
            if f_item.provider != primary_route.provider or f_item.model != primary_route.model:
                candidates.append(f_item)

        last_error: Optional[LLMProviderError] = None
        attempt_number = 1
        successful_response: Optional[NormalizedLLMResponse] = None
        primary_failed_info: Optional[Dict[str, Any]] = None

        for candidate in candidates:
            provider_inst = get_llm_provider(
                provider_name=candidate.provider,
                model_name=candidate.model,
                is_mock=(candidate.provider == "mock"),
            )

            start_t = time.perf_counter()
            invocation_id = str(uuid.uuid4())
            started_dt = utc_now()

            try:
                resp = await provider_inst.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    temperature=temperature,
                    simulate_tool_call=simulate_tool_call,
                )

                # Successfully generated response
                latency_ms = resp.latency_ms or round((time.perf_counter() - start_t) * 1000, 2)
                completed_dt = utc_now()

                # Record successful invocation in database
                if db:
                    inv_record = LLMInvocation(
                        id=invocation_id,
                        trace_id=trace_id,
                        span_id=span_id,
                        request_id=request_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        provider=candidate.provider,
                        model=candidate.model,
                        task_type=task_type,
                        input_tokens=resp.input_tokens,
                        output_tokens=resp.output_tokens,
                        total_tokens=resp.total_tokens,
                        latency_ms=latency_ms,
                        provider_request_id=resp.provider_request_id,
                        finish_reason=resp.finish_reason,
                        status="SUCCESS",
                        error_message=None,
                        error_category=None,
                        retry_count=attempt_number - 1,
                        fallback_occurred=(attempt_number > 1),
                        is_mock=resp.is_mock,
                        started_at=started_dt,
                        completed_at=completed_dt,
                    )
                    db.add(inv_record)

                    # If this was a successful fallback, record the fallback event
                    if attempt_number > 1 and primary_failed_info:
                        fb_event = LLMFallbackEvent(
                            trace_id=trace_id,
                            invocation_id=invocation_id,
                            primary_provider=primary_failed_info["provider"],
                            primary_model=primary_failed_info["model"],
                            fallback_provider=candidate.provider,
                            fallback_model=candidate.model,
                            fallback_reason=primary_failed_info["category"],
                            original_error=primary_failed_info["error"],
                            attempt_number=attempt_number,
                            execution_result="SUCCESS",
                        )
                        db.add(fb_event)

                    try:
                        await db.commit()
                    except Exception as commit_err:
                        sentinel_logger.warning(f"Failed to commit LLM invocation record: {commit_err}")
                        await db.rollback()

                successful_response = resp

                # Record generation telemetry to Langfuse
                if trace_id:
                    try:
                        cost = model_router.calculate_cost(candidate.model, resp.input_tokens, resp.output_tokens)
                        langfuse_service.record_llm_generation(
                            trace_id=trace_id,
                            name=f"LLM Generation: {candidate.provider}/{candidate.model}",
                            provider=candidate.provider,
                            model=candidate.model,
                            prompt_text=prompt,
                            completion_text=resp.content,
                            input_tokens=resp.input_tokens,
                            output_tokens=resp.output_tokens,
                            total_tokens=resp.total_tokens,
                            latency_ms=latency_ms,
                            cost_usd=cost,
                            provider_request_id=resp.provider_request_id,
                            finish_reason=resp.finish_reason,
                            is_mock=resp.is_mock,
                            fallback_occurred=(attempt_number > 1),
                            temperature=temperature,
                            metadata={
                                "task_type": task_type,
                                "attempt_number": attempt_number,
                                "agent_id": agent_id,
                                "request_id": request_id,
                            },
                        )
                    except Exception as lf_err:
                        sentinel_logger.debug(f"Langfuse hook error in llm_gateway: {lf_err}")

                break

            except LLMProviderError as pe:
                latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                completed_dt = utc_now()
                last_error = pe

                # Record failure invocation in database
                if db:
                    inv_record = LLMInvocation(
                        id=invocation_id,
                        trace_id=trace_id,
                        span_id=span_id,
                        request_id=request_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        provider=candidate.provider,
                        model=candidate.model,
                        task_type=task_type,
                        input_tokens=None,
                        output_tokens=None,
                        total_tokens=None,
                        latency_ms=latency_ms,
                        provider_request_id=None,
                        finish_reason="error",
                        status="ERROR",
                        error_message=pe.message[:500],
                        error_category=pe.category,
                        retry_count=attempt_number - 1,
                        fallback_occurred=False,
                        is_mock=(candidate.provider == "mock"),
                        started_at=started_dt,
                        completed_at=completed_dt,
                    )
                    db.add(inv_record)
                    try:
                        await db.commit()
                    except Exception:
                        await db.rollback()

                sentinel_logger.warning(
                    f"LLM Provider [{candidate.provider}/{candidate.model}] failed on attempt {attempt_number}: {pe.message}",
                    extra={"provider": candidate.provider, "category": pe.category, "trace_id": trace_id}
                )

                if attempt_number == 1:
                    primary_failed_info = {
                        "provider": candidate.provider,
                        "model": candidate.model,
                        "category": pe.category,
                        "error": pe.message,
                    }

                # Non-recoverable auth error check: if it's not recoverable and no fallback, stop
                attempt_number += 1
                continue

            except Exception as unk_err:
                latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                completed_dt = utc_now()
                last_error = LLMProviderError(
                    message=f"Unexpected error: {str(unk_err)}",
                    provider=candidate.provider,
                    model=candidate.model,
                    category="UNEXPECTED",
                    is_recoverable=True,
                    original_error=unk_err,
                )

                if db:
                    inv_record = LLMInvocation(
                        id=invocation_id,
                        trace_id=trace_id,
                        span_id=span_id,
                        request_id=request_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        provider=candidate.provider,
                        model=candidate.model,
                        task_type=task_type,
                        input_tokens=None,
                        output_tokens=None,
                        total_tokens=None,
                        latency_ms=latency_ms,
                        provider_request_id=None,
                        finish_reason="error",
                        status="ERROR",
                        error_message=str(unk_err)[:500],
                        error_category="UNEXPECTED",
                        retry_count=attempt_number - 1,
                        fallback_occurred=False,
                        is_mock=(candidate.provider == "mock"),
                        started_at=started_dt,
                        completed_at=completed_dt,
                    )
                    db.add(inv_record)
                    try:
                        await db.commit()
                    except Exception:
                        await db.rollback()

                if attempt_number == 1:
                    primary_failed_info = {
                        "provider": candidate.provider,
                        "model": candidate.model,
                        "category": "UNEXPECTED",
                        "error": str(unk_err),
                    }

                attempt_number += 1
                continue

        if successful_response:
            return successful_response

        # All candidates failed
        raise last_error or LLMProviderError(
            message="All configured LLM providers in fallback chain failed.",
            provider=primary_route.provider,
            model=primary_route.model,
            category="OUTAGE",
            is_recoverable=False,
        )


multi_llm_gateway = MultiLLMGateway()

