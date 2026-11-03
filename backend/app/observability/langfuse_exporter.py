import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

try:
    from backend.app.core.config import settings
    from backend.app.models.entities import ExecutionTrace, TraceSpan
except ImportError:
    from app.core.config import settings
    from app.models.entities import ExecutionTrace, TraceSpan

logger = logging.getLogger("sentinelai.observability")


class LangfuseTraceExporter:
    """
    Exports SentinelAI execution traces to Langfuse or OpenTelemetry-compatible collector.
    Strictly preserves actual timestamps, tokens, and span durations.
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
    ):
        self.public_key = public_key or settings.LANGFUSE_PUBLIC_KEY
        self.secret_key = secret_key or settings.LANGFUSE_SECRET_KEY
        self.host = (host or settings.LANGFUSE_HOST).rstrip("/")
        self.is_configured = bool(self.public_key and self.secret_key)

    def format_trace_for_export(
        self,
        trace: ExecutionTrace,
        spans: List[TraceSpan],
    ) -> Dict[str, Any]:
        """Convert trace and spans into a standard OpenTelemetry/Langfuse trace document."""
        formatted_spans = []
        for s in spans:
            formatted_spans.append({
                "id": s.id,
                "trace_id": s.trace_id,
                "parent_id": s.parent_span_id,
                "name": s.name,
                "type": s.span_type,
                "start_time": s.created_at.isoformat() if s.created_at else None,
                "latency_ms": s.latency_ms,
                "tokens": s.tokens,
                "status": s.status,
                "input": s.input_data,
                "output": s.output_data,
            })

        return {
            "id": trace.id,
            "agent_id": trace.agent_id,
            "tenant_id": trace.tenant_id,
            "session_id": trace.session_id,
            "status": trace.status,
            "is_mock": trace.is_mock,
            "input": trace.input_prompt,
            "sanitized_input": trace.sanitized_input,
            "output": trace.output_response,
            "sanitized_output": trace.sanitized_output,
            "usage": {
                "prompt_tokens": trace.prompt_tokens,
                "completion_tokens": trace.completion_tokens,
                "total_tokens": trace.total_tokens,
            },
            "metrics": {
                "total_latency_ms": trace.total_latency_ms,
                "estimated_cost_usd": trace.estimated_cost_usd,
            },
            "timestamps": {
                "started_at": trace.started_at.isoformat() if trace.started_at else None,
                "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
            },
            "spans": formatted_spans,
        }

    async def export_trace(self, trace_payload: Dict[str, Any]) -> bool:
        """
        Sends trace to remote Langfuse instance if configured.
        Returns True if exported, False otherwise.
        """
        if not self.is_configured:
            return False

        url = f"{self.host}/api/public/ingestion"
        headers = {
            "Content-Type": "application/json",
        }
        auth = (self.public_key, self.secret_key)

        body = {
            "batch": [
                {
                    "id": f"evt-{trace_payload['id']}",
                    "type": "trace-create",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "body": trace_payload,
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=body, headers=headers, auth=auth)
                return resp.status_code in (200, 201, 207)
        except Exception as e:
            logger.warning(f"Failed to export trace to Langfuse: {e}")
            return False


langfuse_exporter = LangfuseTraceExporter()
