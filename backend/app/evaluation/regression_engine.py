from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import EvaluationRun, EvaluationResult


class MetricDelta(BaseModel):
    baseline_value: Optional[float]
    candidate_value: Optional[float]
    absolute_delta: Optional[float]
    percentage_change: Optional[float]
    trend: str  # IMPROVED, REGRESSED, UNCHANGED, NOT_APPLICABLE


def compute_delta(baseline: Optional[float], candidate: Optional[float], lower_is_better: bool = False) -> MetricDelta:
    if baseline is None or candidate is None:
        return MetricDelta(
            baseline_value=baseline,
            candidate_value=candidate,
            absolute_delta=None,
            percentage_change=None,
            trend="NOT_APPLICABLE"
        )
    diff = round(candidate - baseline, 4)
    pct = round((diff / baseline) * 100.0, 2) if baseline != 0.0 else None

    if diff == 0.0:
        trend = "UNCHANGED"
    elif diff > 0.0:
        trend = "REGRESSED" if lower_is_better else "IMPROVED"
    else:
        trend = "IMPROVED" if lower_is_better else "REGRESSED"

    return MetricDelta(
        baseline_value=baseline,
        candidate_value=candidate,
        absolute_delta=diff,
        percentage_change=pct,
        trend=trend
    )


class TestCaseRegressionItem(BaseModel):
    sample_id: str
    category: str
    input_prompt: str
    baseline_status: str  # PASSED, FAILED
    candidate_status: str  # PASSED, FAILED
    status_change: str  # NEW_REGRESSION, NEW_FIX, PERSISTENT_FAILURE


class RegressionComparisonReport(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    dataset_name: str
    is_dataset_compatible: bool
    model_configuration_changes: Dict[str, Any]
    
    # Metric Deltas
    faithfulness_delta: MetricDelta
    relevance_delta: MetricDelta
    context_precision_delta: MetricDelta
    context_recall_delta: MetricDelta
    security_precision_delta: MetricDelta
    security_recall_delta: MetricDelta
    security_fpr_delta: MetricDelta
    security_robustness_delta: MetricDelta
    
    # Regression Findings
    total_regressions: int
    total_fixes: int
    regressed_cases: List[TestCaseRegressionItem]
    fixed_cases: List[TestCaseRegressionItem]
    recommendation: str


class RegressionEvaluationEngine:
    """
    Compares two authentic evaluation runs to detect performance or security regressions.
    Validates dataset compatibility and identifies newly broken test cases.
    """

    async def compare_runs(
        self,
        session: AsyncSession,
        baseline_run_id: str,
        candidate_run_id: str,
    ) -> RegressionComparisonReport:
        # Fetch both runs with test results
        stmt_b = select(EvaluationRun).options(selectinload(EvaluationRun.results)).where(EvaluationRun.id == baseline_run_id)
        stmt_c = select(EvaluationRun).options(selectinload(EvaluationRun.results)).where(EvaluationRun.id == candidate_run_id)

        res_b = (await session.execute(stmt_b)).scalar_one_or_none()
        res_c = (await session.execute(stmt_c)).scalar_one_or_none()

        if not res_b:
            raise ValueError(f"Baseline evaluation run '{baseline_run_id}' not found.")
        if not res_c:
            raise ValueError(f"Candidate evaluation run '{candidate_run_id}' not found.")

        # Check dataset compatibility
        is_compat = (res_b.dataset_name == res_c.dataset_name) and (res_b.dataset_version == res_c.dataset_version)

        config_changes = {
            "baseline_model": res_b.model_identifier,
            "candidate_model": res_c.model_identifier,
            "model_changed": (res_b.model_identifier != res_c.model_identifier),
            "baseline_prompt_version": res_b.prompt_version,
            "candidate_prompt_version": res_c.prompt_version,
            "prompt_version_changed": (res_b.prompt_version != res_c.prompt_version),
        }

        # Calculate Metric Deltas
        f_delta = compute_delta(res_b.faithfulness_score, res_c.faithfulness_score)
        r_delta = compute_delta(res_b.relevance_score, res_c.relevance_score)
        cp_delta = compute_delta(res_b.context_precision_score, res_c.context_precision_score)
        cr_delta = compute_delta(res_b.context_recall_score, res_c.context_recall_score)
        
        sp_delta = compute_delta(res_b.security_precision, res_c.security_precision)
        srec_delta = compute_delta(res_b.security_recall, res_c.security_recall)
        sfpr_delta = compute_delta(res_b.security_fpr, res_c.security_fpr, lower_is_better=True)
        srob_delta = compute_delta(res_b.security_robustness_score, res_c.security_robustness_score)

        # Map baseline sample results
        baseline_samples = {r.sample_id: r for r in res_b.results}
        candidate_samples = {r.sample_id: r for r in res_c.results}

        regressed_cases: List[TestCaseRegressionItem] = []
        fixed_cases: List[TestCaseRegressionItem] = []

        for sid, cand_res in candidate_samples.items():
            base_res = baseline_samples.get(sid)
            if base_res:
                if base_res.passed and not cand_res.passed:
                    regressed_cases.append(
                        TestCaseRegressionItem(
                            sample_id=sid,
                            category=cand_res.category,
                            input_prompt=cand_res.input_prompt,
                            baseline_status="PASSED",
                            candidate_status="FAILED",
                            status_change="NEW_REGRESSION"
                        )
                    )
                elif not base_res.passed and cand_res.passed:
                    fixed_cases.append(
                        TestCaseRegressionItem(
                            sample_id=sid,
                            category=cand_res.category,
                            input_prompt=cand_res.input_prompt,
                            baseline_status="FAILED",
                            candidate_status="PASSED",
                            status_change="NEW_FIX"
                        )
                    )

        # High-level recommendation
        if len(regressed_cases) > 0:
            recommendation = f"REJECT: Detected {len(regressed_cases)} regression(s) where candidate model failed previously passing tests."
        elif len(fixed_cases) > 0:
            recommendation = f"PROMOTE: Candidate model fixed {len(fixed_cases)} issue(s) without introducing any regressions."
        else:
            recommendation = "NEUTRAL: Candidate performance is identical to baseline."

        return RegressionComparisonReport(
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            dataset_name=f"{res_b.dataset_name} ({res_b.dataset_version})",
            is_dataset_compatible=is_compat,
            model_configuration_changes=config_changes,
            faithfulness_delta=f_delta,
            relevance_delta=r_delta,
            context_precision_delta=cp_delta,
            context_recall_delta=cr_delta,
            security_precision_delta=sp_delta,
            security_recall_delta=srec_delta,
            security_fpr_delta=sfpr_delta,
            security_robustness_delta=srob_delta,
            total_regressions=len(regressed_cases),
            total_fixes=len(fixed_cases),
            regressed_cases=regressed_cases,
            fixed_cases=fixed_cases,
            recommendation=recommendation
        )


regression_engine = RegressionEvaluationEngine()
