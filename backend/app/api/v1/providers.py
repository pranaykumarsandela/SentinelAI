import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, case
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.schemas.common import APIResponse, PaginatedResponse
from backend.app.models.entities import (
    LLMInvocation,
    LLMFallbackEvent,
    LLMBenchmarkRun,
    LLMBenchmarkResult,
)
from backend.app.services.llm_provider import (
    get_llm_provider,
    GeminiProvider,
    GroqProvider,
    OpenAIProvider,
    MockLLMProvider,
)
from backend.app.services.model_router import (
    model_router,
    SUPPORTED_MODELS_ALLOWLIST,
    PRICING_CATALOG_V1,
)
from backend.app.evaluation.provider_benchmark import provider_benchmark_engine


providers_router = APIRouter(tags=["Multi-LLM Providers & Observability"])


# --- Schemas ---

class ProviderStatusItem(BaseModel):
    provider: str
    display_name: str
    is_configured: bool
    configured_model: str
    supports_tools: bool
    supports_structured: bool
    supports_streaming: bool


class ProviderHealthCheckItem(BaseModel):
    provider: str
    model: str
    connected: bool
    status: str  # HEALTHY, UNREACHABLE, NOT_CONFIGURED
    latency_ms: Optional[float] = None
    message: str
    timestamp: float


class ProviderConfigUpdatePayload(BaseModel):
    default_provider: Optional[str] = None
    default_model: Optional[str] = None
    task_routing: Optional[Dict[str, Dict[str, str]]] = None
    fallback_chains: Optional[Dict[str, List[Dict[str, str]]]] = None


class BenchmarkRunRequestPayload(BaseModel):
    providers: List[Dict[str, str]] = Field(..., min_length=1)
    dataset_name: Optional[str] = "SentinelAI Standard Multi-LLM Benchmark"
    dataset_version: Optional[str] = "v1.0"
    prompt_version: Optional[str] = "v1.0"
    is_mock: Optional[bool] = False


# ==============================================================================
# PROVIDER STATUS & HEALTH ENDPOINTS
# ==============================================================================

@providers_router.get("/providers", response_model=APIResponse[List[ProviderStatusItem]])
async def list_providers():
    """Lists all supported LLM providers and their configuration status without exposing keys."""
    providers_list = [
        ProviderStatusItem(
            provider="gemini",
            display_name="Google Gemini",
            is_configured=bool(settings.effective_gemini_api_key),
            configured_model=settings.GEMINI_MODEL,
            supports_tools=True,
            supports_structured=True,
            supports_streaming=True,
        ),
        ProviderStatusItem(
            provider="groq",
            display_name="Groq",
            is_configured=bool(settings.GROQ_API_KEY),
            configured_model=settings.GROQ_MODEL,
            supports_tools=True,
            supports_structured=True,
            supports_streaming=True,
        ),
        ProviderStatusItem(
            provider="openai",
            display_name="OpenAI",
            is_configured=bool(settings.OPENAI_API_KEY),
            configured_model=settings.OPENAI_MODEL,
            supports_tools=True,
            supports_structured=True,
            supports_streaming=True,
        ),
        ProviderStatusItem(
            provider="mock",
            display_name="SentinelAI Mock Engine",
            is_configured=True,
            configured_model="mock-sentinel-v1",
            supports_tools=True,
            supports_structured=True,
            supports_streaming=True,
        ),
    ]
    return APIResponse(success=True, data=providers_list)


@providers_router.get("/providers/health", response_model=APIResponse[List[ProviderHealthCheckItem]])
async def get_all_providers_health():
    """Returns live connection health checks across all LLM providers."""
    results: List[ProviderHealthCheckItem] = []

    # Gemini
    p_gemini = GeminiProvider()
    h_gemini = await p_gemini.health_check()
    results.append(ProviderHealthCheckItem(**h_gemini))

    # Groq
    p_groq = GroqProvider()
    h_groq = await p_groq.health_check()
    results.append(ProviderHealthCheckItem(**h_groq))

    # OpenAI
    p_openai = OpenAIProvider()
    h_openai = await p_openai.health_check()
    results.append(ProviderHealthCheckItem(**h_openai))

    # Mock
    p_mock = MockLLMProvider()
    h_mock = await p_mock.health_check()
    results.append(ProviderHealthCheckItem(**h_mock))

    return APIResponse(success=True, data=results)


@providers_router.post("/providers/health-check", response_model=APIResponse[ProviderHealthCheckItem])
async def check_single_provider_health(provider: str = Query(..., description="Provider name")):
    """Performs an on-demand live health check for a specific provider."""
    p_lower = provider.lower()
    if p_lower == "gemini":
        inst = GeminiProvider()
    elif p_lower == "groq":
        inst = GroqProvider()
    elif p_lower == "openai":
        inst = OpenAIProvider()
    elif p_lower == "mock":
        inst = MockLLMProvider()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    res = await inst.health_check()
    return APIResponse(success=True, data=ProviderHealthCheckItem(**res))


