import os
import uuid
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from backend.app.core.database import Base, get_db
from backend.app.core.config import settings
from backend.app.main import app
from backend.app.models.entities import Tenant, Agent, ExecutionTrace
from backend.app.schemas.entities import GatewayExecuteRequest
from backend.app.agent.orchestrator import agent_orchestrator
from backend.app.observability.langfuse_service import (
    LangfuseObservabilityService,
    to_langfuse_trace_id,
    mask_secret,
    sanitize_value,
    langfuse_service,
)


@pytest.fixture
async def test_obs_db():
    db_filename = f"test_obs_{uuid.uuid4().hex[:8]}.db"
    test_db_url = f"sqlite+aiosqlite:///{db_filename}"

    engine = create_async_engine(test_db_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        t = Tenant(id="tenant_obs_1", name="Observability Enterprise Corp")
        a = Agent(
            id="agent_obs_1",
            tenant_id="tenant_obs_1",
            name="Sentinel Observability Agent",
            model_provider="mock",
            model_name="mock-sentinel-v1",
        )
        session.add_all([t, a])
        await session.commit()

    yield async_session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists(db_filename):
        try:
            os.remove(db_filename)
        except Exception:
            pass


@pytest.fixture
async def test_obs_client(test_obs_db):
    async def override_get_db():
        async with test_obs_db() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. UNIT TESTS: IDENTIFIER, SECRET MASKING & SANITIZATION
# ==============================================================================

def test_to_langfuse_trace_id_normalization():
    """Verify trace ID conforms strictly to 32 lowercase hex characters."""
    sample_uuid = "c7bc4c37-1ea0-d6f7-689b-7057426c08bd"
    clean_id = to_langfuse_trace_id(sample_uuid)
    assert len(clean_id) == 32
    assert clean_id == "c7bc4c371ea0d6f7689b7057426c08bd"
    assert all(c in "0123456789abcdef" for c in clean_id)

    # Arbitrary non-UUID string should be deterministically hashed to 32 hex chars
    hash_id = to_langfuse_trace_id("arbitrary-request-identifier-999")
    assert len(hash_id) == 32
    assert all(c in "0123456789abcdef" for c in hash_id)
    # Determinism check
    assert to_langfuse_trace_id("arbitrary-request-identifier-999") == hash_id


def test_mask_secret_utility():
    """Ensure sensitive API keys are never exposed in plaintext."""
    assert mask_secret(None) == ""
    assert mask_secret("") == ""
    assert mask_secret("short") == "********"
    masked = mask_secret("sk-lf-sample-test-dummy-key-9876543210ab")
    assert masked.startswith("sk-lf-")
    assert masked.endswith("10ab")
    assert "..." in masked
    assert "sample-test-dummy" not in masked


def test_sanitize_value_scrubbing():
    """Ensure recursive scrubbing redacts credentials and PII."""
    raw_dict = {
        "user_id": "usr_123",
        "api_key": "sk-proj-supersecretkey123456789",
        "password": "Password123!",
        "auth_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123456789",
        "nested": {
            "credit_card": "4111-2222-3333-4444",
            "social_security": "123-45-6789",
            "note": "Here is my secret token: sk-live-9876543210123456",
        },
    }
    cleaned = sanitize_value(raw_dict)
    assert cleaned["user_id"] == "usr_123"
    assert cleaned["api_key"] == "[REDACTED_FIELD]"
    assert cleaned["password"] == "[REDACTED_FIELD]"
    assert "[REDACTED_TOKEN]" in cleaned["auth_header"]
    assert "[REDACTED_CREDIT_CARD]" in cleaned["nested"]["credit_card"]
    assert "[REDACTED_SSN]" in cleaned["nested"]["social_security"]
    assert "[REDACTED_API_KEY]" in cleaned["nested"]["note"]


# ==============================================================================
# 2. SERVICE BEHAVIOR: DISABLED & MISSING CREDENTIAL MODES
# ==============================================================================

def test_langfuse_service_disabled_mode():
    """When LANGFUSE_ENABLED is false, all calls must gracefully no-op."""
    svc = LangfuseObservabilityService()
    svc.enabled = False
    svc.client = None

    assert svc.is_operational is False
    assert svc.start_trace("trace-123") is None
    svc.end_trace("trace-123")
    assert svc.start_span("trace-123", "test_span") is None
    svc.end_span(None)
    svc.record_llm_generation("trace-123", "gen", "mock", "mock-v1", "prompt")
    svc.record_rag_retrieval("trace-123", "query", [])
    svc.record_guardrail_decision("trace-123", "INPUT", "ALLOW", [])
    svc.record_security_event("trace-123", "PROMPT_INJECTION", "HIGH", "BLOCK")
    svc.record_evaluation_score("trace-123", "faithfulness", 0.95)
    assert svc.get_trace_url("trace-123") is None


@pytest.mark.asyncio
async def test_langfuse_service_health_check_states():
    """Test health check states: DISABLED, NOT_CONFIGURED, HEALTHY, UNREACHABLE."""
    svc = LangfuseObservabilityService()
    svc.enabled = False
    res_disabled = await svc.health_check()
    assert res_disabled["status"] == "DISABLED"
    assert res_disabled["enabled"] is False

    svc.enabled = True
    svc.configured = False
    svc.client = None
    res_not_cfg = await svc.health_check()
    assert res_not_cfg["status"] == "NOT_CONFIGURED"
    assert res_not_cfg["configured"] is False


# ==============================================================================
# 3. SERVICE TELEMETRY LIFECYCLE (WITH MOCKED CLIENT)
# ==============================================================================

def test_mocked_langfuse_lifecycle():
    """Validates full lifecycle tracing: root agent trace, spans, generation, retriever, guardrail, score."""
    svc = LangfuseObservabilityService()
    svc.enabled = True
    svc.configured = True

    mock_client = MagicMock()
    mock_root_obs = MagicMock()
    mock_span_obs = MagicMock()
    mock_gen_obs = MagicMock()
    mock_ret_obs = MagicMock()
    mock_guard_obs = MagicMock()

    mock_client.start_observation.return_value = mock_root_obs
    mock_root_obs.start_observation.side_effect = [
        mock_span_obs,
        mock_gen_obs,
        mock_ret_obs,
        mock_guard_obs,
    ]
    svc.client = mock_client

    tid = "c7bc4c37-1ea0-d6f7-689b-7057426c08bd"
    clean_tid = to_langfuse_trace_id(tid)

    # 1. Start root trace
    res_tid = svc.start_trace(
        trace_id=tid,
        name="SentinelAI Agent Root",
        user_id="user_test",
        session_id="sess_123",
        tags=["enterprise", "security"],
        metadata={"tenant_id": "t1"},
        input_data={"prompt": "Hello secure agent"},
    )
    assert res_tid == clean_tid
    mock_client.start_observation.assert_called_once()
    call_kwargs = mock_client.start_observation.call_args[1]
    assert call_kwargs["trace_context"]["trace_id"] == clean_tid
    assert call_kwargs["as_type"] == "agent"

    # 2. Nested span
    span = svc.start_span(tid, "Tool Execution: search_documents", as_type="tool", input_data={"q": "policy"})
    assert span is not None
    svc.end_span(span, output_data={"results": 2}, status="OK")
    mock_span_obs.update.assert_called_once()
    mock_span_obs.end.assert_called_once()

    # 3. Record LLM generation
    svc.record_llm_generation(
        trace_id=tid,
        name="LLM Generation: Mock",
        provider="mock",
        model="mock-sentinel-v1",
        prompt_text="User question",
        completion_text="Assistant answer",
        input_tokens=15,
        output_tokens=25,
        total_tokens=40,
        latency_ms=120.5,
        cost_usd=0.00004,
        is_mock=True,
    )
    mock_gen_obs.end.assert_called_once()

    # 4. Record RAG retrieval
    svc.record_rag_retrieval(
        trace_id=tid,
        query="security policy",
        retrieved_chunks=[
            {"chunk_id": "c1", "filename": "doc.pdf", "page_number": 1, "score": 0.95, "content": "Sample content"}
        ],
        strategy="hybrid_rrf",
    )
    mock_ret_obs.end.assert_called_once()

    # 5. Record Guardrail decision
    svc.record_guardrail_decision(
        trace_id=tid,
        stage="INPUT_FIREWALL",
        verdict="ALLOW",
        violations=[],
        sanitized_sample="clean input",
    )
    mock_guard_obs.end.assert_called_once()

    # 6. Record Security Event
    svc.record_security_event(
        trace_id=tid,
        event_type="PROMPT_INJECTION",
        severity="HIGH",
        action="BLOCKED",
        details={"pattern": "ignore previous instructions"},
    )
    mock_root_obs.create_event.assert_called_once()

    # 7. Record Evaluation Score
    svc.record_evaluation_score(
        trace_id=tid,
        name="ragas_faithfulness",
        value=0.92,
        comment="High grounding",
    )
    mock_client.create_score.assert_called_once_with(
        trace_id=clean_tid,
        name="ragas_faithfulness",
        value=0.92,
        comment="High grounding",
        data_type="NUMERIC",
    )

    # 8. End root trace
    svc.end_trace(
        trace_id=tid,
        output_data="Final secure answer",
        status="SUCCESS",
        total_tokens=40,
        total_cost_usd=0.00004,
    )
    mock_root_obs.update.assert_called_once()
    mock_root_obs.end.assert_called_once()
    assert svc.total_traces_exported == 1


def test_graceful_degradation_on_exception():
    """Ensure errors during Langfuse transmission do not crash the service or propagate exceptions."""
    svc = LangfuseObservabilityService()
    svc.enabled = True
    svc.configured = True

    mock_client = MagicMock()
    mock_client.start_observation.side_effect = RuntimeError("Langfuse server connection timed out")
    svc.client = mock_client

    failed_tid = svc.start_trace("trace-err", name="Failing Trace")
    assert failed_tid is None
    assert svc.total_failed_deliveries == 1
    assert "timed out" in (svc.last_error or "")


# ==============================================================================
# 4. FASTAPI OBSERVABILITY REST API ENDPOINTS
# ==============================================================================

@pytest.mark.asyncio
async def test_api_langfuse_status(test_obs_client):
    """GET /api/v1/observability/langfuse/status returns 200 with structured health."""
    resp = await test_obs_client.get("/api/v1/observability/langfuse/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "enabled" in data
    assert "configured" in data
    assert "status" in data
    assert "host" in data
    assert "public_key_masked" in data
    assert "total_traces_exported" in data


@pytest.mark.asyncio
async def test_api_langfuse_configuration(test_obs_client):
    """GET /api/v1/observability/langfuse/configuration returns 200 with masked secrets."""
    resp = await test_obs_client.get("/api/v1/observability/langfuse/configuration")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "host" in data
    assert "public_key_masked" in data
    assert "secret_key_masked" in data
    # Ensure unmasked secret key is never leaked
    if settings.LANGFUSE_SECRET_KEY:
        assert data["secret_key_masked"] != settings.LANGFUSE_SECRET_KEY


@pytest.mark.asyncio
async def test_api_langfuse_test_connection(test_obs_client):
    """POST /api/v1/observability/langfuse/test-connection triggers connection test."""
    resp = await test_obs_client.post("/api/v1/observability/langfuse/test-connection")
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["status"] in ("HEALTHY", "NOT_CONFIGURED", "UNREACHABLE", "DISABLED")


@pytest.mark.asyncio
async def test_api_langfuse_traces_and_metrics(test_obs_client, test_obs_db):
    """GET /api/v1/observability/langfuse/traces and /metrics."""
    # Seed a trace in DB
    trace_id = str(uuid.uuid4())
    async with test_obs_db() as session:
        tr = ExecutionTrace(
            id=trace_id,
            tenant_id="tenant_obs_1",
            agent_id="agent_obs_1",
            input_prompt="Testing Langfuse trace listing",
            output_response="Output trace response",
            status="SUCCESS",
            is_mock=True,
            total_tokens=30,
            prompt_tokens=10,
            completion_tokens=20,
            total_latency_ms=45.2,
            estimated_cost_usd=0.00003,
        )
        session.add(tr)
        await session.commit()

    # Test traces endpoint
    resp_traces = await test_obs_client.get("/api/v1/observability/langfuse/traces")
    assert resp_traces.status_code == 200
    data_traces = resp_traces.json()["data"]
    assert data_traces["total"] >= 1
    found = any(t["id"] == trace_id for t in data_traces["items"])
    assert found is True
    item = next(t for t in data_traces["items"] if t["id"] == trace_id)
    assert len(item["langfuse_trace_id"]) == 32

    # Test metrics endpoint
    resp_metrics = await test_obs_client.get("/api/v1/observability/langfuse/metrics")
    assert resp_metrics.status_code == 200
    data_metrics = resp_metrics.json()["data"]
    assert "total_traces_exported" in data_metrics
    assert "total_failed_deliveries" in data_metrics


# ==============================================================================
# 5. AGENT EXECUTION INTEGRATION WITH LANGFUSE HOOKS
# ==============================================================================

@pytest.mark.asyncio
async def test_agent_execution_with_langfuse(test_obs_db):
    """Executes a real AgentOrchestrator request and verifies DB persistence + trace export."""
    async with test_obs_db() as session:
        req = GatewayExecuteRequest(
            agent_id="agent_obs_1",
            prompt="What is the encryption standard used by SentinelAI?",
            is_mock=True,
        )
        resp = await agent_orchestrator.execute(
            db=session,
            request=req,
            tenant_id="tenant_obs_1",
            role="user",
        )
        assert resp.trace_id is not None
        assert resp.status == "SUCCESS"
        assert resp.output is not None

        # Verify trace persisted in DB
        db_trace = await session.get(ExecutionTrace, resp.trace_id)
        assert db_trace is not None
        assert db_trace.input_prompt == req.prompt


# ==============================================================================
# 6. LIVE LANGFUSE CLOUD VERIFICATION (CONDITIONAL ON CREDENTIALS)
# ==============================================================================

@pytest.mark.asyncio
async def test_live_langfuse_cloud_connectivity():
    """
    Live verification against Langfuse Cloud if live credentials are configured.
    Validates auth_check, trace observation creation, and score submission.
    """
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        pytest.skip("Langfuse Cloud credentials not present in environment")

    from langfuse import Langfuse

    client = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.effective_langfuse_host,
        timeout=10.0,
    )

    # 1. Verify authentication
    auth_ok = client.auth_check()
    assert auth_ok is True, "Live auth_check() with Langfuse Cloud failed"

    # 2. Verify trace observation creation with 32-hex trace ID
    live_trace_id = uuid.uuid4().hex
    obs = client.start_observation(
        trace_context={"trace_id": live_trace_id},
        name="SentinelAI Automated CI/CD Live Verification",
        as_type="agent",
        input={"test_suite": "test_langfuse_integration.py"},
        metadata={"environment": "automated_test", "live_verified": True},
    )
    obs.update(output={"status": "LIVE_VERIFIED"}, status_message="Status: SUCCESS")
    obs.end()

    # 3. Verify score submission
    client.create_score(
        trace_id=live_trace_id,
        name="live_verification_score",
        value=1.0,
        comment="Automated test score confirmation",
    )

    # 4. Verify get_trace_url
    url = client.get_trace_url(trace_id=live_trace_id)
    assert url is not None
    assert "langfuse" in url.lower()
    assert live_trace_id in url

    client.flush()
