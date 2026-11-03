from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import EvaluationRun, EvaluationResult, EvaluationStatus
from backend.app.evaluation.ragas_engine import ragas_engine, RAGASSample
from backend.app.evaluation.security_benchmarks import (
    security_benchmark_runner,
    STANDARD_SECURITY_DATASET,
    SecurityBenchmarkCase,
)
from backend.app.evaluation.regression_engine import regression_engine, RegressionComparisonReport


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Standard RAG Evaluation benchmark samples
STANDARD_RAG_DATASET: List[RAGASSample] = [
    RAGASSample(
        sample_id="RAG-BENCH-001",
        question="What cryptographic technology does SentinelAI implement for cloud data?",
        contexts=[
            "SentinelAI enforces AES-256 encryption at rest and TLS 1.3 for all data in transit across cloud endpoints."
        ],
        answer="SentinelAI utilizes AES-256 encryption for data at rest and TLS 1.3 for data in transit.",
        ground_truth="SentinelAI implements AES-256 for data at rest and TLS 1.3 in transit."
    ),
    RAGASSample(
        sample_id="RAG-BENCH-002",
        question="What are the approval requirements for requesting customer refunds?",
        contexts=[
            "Customer refund operations are classified as critical external actions and strictly require human supervisor authorization."
        ],
        answer="Customer refunds require explicit supervisor authorization before execution.",
        ground_truth="Refund requests require human supervisor approval."
    ),
]


class EvaluationService:
    """Evaluation & Benchmarking Service for SentinelAI."""

    async def run_evaluation(
        self,
        session: AsyncSession,
        run_type: str = "SECURITY",  # RAG, SECURITY, FULL
        dataset_name: Optional[str] = None,
        agent_id: Optional[str] = None,
        is_mock: bool = True,
        custom_cases: Optional[List[Dict[str, Any]]] = None,
    ) -> EvaluationRun:
        run_id = f"eval_{int(utc_now().timestamp())}"
        ds_name = dataset_name or ("Standard-Security-Benchmark" if run_type == "SECURITY" else "Standard-RAGAS-Benchmark")

        eval_run = EvaluationRun(
            agent_id=agent_id,
            dataset_name=ds_name,
            dataset_version="v1.0",
            run_type=run_type,
            model_identifier="mock-sentinel-v1" if is_mock else "production-sentinel-llm",
            prompt_version="v1.0",
            status=EvaluationStatus.RUNNING.value,
            is_mock=is_mock,
            started_at=utc_now(),
        )
        session.add(eval_run)
        await session.flush()
        await session.refresh(eval_run)

        try:
            results_to_save: List[EvaluationResult] = []
            total_cases = 0
            passed_cases = 0

            # 1. Run Security Evaluation if requested
            if run_type in ("SECURITY", "FULL"):
                cases = STANDARD_SECURITY_DATASET
                if custom_cases:
                    cases = [SecurityBenchmarkCase(**c) for c in custom_cases]

                sec_summary = security_benchmark_runner.run_benchmark(cases, dataset_name=ds_name)
                total_cases += sec_summary.total_cases
                passed_cases += sec_summary.passed_cases

                eval_run.security_precision = sec_summary.precision
                eval_run.security_recall = sec_summary.recall
                eval_run.security_f1 = sec_summary.f1_score
                eval_run.security_fpr = sec_summary.false_positive_rate
                eval_run.security_robustness_score = sec_summary.robustness_score
                eval_run.confusion_matrix = sec_summary.confusion_matrix.model_dump()

                for r in sec_summary.case_results:
                    results_to_save.append(
                        EvaluationResult(
                            evaluation_run_id=eval_run.id,
                            sample_id=r.case_id,
                            category=r.category,
                            input_prompt=r.case_id,
                            expected_behavior=r.expected_action,
                            actual_output=r.actual_action,
                            passed=r.passed,
                            metrics=r.details,
                        )
                    )

            # 2. Run RAG Evaluation if requested
            if run_type in ("RAG", "FULL"):
                rag_samples = STANDARD_RAG_DATASET
                f_scores, rel_scores, cp_scores, cr_scores = [], [], [], []

                for sample in rag_samples:
                    m_res = ragas_engine.evaluate_sample(sample)
                    sample_passed = (
                        (m_res.faithfulness is not None and m_res.faithfulness >= 0.75) and
                        (m_res.answer_relevancy is not None and m_res.answer_relevancy >= 0.60)
                    )
                    if sample_passed:
                        passed_cases += 1
                    total_cases += 1

                    if m_res.faithfulness is not None:
                        f_scores.append(m_res.faithfulness)
                    if m_res.answer_relevancy is not None:
                        rel_scores.append(m_res.answer_relevancy)
                    if m_res.context_precision is not None:
                        cp_scores.append(m_res.context_precision)
                    if m_res.context_recall is not None:
                        cr_scores.append(m_res.context_recall)

                    results_to_save.append(
                        EvaluationResult(
                            evaluation_run_id=eval_run.id,
                            sample_id=sample.sample_id,
                            category="RAGAS_METRIC",
                            input_prompt=sample.question,
                            expected_behavior=sample.ground_truth or "Grounded Context",
                            actual_output=sample.answer,
                            passed=sample_passed,
                            metrics=m_res.model_dump(),
                        )
                    )

                eval_run.faithfulness_score = round(sum(f_scores) / len(f_scores), 4) if f_scores else None
                eval_run.relevance_score = round(sum(rel_scores) / len(rel_scores), 4) if rel_scores else None
                eval_run.context_precision_score = round(sum(cp_scores) / len(cp_scores), 4) if cp_scores else None
                eval_run.context_recall_score = round(sum(cr_scores) / len(cr_scores), 4) if cr_scores else None

            eval_run.total_samples = total_cases
            eval_run.passed_samples = passed_cases
            eval_run.status = EvaluationStatus.COMPLETED.value
            eval_run.completed_at = utc_now()

            session.add_all(results_to_save)
            await session.commit()
            await session.refresh(eval_run)
            return eval_run

        except Exception as e:
            eval_run.status = EvaluationStatus.FAILED.value
            eval_run.errors = {"error": str(e)}
            eval_run.completed_at = utc_now()
            await session.commit()
            await session.refresh(eval_run)
            raise

    async def list_runs(
        self,
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[EvaluationRun], int]:
        offset = (page - 1) * page_size
        count_stmt = select(EvaluationRun)
        count_res = await session.execute(count_stmt)
        total = len(count_res.scalars().all())

        stmt = (
            select(EvaluationRun)
            .order_by(desc(EvaluationRun.started_at))
            .offset(offset)
            .limit(page_size)
        )
        res = await session.execute(stmt)
        runs = list(res.scalars().all())
        return runs, total

    async def get_run(
        self,
        session: AsyncSession,
        run_id: str
    ) -> Optional[EvaluationRun]:
        stmt = (
            select(EvaluationRun)
            .options(selectinload(EvaluationRun.results))
            .where(EvaluationRun.id == run_id)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def compare_runs(
        self,
        session: AsyncSession,
        baseline_run_id: str,
        candidate_run_id: str,
    ) -> RegressionComparisonReport:
        return await regression_engine.compare_runs(session, baseline_run_id, candidate_run_id)


evaluation_service = EvaluationService()
