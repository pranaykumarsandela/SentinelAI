from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from backend.app.evaluation.regression_engine import RegressionComparisonReport


class EvaluationRunRequest(BaseModel):
    run_type: str = Field(default="SECURITY", pattern="^(RAG|SECURITY|FULL)$")
    dataset_name: Optional[str] = None
    agent_id: Optional[str] = None
    is_mock: bool = True
    custom_cases: Optional[List[Dict[str, Any]]] = None


class EvaluationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sample_id: str
    category: str
    input_prompt: str
    expected_behavior: str
    actual_output: Optional[str] = None
    passed: bool
    metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: Optional[str] = None
    dataset_name: str
    dataset_version: str
    run_type: str
    model_identifier: str
    prompt_version: str
    total_samples: int
    passed_samples: int
    status: str
    faithfulness_score: Optional[float] = None
    relevance_score: Optional[float] = None
    context_precision_score: Optional[float] = None
    context_recall_score: Optional[float] = None
    security_precision: Optional[float] = None
    security_recall: Optional[float] = None
    security_f1: Optional[float] = None
    security_fpr: Optional[float] = None
    security_robustness_score: Optional[float] = None
    confusion_matrix: Optional[Dict[str, Any]] = None
    errors: Optional[Dict[str, Any]] = None
    is_mock: bool
    started_at: datetime
    completed_at: Optional[datetime] = None


class EvaluationRunDetailRead(EvaluationRunRead):
    results: List[EvaluationResultRead] = []

