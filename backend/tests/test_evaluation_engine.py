import os
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.entities import Tenant, ExecutionTrace, TraceSpan, ExecutionStatus
from backend.app.evaluation.metrics_calculator import (
    metrics_calculator,
    compute_percentile,
    DashboardOverviewMetrics,
)
from backend.app.evaluation.security_benchmarks import (
    ConfusionMatrix,
    security_benchmark_runner,
    SecurityBenchmarkCase,
)
from backend.app.evaluation.ragas_engine import ragas_engine, RAGASSample
from backend.app.evaluation.service import evaluation_service


# --- Module 7: Evaluation & Metrics Tests ---

def test_percentile_latency_calculation():
    # Known 10-element distribution
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p50 = compute_percentile(latencies, 50.0)
    p95 = compute_percentile(latencies, 95.0)
    p99 = compute_percentile(latencies, 99.0)

    assert p50 == 55.0
    assert p95 == 95.5
    assert p99 == 99.1

    # Empty list edge case
    assert compute_percentile([], 50.0) == 0.0

    # Single element edge case
    assert compute_percentile([42.0], 95.0) == 42.0


def test_confusion_matrix_calculations_and_zero_denominators():
    # Standard positive scenario
    matrix = ConfusionMatrix(
        true_positives=8,
        false_positives=2,
        true_negatives=18,
        false_negatives=2
    )
    assert matrix.precision() == 0.8  # 8 / (8 + 2)
    assert matrix.recall() == 0.8     # 8 / (8 + 2)
    assert matrix.f1_score() == 0.8   # 2 * 0.8 * 0.8 / 1.6
    assert matrix.false_positive_rate() == 0.1  # 2 / (2 + 18)
    assert matrix.accuracy() == 0.8667          # 26 / 30

    # Zero denominator edge case: zero detections
    empty_matrix = ConfusionMatrix(
        true_positives=0,
        false_positives=0,
        true_negatives=10,
        false_negatives=5
    )
    # Precision is TP / (TP + FP) = 0 / 0 -> must return None (N/A)
    assert empty_matrix.precision() is None
    assert empty_matrix.f1_score() is None
    assert empty_matrix.recall() == 0.0  # 0 / 5


@pytest.mark.asyncio
async def test_known_fixture_metrics_calculation():
    """
    Test fixture specified in requirements:
    10 requests:
    - 6 successful
    - 2 blocked
    - 2 failed
    Expected API return:
    - Total = 10
    - Successful = 6
    - Blocked = 2
    - Failed = 2
    - Success rate = 75% using (successful + failed) as denominator
    - Blocked rate = 20%
    """
    db_file = "./test_known_fixture.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)

    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            # Create Tenant
            tenant = Tenant(name="Fixture Corp")
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)

            now = datetime.now(timezone.utc)
            traces = []

            # 6 Successful requests
            for i in range(6):
                traces.append(
                    ExecutionTrace(
                        tenant_id=tenant.id,
                        agent_id=tenant.id,
                        input_prompt=f"Valid query {i}",
                        status=ExecutionStatus.SUCCESS.value,
                        is_mock=False,
                        total_tokens=50,
                        prompt_tokens=30,
                        completion_tokens=20,
                        total_latency_ms=100.0 + (i * 10.0),
                        started_at=now - timedelta(minutes=i)
                    )
                )

            # 2 Blocked requests
            for i in range(2):
                traces.append(
                    ExecutionTrace(
                        tenant_id=tenant.id,
                        agent_id=tenant.id,
                        input_prompt=f"Adversarial injection {i}",
                        status=ExecutionStatus.BLOCKED.value,
                        is_mock=False,
                        total_tokens=15,
                        prompt_tokens=15,
                        completion_tokens=0,
                        total_latency_ms=25.0,
                        started_at=now - timedelta(minutes=10 + i)
                    )
                )

            # 2 Failed requests
            for i in range(2):
                traces.append(
                    ExecutionTrace(
                        tenant_id=tenant.id,
                        agent_id=tenant.id,
                        input_prompt=f"Error request {i}",
                        status=ExecutionStatus.ERROR.value,
                        is_mock=False,
                        total_tokens=10,
                        prompt_tokens=10,
                        completion_tokens=0,
                        total_latency_ms=50.0,
                        started_at=now - timedelta(minutes=20 + i)
                    )
                )

            session.add_all(traces)
            await session.commit()

            # Execute calculation via metrics calculator
            metrics = await metrics_calculator.calculate_overview(session=session, environment="live")

            assert metrics.total_requests == 10
            assert metrics.successful_requests == 6
            assert metrics.blocked_requests == 2
            assert metrics.failed_requests == 2
            # Success rate: 6 / (6 + 2) = 75.0%
            assert metrics.success_rate_percent == 75.0
            # Blocked rate: 2 / 10 = 20.0%
            assert metrics.blocked_rate_percent == 20.0
            assert metrics.total_tokens_consumed == (6 * 50) + (2 * 15) + (2 * 10)
            assert metrics.is_fresh_install_zero_state is False

    finally:
        await test_engine.dispose()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except OSError:
                pass


