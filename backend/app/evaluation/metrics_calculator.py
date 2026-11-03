import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.app.models.entities import ExecutionTrace, TraceSpan, SecurityEvent, SpanType, ExecutionStatus


def compute_percentile(values: List[float], percentile: float) -> float:
    """
    Computes exact percentile from a distribution of numeric values.
    Uses linear interpolation between nearest ranks.
    """
    if not values:
        return 0.0
    sorted_v = sorted(values)
    if len(sorted_v) == 1:
        return sorted_v[0]

    k = (len(sorted_v) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(float(sorted_v[int(k)]), 2)
    d0 = sorted_v[int(f)] * (c - k)
    d1 = sorted_v[int(c)] * (k - f)
    return round(float(d0 + d1), 2)


class DashboardOverviewMetrics(BaseModel):
    environment_filter: str  # live, mock, all
    total_requests: int
    successful_requests: int
    blocked_requests: int
    failed_requests: int
    success_rate_percent: Optional[float]
    blocked_rate_percent: Optional[float]
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_tokens_consumed: int
    prompt_tokens: int
    completion_tokens: int
    total_security_threats: int
    avg_tool_duration_ms: float
    sample_size: int
    is_fresh_install_zero_state: bool


class TimeseriesPoint(BaseModel):
    timestamp_bucket: str
    total_requests: int
    successful_requests: int
    blocked_requests: int
    failed_requests: int
    avg_latency_ms: float
    tokens_consumed: int


class MetricsCalculator:
    """
    Execution Metrics & Analytics Aggregator for SentinelAI.
    Calculates authentic dashboard KPIs directly from database tables.
    Never fabricates historical, latency, or token values.
    """

    async def calculate_overview(
        self,
        session: AsyncSession,
        environment: str = "all",  # "live", "mock", "all"
        tenant_id: Optional[str] = None,
        hours: Optional[int] = None,
    ) -> DashboardOverviewMetrics:
        # Base query filters
        filters = []
        if environment == "live":
            filters.append(ExecutionTrace.is_mock == False)
        elif environment == "mock":
            filters.append(ExecutionTrace.is_mock == True)

        if tenant_id:
            filters.append(ExecutionTrace.tenant_id == tenant_id)

        if hours:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            filters.append(ExecutionTrace.started_at >= cutoff)

        stmt = select(ExecutionTrace)
        if filters:
            stmt = stmt.where(and_(*filters))

        res = await session.execute(stmt)
        traces = list(res.scalars().all())

        total = len(traces)
        if total == 0:
            # Fresh install / zero records state: display authentic zeroes
            return DashboardOverviewMetrics(
                environment_filter=environment,
                total_requests=0,
                successful_requests=0,
                blocked_requests=0,
                failed_requests=0,
                success_rate_percent=None,
                blocked_rate_percent=None,
                avg_latency_ms=0.0,
                median_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                total_tokens_consumed=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_security_threats=0,
                avg_tool_duration_ms=0.0,
                sample_size=0,
                is_fresh_install_zero_state=True
            )

        # Compute counts
        successful = sum(1 for t in traces if t.status == ExecutionStatus.SUCCESS.value)
        blocked = sum(1 for t in traces if t.status == ExecutionStatus.BLOCKED.value)
        failed = sum(1 for t in traces if t.status == ExecutionStatus.ERROR.value)

        # Success rate using (successful + failed) as denominator
        active_denom = successful + failed
        success_rate = round((successful / active_denom) * 100.0, 2) if active_denom > 0 else None

        # Blocked rate using total as denominator
        blocked_rate = round((blocked / total) * 100.0, 2)

        # Latency percentiles
        latencies = [t.total_latency_ms for t in traces if t.total_latency_ms is not None]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        p50 = compute_percentile(latencies, 50.0)
        p95 = compute_percentile(latencies, 95.0)
        p99 = compute_percentile(latencies, 99.0)

        # Tokens
        total_tokens = sum(t.total_tokens for t in traces if t.total_tokens is not None)
        p_tokens = sum(t.prompt_tokens for t in traces if t.prompt_tokens is not None)
        c_tokens = sum(t.completion_tokens for t in traces if t.completion_tokens is not None)

        # Security Threats count
        sec_stmt = select(func.count(SecurityEvent.id))
        if tenant_id:
            sec_stmt = sec_stmt.join(ExecutionTrace, SecurityEvent.trace_id == ExecutionTrace.id).where(ExecutionTrace.tenant_id == tenant_id)
        sec_res = await session.execute(sec_stmt)
        threats_count = sec_res.scalar() or 0

        # Tool execution durations from Spans
        span_stmt = select(TraceSpan.latency_ms).where(TraceSpan.span_type == SpanType.TOOL_EXECUTION.value)
        span_res = await session.execute(span_stmt)
        tool_latencies = list(span_res.scalars().all())
        avg_tool_dur = round(sum(tool_latencies) / len(tool_latencies), 2) if tool_latencies else 0.0

        return DashboardOverviewMetrics(
            environment_filter=environment,
            total_requests=total,
            successful_requests=successful,
            blocked_requests=blocked,
            failed_requests=failed,
            success_rate_percent=success_rate,
            blocked_rate_percent=blocked_rate,
            avg_latency_ms=avg_latency,
            median_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            total_tokens_consumed=total_tokens,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_security_threats=threats_count,
            avg_tool_duration_ms=avg_tool_dur,
            sample_size=total,
            is_fresh_install_zero_state=False
        )

    async def calculate_timeseries(
        self,
        session: AsyncSession,
        environment: str = "all",
        tenant_id: Optional[str] = None,
        bucket_hours: int = 1,
    ) -> List[TimeseriesPoint]:
        """Calculates authentic time-series points from recorded traces."""
        filters = []
        if environment == "live":
            filters.append(ExecutionTrace.is_mock == False)
        elif environment == "mock":
            filters.append(ExecutionTrace.is_mock == True)
        if tenant_id:
            filters.append(ExecutionTrace.tenant_id == tenant_id)

        stmt = select(ExecutionTrace).order_by(ExecutionTrace.started_at)
        if filters:
            stmt = stmt.where(and_(*filters))

        res = await session.execute(stmt)
        traces = list(res.scalars().all())

        if not traces:
            return []

        # Group by hourly buckets
        buckets: Dict[str, List[ExecutionTrace]] = {}
        for t in traces:
            if not t.started_at:
                continue
            # ISO hour format YYYY-MM-DDTHH:00:00Z
            bucket_key = t.started_at.strftime("%Y-%m-%dT%H:00:00Z")
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(t)

        series = []
        for b_time, b_traces in sorted(buckets.items()):
            b_total = len(b_traces)
            b_succ = sum(1 for tr in b_traces if tr.status == ExecutionStatus.SUCCESS.value)
            b_block = sum(1 for tr in b_traces if tr.status == ExecutionStatus.BLOCKED.value)
            b_fail = sum(1 for tr in b_traces if tr.status == ExecutionStatus.ERROR.value)
            b_tokens = sum(tr.total_tokens for tr in b_traces if tr.total_tokens is not None)
            lats = [tr.total_latency_ms for tr in b_traces if tr.total_latency_ms is not None]
            b_avg_lat = round(sum(lats) / len(lats), 2) if lats else 0.0

            series.append(
                TimeseriesPoint(
                    timestamp_bucket=b_time,
                    total_requests=b_total,
                    successful_requests=b_succ,
                    blocked_requests=b_block,
                    failed_requests=b_fail,
                    avg_latency_ms=b_avg_lat,
                    tokens_consumed=b_tokens
                )
            )
        return series


metrics_calculator = MetricsCalculator()

