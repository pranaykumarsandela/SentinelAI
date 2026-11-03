from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.common import APIResponse
from backend.app.evaluation.metrics_calculator import (
    metrics_calculator,
    DashboardOverviewMetrics,
    TimeseriesPoint,
)

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard Analytics"])


@dashboard_router.get("/overview", response_model=APIResponse[DashboardOverviewMetrics])
async def get_dashboard_overview(
    environment: str = Query("all", pattern="^(live|mock|all)$", description="Filter by environment partition"),
    tenant_id: Optional[str] = Query(None, description="Filter metrics by tenant ID"),
    hours: Optional[int] = Query(None, ge=1, description="Filter to past N hours"),
    db: AsyncSession = Depends(get_db),
):
    """
    Computes authentic dashboard metrics directly from persisted database records.
    Enforces the Mandatory Data Integrity Policy:
    - Zero counts and null rates for fresh installations.
    - Zero random or fabricated numbers.
    - Segregated live vs. mock environment analytics.
    """
    metrics = await metrics_calculator.calculate_overview(
        session=db,
        environment=environment,
        tenant_id=tenant_id,
        hours=hours,
    )
    return APIResponse(
        success=True,
        message="Dashboard overview metrics calculated",
        data=metrics
    )


@dashboard_router.get("/timeseries", response_model=APIResponse[List[TimeseriesPoint]])
async def get_dashboard_timeseries(
    environment: str = Query("all", pattern="^(live|mock|all)$"),
    tenant_id: Optional[str] = Query(None),
    bucket_hours: int = Query(1, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns authentic time-series request volume, latency, and token consumption points.
    Empty list if no records are found in database.
    """
    points = await metrics_calculator.calculate_timeseries(
        session=db,
        environment=environment,
        tenant_id=tenant_id,
        bucket_hours=bucket_hours,
    )
    return APIResponse(
        success=True,
        data=points
    )

