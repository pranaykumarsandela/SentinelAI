from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.common import APIResponse, PaginatedResponse
from backend.app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunRead,
    EvaluationRunDetailRead,
)
from backend.app.evaluation.service import evaluation_service
from backend.app.evaluation.regression_engine import RegressionComparisonReport
from backend.app.evaluation.security_benchmarks import STANDARD_SECURITY_DATASET, SecurityBenchmarkCase

evaluations_router = APIRouter(prefix="/evaluations", tags=["Evaluations & Benchmarks"])


@evaluations_router.post("/run", response_model=APIResponse[EvaluationRunRead], status_code=status.HTTP_201_CREATED)
async def run_evaluation(
    payload: EvaluationRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a real security or RAGAS evaluation run against labeled benchmark datasets.
    Computes authentic confusion matrix, precision, recall, F1, FPR, faithfulness, and relevancy.
    Zero synthetic scores.
    """
    try:
        run = await evaluation_service.run_evaluation(
            session=db,
            run_type=payload.run_type,
            dataset_name=payload.dataset_name,
            agent_id=payload.agent_id,
            is_mock=payload.is_mock,
            custom_cases=payload.custom_cases,
        )
        return APIResponse(
            success=True,
            message=f"Evaluation run '{run.id}' completed ({run.passed_samples}/{run.total_samples} passed)",
            data=EvaluationRunRead.model_validate(run)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation benchmark failed: {str(e)}"
        )


@evaluations_router.post("/ragas/run", response_model=APIResponse[EvaluationRunRead], status_code=status.HTTP_201_CREATED)
async def run_ragas_evaluation(
    dataset_version: str = Query("v1.0"),
    is_mock: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """Convenience endpoint to trigger automated RAGAS evaluation benchmark."""
    req = EvaluationRunRequest(
        run_type="RAG",
        dataset_name=f"Standard-RAGAS-{dataset_version}",
        is_mock=is_mock,
    )
    return await run_evaluation(payload=req, db=db)


@evaluations_router.post("/security/benchmark", response_model=APIResponse[EvaluationRunRead], status_code=status.HTTP_201_CREATED)
async def run_security_benchmark(
    dataset_version: str = Query("v1.0"),
    is_mock: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """Convenience endpoint to trigger automated Adversarial Security robustness benchmark."""
    req = EvaluationRunRequest(
        run_type="SECURITY",
        dataset_name=f"Standard-Security-{dataset_version}",
        is_mock=is_mock,
    )
    return await run_evaluation(payload=req, db=db)


@evaluations_router.get("/runs", response_model=APIResponse[PaginatedResponse[EvaluationRunRead]])
async def list_evaluation_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List historical evaluation benchmark runs."""
    runs, total = await evaluation_service.list_runs(db, page=page, page_size=page_size)
    items = [EvaluationRunRead.model_validate(r) for r in runs]
    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size < total)
        )
    )


@evaluations_router.get("/runs/{run_id}", response_model=APIResponse[EvaluationRunDetailRead])
async def get_evaluation_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full evaluation run details including individual test sample outcomes."""
    run = await evaluation_service.get_run(db, run_id=run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run '{run_id}' not found."
        )
    return APIResponse(
        success=True,
        data=EvaluationRunDetailRead.model_validate(run)
    )


@evaluations_router.get("/compare", response_model=APIResponse[RegressionComparisonReport])
async def compare_evaluation_runs(
    baseline_run_id: str = Query(..., description="UUID of the baseline evaluation run"),
    candidate_run_id: str = Query(..., description="UUID of the candidate evaluation run"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compares two authentic evaluation runs to detect performance, accuracy, or security regressions.
    Discloses model differences and identifies newly broken test cases.
    """
    try:
        report = await evaluation_service.compare_runs(
            session=db,
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
        )
        return APIResponse(
            success=True,
            message="Regression comparison completed",
            data=report
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Regression comparison failed: {str(e)}"
        )


class CompareRunsPayload(BaseModel):
    baseline_run_id: str
    candidate_run_id: str


@evaluations_router.post("/compare", response_model=APIResponse[RegressionComparisonReport])
async def compare_evaluation_runs_post(
    payload: CompareRunsPayload,
    db: AsyncSession = Depends(get_db),
):
    """POST endpoint for comparing two evaluation runs with request body."""
    return await compare_evaluation_runs(
        baseline_run_id=payload.baseline_run_id,
        candidate_run_id=payload.candidate_run_id,
        db=db,
    )


@evaluations_router.get("/metrics", response_model=APIResponse[dict])
async def get_evaluation_metrics_summary(
    db: AsyncSession = Depends(get_db),
):
    """Aggregates security accuracy and RAG scores across completed evaluation runs."""
    runs, total = await evaluation_service.list_runs(db, page=1, page_size=100)
    completed_runs = [r for r in runs if r.status == "COMPLETED"]

    if not completed_runs:
        return APIResponse(
            success=True,
            data={
                "total_completed_runs": 0,
                "avg_faithfulness": None,
                "avg_relevance": None,
                "avg_security_robustness": None,
                "avg_security_precision": None,
                "avg_security_recall": None,
            }
        )

    f_vals = [r.faithfulness_score for r in completed_runs if r.faithfulness_score is not None]
    r_vals = [r.relevance_score for r in completed_runs if r.relevance_score is not None]
    s_vals = [r.security_robustness_score for r in completed_runs if r.security_robustness_score is not None]
    sp_vals = [r.security_precision for r in completed_runs if r.security_precision is not None]
    sr_vals = [r.security_recall for r in completed_runs if r.security_recall is not None]

    return APIResponse(
        success=True,
        data={
            "total_completed_runs": len(completed_runs),
            "avg_faithfulness": round(sum(f_vals) / len(f_vals), 4) if f_vals else None,
            "avg_relevance": round(sum(r_vals) / len(r_vals), 4) if r_vals else None,
            "avg_security_robustness": round(sum(s_vals) / len(s_vals), 4) if s_vals else None,
            "avg_security_precision": round(sum(sp_vals) / len(sp_vals), 4) if sp_vals else None,
            "avg_security_recall": round(sum(sr_vals) / len(sr_vals), 4) if sr_vals else None,
        }
    )


@evaluations_router.get("/benchmarks/cases", response_model=APIResponse[List[SecurityBenchmarkCase]])
async def list_benchmark_cases():
    """Lists the standard labeled adversarial benchmark cases for Red Team Lab testing."""
    return APIResponse(
        success=True,
        data=STANDARD_SECURITY_DATASET,
    )