@pytest.mark.asyncio
async def test_fresh_install_zero_metrics():
    """Verifies that an empty database returns verified zeroes without errors."""
    db_file = "./test_fresh_zero.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)

    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            metrics = await metrics_calculator.calculate_overview(session=session, environment="all")
            assert metrics.total_requests == 0
            assert metrics.successful_requests == 0
            assert metrics.blocked_requests == 0
            assert metrics.failed_requests == 0
            assert metrics.success_rate_percent is None
            assert metrics.blocked_rate_percent is None
            assert metrics.avg_latency_ms == 0.0
            assert metrics.total_tokens_consumed == 0
            assert metrics.is_fresh_install_zero_state is True
    finally:
        await test_engine.dispose()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except OSError:
                pass


def test_ragas_evaluation_engine_metrics():
    # 1. Grounded & Relevant Sample
    grounded_sample = RAGASSample(
        sample_id="SAMPLE-01",
        question="What is the data retention policy for audit logs?",
        contexts=[
            "SentinelAI retains audit logs for a minimum of 365 days in encrypted immutable cold storage."
        ],
        answer="Audit logs are retained for 365 days in encrypted immutable cold storage.",
        ground_truth="Audit logs must be retained for 365 days in cold storage."
    )
    result = ragas_engine.evaluate_sample(grounded_sample)
    assert result.faithfulness is not None and result.faithfulness >= 0.8
    assert result.answer_relevancy is not None and result.answer_relevancy >= 0.6
    assert result.context_precision is not None and result.context_precision > 0.0
    assert result.context_recall is not None and result.context_recall > 0.0

    # 2. Missing Context Edge Case (Must return None with honest reason)
    empty_ctx_sample = RAGASSample(
        sample_id="SAMPLE-EMPTY",
        question="What is SentinelAI?",
        contexts=[],
        answer="SentinelAI is a platform.",
        ground_truth="SentinelAI is a security gateway."
    )
    res_empty = ragas_engine.evaluate_sample(empty_ctx_sample)
    assert res_empty.faithfulness is None
    assert "N/A: Retrieved context is empty" in res_empty.faithfulness_reason


@pytest.mark.asyncio
async def test_regression_comparison_engine():
    db_file = "./test_regression_eval.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)

    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            # Run Baseline Benchmark
            baseline = await evaluation_service.run_evaluation(
                session=session,
                run_type="SECURITY",
                dataset_name="Security-Test-v1",
                is_mock=True
            )

            # Run Candidate Benchmark
            candidate = await evaluation_service.run_evaluation(
                session=session,
                run_type="SECURITY",
                dataset_name="Security-Test-v1",
                is_mock=True
            )

            # Compare runs
            report = await evaluation_service.compare_runs(
                session=session,
                baseline_run_id=baseline.id,
                candidate_run_id=candidate.id
            )

            assert report.is_dataset_compatible is True
            assert report.baseline_run_id == baseline.id
            assert report.candidate_run_id == candidate.id
            assert report.security_precision_delta.trend in ("UNCHANGED", "IMPROVED", "REGRESSED")
            assert report.total_regressions == 0  # Identical runs have 0 regressions

    finally:
        await test_engine.dispose()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except OSError:
                pass


@pytest.mark.asyncio
async def test_evaluations_and_dashboard_api_endpoints():
    db_file = "./test_eval_api.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)

    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Initial Dashboard Overview (Fresh install state)
            res_overview = await client.get("/api/v1/dashboard/overview?environment=all")
            assert res_overview.status_code == 200
            ov_data = res_overview.json()["data"]
            assert ov_data["total_requests"] == 0
            assert ov_data["is_fresh_install_zero_state"] is True

            # 2. Trigger Real Benchmark Evaluation
            res_eval = await client.post(
                "/api/v1/evaluations/run",
                json={"run_type": "SECURITY", "dataset_name": "Standard-Security-Benchmark", "is_mock": True}
            )
            assert res_eval.status_code == 201
            eval_data = res_eval.json()["data"]
            eval_id = eval_data["id"]
            assert eval_data["status"] == "COMPLETED"
            assert eval_data["total_samples"] > 0
            assert eval_data["security_precision"] is not None

            # 3. List Evaluation Runs
            res_runs = await client.get("/api/v1/evaluations/runs")
            assert res_runs.status_code == 200
            assert res_runs.json()["data"]["total"] >= 1

            # 4. Get Evaluation Run Detail (verifying individual samples)
            res_detail = await client.get(f"/api/v1/evaluations/runs/{eval_id}")
            assert res_detail.status_code == 200
            detail_data = res_detail.json()["data"]
            assert len(detail_data["results"]) > 0

            # 5. Get Aggregated Evaluation Metrics
            res_metrics = await client.get("/api/v1/evaluations/metrics")
            assert res_metrics.status_code == 200
            assert res_metrics.json()["data"]["total_completed_runs"] >= 1

    finally:
        app.dependency_overrides.clear()
        await test_engine.dispose()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except OSError:
                pass