@providers_router.get("/providers/models", response_model=APIResponse[Dict[str, Any]])
async def get_supported_models():
    """Returns administrator-maintained allowlist of verified models per provider."""
    return APIResponse(
        success=True,
        data={
            "models": SUPPORTED_MODELS_ALLOWLIST,
            "pricing_catalog_version": PRICING_CATALOG_V1["version"],
        }
    )


# ==============================================================================
# CONFIGURATION & ROUTING ENDPOINTS
# ==============================================================================

@providers_router.get("/providers/configuration", response_model=APIResponse[Dict[str, Any]])
async def get_provider_configuration():
    """Returns current model routing and fallback chains."""
    return APIResponse(
        success=True,
        data=model_router.config.model_dump(),
    )


@providers_router.put("/providers/configuration", response_model=APIResponse[Dict[str, Any]])
async def update_provider_configuration(payload: ProviderConfigUpdatePayload):
    """Updates runtime model routing and fallback chains with allowlist validation."""
    try:
        updated = model_router.update_configuration(
            default_provider=payload.default_provider,
            default_model=payload.default_model,
            task_routing=payload.task_routing,
            fallback_chains=payload.fallback_chains,
        )
        return APIResponse(
            success=True,
            message="Model routing configuration successfully updated.",
            data=updated.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==============================================================================
# INVOCATIONS & TELEMETRY OBSERVABILITY ENDPOINTS
# ==============================================================================

@providers_router.get("/llm/invocations", response_model=APIResponse[List[Dict[str, Any]]])
async def list_llm_invocations(
    provider: Optional[str] = None,
    trace_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Lists persisted LLM provider invocations with authentic token metadata."""
    stmt = select(LLMInvocation).order_by(desc(LLMInvocation.started_at))

    if provider:
        stmt = stmt.where(LLMInvocation.provider == provider.lower())
    if trace_id:
        stmt = stmt.where(LLMInvocation.trace_id == trace_id)
    if status:
        stmt = stmt.where(LLMInvocation.status == status.upper())

    stmt = stmt.offset(offset).limit(limit)
    res = await db.execute(stmt)
    invocations = res.scalars().all()

    data = [
        {
            "id": inv.id,
            "trace_id": inv.trace_id,
            "span_id": inv.span_id,
            "request_id": inv.request_id,
            "agent_id": inv.agent_id,
            "provider": inv.provider,
            "model": inv.model,
            "task_type": inv.task_type,
            "input_tokens": inv.input_tokens,
            "output_tokens": inv.output_tokens,
            "total_tokens": inv.total_tokens,
            "latency_ms": inv.latency_ms,
            "provider_request_id": inv.provider_request_id,
            "finish_reason": inv.finish_reason,
            "status": inv.status,
            "error_message": inv.error_message,
            "error_category": inv.error_category,
            "retry_count": inv.retry_count,
            "fallback_occurred": inv.fallback_occurred,
            "is_mock": inv.is_mock,
            "started_at": inv.started_at.isoformat() if inv.started_at else None,
            "completed_at": inv.completed_at.isoformat() if inv.completed_at else None,
        }
        for inv in invocations
    ]
    return APIResponse(success=True, data=data)


@providers_router.get("/llm/usage", response_model=APIResponse[Dict[str, Any]])
async def get_llm_usage(db: AsyncSession = Depends(get_db)):
    """Returns aggregated token usage grouped by provider from authentic persisted records."""
    stmt = (
        select(
            LLMInvocation.provider,
            func.count(LLMInvocation.id).label("total_calls"),
            func.sum(LLMInvocation.input_tokens).label("sum_input_tokens"),
            func.sum(LLMInvocation.output_tokens).label("sum_output_tokens"),
            func.sum(LLMInvocation.total_tokens).label("sum_total_tokens"),
            func.avg(LLMInvocation.latency_ms).label("avg_latency_ms"),
        )
        .group_by(LLMInvocation.provider)
    )
    res = await db.execute(stmt)
    rows = res.all()

    usage_by_provider = {}
    for r in rows:
        usage_by_provider[r.provider] = {
            "total_calls": r.total_calls or 0,
            "input_tokens": r.sum_input_tokens or 0,
            "output_tokens": r.sum_output_tokens or 0,
            "total_tokens": r.sum_total_tokens or 0,
            "avg_latency_ms": round(r.avg_latency_ms, 2) if r.avg_latency_ms else 0.0,
        }

    return APIResponse(success=True, data={"by_provider": usage_by_provider})


@providers_router.get("/llm/metrics", response_model=APIResponse[Dict[str, Any]])
async def get_llm_metrics(db: AsyncSession = Depends(get_db)):
    """Returns holistic provider metrics including errors and fallback event counts."""
    # Count invocations by status
    stmt_inv = select(LLMInvocation.provider, LLMInvocation.status, func.count(LLMInvocation.id)).group_by(
        LLMInvocation.provider, LLMInvocation.status
    )
    res_inv = await db.execute(stmt_inv)
    inv_rows = res_inv.all()

    # Count fallbacks
    stmt_fb = select(LLMFallbackEvent.primary_provider, func.count(LLMFallbackEvent.id)).group_by(
        LLMFallbackEvent.primary_provider
    )
    res_fb = await db.execute(stmt_fb)
    fb_rows = res_fb.all()

    metrics_by_prov: Dict[str, Dict[str, Any]] = {}
    for p, status, cnt in inv_rows:
        if p not in metrics_by_prov:
            metrics_by_prov[p] = {"success_count": 0, "error_count": 0, "fallback_count": 0}
        if status == "SUCCESS":
            metrics_by_prov[p]["success_count"] += cnt
        else:
            metrics_by_prov[p]["error_count"] += cnt

    for p, cnt in fb_rows:
        if p not in metrics_by_prov:
            metrics_by_prov[p] = {"success_count": 0, "error_count": 0, "fallback_count": 0}
        metrics_by_prov[p]["fallback_count"] += cnt

    return APIResponse(success=True, data={"provider_metrics": metrics_by_prov})


# ==============================================================================
# DASHBOARD INTEGRATION ENDPOINT
# ==============================================================================

@providers_router.get("/dashboard/providers", response_model=APIResponse[Dict[str, Any]])
async def get_dashboard_provider_telemetry(db: AsyncSession = Depends(get_db)):
    """
    Returns authentic database-backed provider distributions for the Overview Dashboard:
    - requests by provider
    - tokens by provider
    - average measured latency by provider
    - error counts
    - fallback counts
    Zero synthetic or hardcoded metrics.
    """
    stmt = (
        select(
            LLMInvocation.provider,
            func.count(LLMInvocation.id).label("requests"),
            func.sum(LLMInvocation.total_tokens).label("total_tokens"),
            func.avg(LLMInvocation.latency_ms).label("avg_latency_ms"),
            func.sum(
                case((LLMInvocation.status != "SUCCESS", 1), else_=0)
            ).label("errors"),
            func.sum(
                case((LLMInvocation.fallback_occurred == True, 1), else_=0)
            ).label("fallbacks"),
        )
        .group_by(LLMInvocation.provider)
    )
    res = await db.execute(stmt)
    rows = res.all()

    distribution = []
    for r in rows:
        distribution.append({
            "provider": r.provider,
            "requests": r.requests or 0,
            "total_tokens": r.total_tokens or 0,
            "avg_latency_ms": round(r.avg_latency_ms, 2) if r.avg_latency_ms else 0.0,
            "errors": r.errors or 0,
            "fallbacks": r.fallbacks or 0,
        })

    is_empty = (len(distribution) == 0)

    return APIResponse(
        success=True,
        data={
            "is_fresh_zero_state": is_empty,
            "providers": distribution,
        }
    )


# ==============================================================================
# BENCHMARK COMPARISON ENDPOINTS
# ==============================================================================

@providers_router.get("/llm/benchmarks", response_model=APIResponse[List[Dict[str, Any]]])
async def list_benchmarks(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Lists past Multi-LLM provider benchmark runs."""
    runs = await provider_benchmark_engine.list_benchmark_runs(db, limit=limit)
    data = [
        {
            "id": r.id,
            "dataset_name": r.dataset_name,
            "dataset_version": r.dataset_version,
            "prompt_version": r.prompt_version,
            "selected_providers": r.selected_providers,
            "total_samples": r.total_samples,
            "status": r.status,
            "pricing_source": r.pricing_source,
            "pricing_version": r.pricing_version,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]
    return APIResponse(success=True, data=data)


@providers_router.get("/llm/benchmarks/{run_id}", response_model=APIResponse[Dict[str, Any]])
async def get_benchmark_details(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns detailed comparison scorecards for a specific benchmark run."""
    details = await provider_benchmark_engine.get_benchmark_details(db, run_id)
    if not details:
        raise HTTPException(status_code=404, detail=f"Benchmark run '{run_id}' not found.")
    return APIResponse(success=True, data=details)


@providers_router.post("/llm/benchmarks/run", response_model=APIResponse[Dict[str, Any]])
async def run_provider_benchmark(
    payload: BenchmarkRunRequestPayload,
    db: AsyncSession = Depends(get_db),
):
    """Executes identical benchmark dataset against selected LLM providers."""
    run_entity = await provider_benchmark_engine.run_benchmark(
        db=db,
        providers_to_test=payload.providers,
        dataset_name=payload.dataset_name or "SentinelAI Standard Multi-LLM Benchmark",
        dataset_version=payload.dataset_version or "v1.0",
        prompt_version=payload.prompt_version or "v1.0",
        is_mock=payload.is_mock or False,
    )
    details = await provider_benchmark_engine.get_benchmark_details(db, run_entity.id)
    return APIResponse(
        success=True,
        message="Multi-LLM Benchmark successfully executed.",
        data=details,
    )
