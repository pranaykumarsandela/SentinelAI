import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.main import app
from backend.app.models.entities import Tenant, Agent, SecurityPolicy, ExecutionTrace
from backend.app.services.mock_llm import DeterministicMockLLM


def test_settings_loaded():
    assert settings.PROJECT_NAME == "SentinelAI"
    assert settings.VERSION == "0.1.0"
    assert isinstance(settings.CORS_ORIGINS, list)
    assert len(settings.CORS_ORIGINS) > 0


def test_deterministic_mock_llm():
    mock_llm = DeterministicMockLLM()
    response = mock_llm.generate("Hello SentinelAI, who are you?")
    assert response.is_mock is True
    assert "SentinelAI Mock Agent" in response.content
    assert response.total_tokens > 0
    assert response.latency_ms > 0
    assert response.prompt_tokens == mock_llm._count_tokens("Hello SentinelAI, who are you?")


def test_deterministic_mock_llm_tool_simulation():
    mock_llm = DeterministicMockLLM()
    response = mock_llm.generate(
        "Please check the user profile",
        simulate_tool_call="get_user_profile"
    )
    assert response.is_mock is True
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["name"] == "get_user_profile"


@pytest.mark.asyncio
async def test_database_models_persistence():
    db_file = "./test_sentinel.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            # Create Tenant
            tenant = Tenant(name="Acme Corp")
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            assert tenant.id is not None
            assert tenant.name == "Acme Corp"

            # Create Agent
            agent = Agent(
                tenant_id=tenant.id,
                name="SupportBot",
                model_provider="mock",
                model_name="mock-sentinel-v1"
            )
            session.add(agent)
            await session.commit()
            await session.refresh(agent)
            assert agent.id is not None
            assert agent.tenant_id == tenant.id

            # Create Security Policy
            policy = SecurityPolicy(
                tenant_id=tenant.id,
                name="Default Zero Trust",
                prompt_injection_threshold=0.8,
                is_default=True
            )
            session.add(policy)
            await session.commit()
            await session.refresh(policy)
            assert policy.id is not None
            assert policy.is_default is True

            # Create Execution Trace (verifying Mandatory Data Integrity flag)
            trace = ExecutionTrace(
                tenant_id=tenant.id,
                agent_id=agent.id,
                input_prompt="Test prompt",
                status="SUCCESS",
                is_mock=True,
                total_tokens=15,
                total_latency_ms=1.2
            )
            session.add(trace)
            await session.commit()
            await session.refresh(trace)
            assert trace.id is not None
            assert trace.is_mock is True
            assert trace.total_tokens == 15
    finally:
        await test_engine.dispose()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except OSError:
                pass


@pytest.mark.asyncio
async def test_fastapi_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test Root Endpoint
        res_root = await client.get("/")
        assert res_root.status_code == 200
        root_data = res_root.json()
        assert root_data["status"] == "OPERATIONAL"
        assert root_data["name"] == "SentinelAI"

        # Test Health Endpoint
        res_health = await client.get("/api/v1/health")
        assert res_health.status_code == 200
        health_data = res_health.json()
        assert health_data["success"] is True
        assert health_data["data"]["status"] == "HEALTHY"
