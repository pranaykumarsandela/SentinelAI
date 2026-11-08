import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from backend.app.core.config import settings
from backend.app.observability.logger import sentinel_logger

logger = logging.getLogger("sentinelai.langfuse")

# Try to import official Langfuse SDK
try:
    from langfuse import Langfuse
    from langfuse.types import TraceContext
    LANGFUSE_SDK_AVAILABLE = True
except ImportError:
    Langfuse = None  # type: ignore
    TraceContext = None  # type: ignore
    LANGFUSE_SDK_AVAILABLE = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_langfuse_trace_id(raw_id: str) -> str:
    """
    Converts a UUID or arbitrary trace string to 32 lowercase hex characters
    conforming strictly to OpenTelemetry and Langfuse trace ID specifications.
    """
    clean = str(raw_id).replace("-", "").strip().lower()
    if len(clean) == 32 and all(c in "0123456789abcdef" for c in clean):
        return clean
    # Fallback to UUIDv5 deterministic 32-char hex
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(raw_id)).hex


def mask_secret(secret: Optional[str]) -> str:
    """Masks API keys and secrets so they are never leaked in logs or API responses."""
    if not secret:
        return ""
    s = secret.strip()
    if len(s) <= 8:
        return "********"
    return f"{s[:6]}...{s[-4:]}"


# Patterns for PII / sensitive credential scrubbing before sending to Langfuse
SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{15,}"), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(?i)(sk-[a-zA-Z0-9_\-]{16,})"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)(pk-[a-zA-Z0-9_\-]{16,})"), "[REDACTED_PUBLIC_KEY]"),
    (re.compile(r"(?i)(gsk_[a-zA-Z0-9_\-]{16,})"), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[REDACTED_CREDIT_CARD]"),
    (re.compile(r"(?i)(password|secret|passwd|token)['\":\s=]+([^,\s\}\]]+)"), r"\1: [REDACTED]"),
]


def sanitize_value(val: Any, max_str_len: int = 1200) -> Any:
    """Recursively redacts secrets and PII from inputs and outputs before forwarding to Langfuse."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool)):
        return val
    if isinstance(val, str):
        sanitized = val
        for pat, repl in SENSITIVE_PATTERNS:
            sanitized = pat.sub(repl, sanitized)
        if len(sanitized) > max_str_len:
            return sanitized[:max_str_len] + "... [TRUNCATED]"
        return sanitized
    if isinstance(val, dict):
        out = {}
        for k, v in val.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "secret", "api_key", "authorization", "token", "jwt")):
                out[k] = "[REDACTED_FIELD]"
            else:
                out[k] = sanitize_value(v, max_str_len=max_str_len)
        return out
    if isinstance(val, (list, tuple)):
        return [sanitize_value(v, max_str_len=max_str_len) for v in val]
    return str(val)


class LangfuseObservabilityService:
    """
    Centralized Langfuse Observability Service for SentinelAI.
    
    Provides production-grade tracing, nested span management, generation telemetry,
    RAG retrieval tracking, security guardrail recording, and evaluation scoring.
    
    Adheres strictly to the SentinelAI Mandatory Data Integrity Policy:
    - Zero Token Fabrication: Captures authentic tokens from provider usage metadata.
    - Zero Credential Leakage: Redacts API keys, secrets, and raw PII.
    - Graceful Degradation: All operations are wrapped in safe error handlers.
      If Langfuse is unavailable, SentinelAI execution continues without disruption.
    """

    def __init__(self):
        self.enabled: bool = False
        self.configured: bool = False
        self.host: str = settings.effective_langfuse_host
        self.public_key: Optional[str] = settings.LANGFUSE_PUBLIC_KEY
        self.secret_key: Optional[str] = settings.LANGFUSE_SECRET_KEY
        self.timeout: float = getattr(settings, "LANGFUSE_TIMEOUT", 5.0)
        self.capture_io: bool = getattr(settings, "LANGFUSE_CAPTURE_INPUT_OUTPUT", True)

        self.client: Optional[Any] = None
        self.last_successful_delivery: Optional[str] = None
        self.total_traces_exported: int = 0
        self.total_failed_deliveries: int = 0
        self.last_error: Optional[str] = None

        # Track active observations by 32-hex trace_id for nested spans
        self._active_observations: Dict[str, Any] = {}
        self._active_spans: Dict[str, Any] = {}

        self.initialize()

    def initialize(self) -> None:
        """Initializes the Langfuse client if enabled and keys are configured."""
        self.enabled = getattr(settings, "LANGFUSE_ENABLED", True)
        self.host = settings.effective_langfuse_host
        self.public_key = settings.LANGFUSE_PUBLIC_KEY
        self.secret_key = settings.LANGFUSE_SECRET_KEY
        self.configured = bool(self.public_key and self.secret_key and LANGFUSE_SDK_AVAILABLE)

        if not self.enabled:
            logger.info("Langfuse Observability is explicitly disabled via configuration.")
            self.client = None
            return

        if not LANGFUSE_SDK_AVAILABLE:
            logger.warning("Langfuse Python SDK is not installed. Observability running in disabled mode.")
            self.client = None
            return

        if not self.configured:
            logger.info("Langfuse credentials not set. Observability running in local database-only mode.")
            self.client = None
            return

        try:
            self.client = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host,
                timeout=self.timeout,
            )
            logger.info(
                f"Langfuse Observability Client initialized successfully. "
                f"Endpoint: {self.host} (Public Key: {mask_secret(self.public_key)})"
            )
        except Exception as e:
            self.configured = False
            self.last_error = str(e)
            logger.warning(f"Failed to initialize Langfuse Client: {e}")
            self.client = None

    @property
    def is_operational(self) -> bool:
        """Returns True if Langfuse is configured, enabled, and the client is ready."""
        return bool(self.enabled and self.configured and self.client is not None)

    # ==========================================================================
    # 1. TRACE LIFECYCLE MANAGEMENT
    # ==========================================================================

    def start_trace(
        self,
        trace_id: str,
        name: str = "SentinelAI Agent Execution",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        input_data: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Starts a root agent observation in Langfuse correlated with SentinelAI's PostgreSQL trace ID.
        Returns the canonical 32-hex Langfuse trace ID.
        """
        if not self.is_operational:
            return None

        clean_tid = to_langfuse_trace_id(trace_id)
        try:
            safe_input = sanitize_value(input_data) if self.capture_io else "[CAPTURE_DISABLED]"
            meta = sanitize_value(metadata or {})
            meta["sentinel_trace_id"] = str(trace_id)
            if user_id:
                meta["user_id"] = user_id
            if session_id:
                meta["session_id"] = session_id
            if tags:
                meta["tags"] = tags

            root_obs = self.client.start_observation(
                trace_context={"trace_id": clean_tid},
                name=name,
                as_type="agent",
                input=safe_input,
                metadata=meta,
            )

            self._active_observations[clean_tid] = root_obs
            return clean_tid
        except Exception as e:
            self.total_failed_deliveries += 1
            self.last_error = str(e)
            logger.warning(f"Failed to start Langfuse trace observation {clean_tid}: {e}")
            return None

    def end_trace(
        self,
        trace_id: str,
        output_data: Optional[Any] = None,
        status: str = "SUCCESS",
        total_tokens: Optional[int] = None,
        total_cost_usd: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Finalizes the root observation and flushes telemetry to Langfuse."""
        if not self.is_operational:
            return

        clean_tid = to_langfuse_trace_id(trace_id)
        root_obs = self._active_observations.pop(clean_tid, None)
        if not root_obs:
            return

        try:
            safe_output = sanitize_value(output_data) if self.capture_io else "[CAPTURE_DISABLED]"
            level = "ERROR" if status in ("BLOCKED", "FAILED", "ERROR") else "DEFAULT"
            status_msg = f"Status: {status}"

            update_kwargs: Dict[str, Any] = {
                "output": safe_output,
                "level": level,
                "status_message": status_msg,
            }

            if metadata:
                update_kwargs["metadata"] = sanitize_value(metadata)

            if total_tokens is not None and total_tokens > 0:
                update_kwargs["usage_details"] = {"total": total_tokens}

            if total_cost_usd is not None and total_cost_usd > 0.0:
                update_kwargs["cost_details"] = {"total": round(total_cost_usd, 6)}

            root_obs.update(**update_kwargs)
            root_obs.end()

            self.total_traces_exported += 1
            self.last_successful_delivery = utc_now_iso()

            # Non-blocking async background flush
            self.flush()
        except Exception as e:
            self.total_failed_deliveries += 1
            self.last_error = str(e)
            logger.warning(f"Failed to end Langfuse trace {clean_tid}: {e}")

    # ==========================================================================
    # 2. NESTED OBSERVATIONS & SPANS
    # ==========================================================================

    def start_span(
        self,
        trace_id: str,
        name: str,
        span_id: Optional[str] = None,
        as_type: str = "span",
        input_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Creates a nested observation (guardrail, retriever, tool, generation, span)."""
        if not self.is_operational:
            return None

        clean_tid = to_langfuse_trace_id(trace_id)
        root_obs = self._active_observations.get(clean_tid)

        try:
            safe_input = sanitize_value(input_data) if self.capture_io else "[CAPTURE_DISABLED]"
            meta = sanitize_value(metadata or {})
            if span_id:
                meta["sentinel_span_id"] = str(span_id)

            if root_obs:
                span_obs = root_obs.start_observation(
                    name=name,
                    as_type=as_type,
                    input=safe_input,
                    metadata=meta,
                )
            else:
                span_obs = self.client.start_observation(
                    trace_context={"trace_id": clean_tid},
                    name=name,
                    as_type=as_type,
                    input=safe_input,
                    metadata=meta,
                )

            span_key = f"{clean_tid}:{span_id or uuid.uuid4().hex[:8]}"
            self._active_spans[span_key] = span_obs
            return span_obs
        except Exception as e:
            self.total_failed_deliveries += 1
            self.last_error = str(e)
            logger.warning(f"Failed to start Langfuse span '{name}' for trace {clean_tid}: {e}")
            return None

    def end_span(
        self,
        span_obs: Any,
        output_data: Optional[Any] = None,
        status: str = "OK",
        metadata: Optional[Dict[str, Any]] = None,
        usage_details: Optional[Dict[str, int]] = None,
        cost_details: Optional[Dict[str, float]] = None,
    ) -> None:
        """Ends an active nested observation."""
        if not self.is_operational or not span_obs:
            return

        try:
            safe_output = sanitize_value(output_data) if self.capture_io else "[CAPTURE_DISABLED]"
            level = "ERROR" if status in ("ERROR", "BLOCKED", "FAILED") else "DEFAULT"

            update_kwargs: Dict[str, Any] = {
                "output": safe_output,
                "level": level,
                "status_message": f"Status: {status}",
            }
            if metadata:
                update_kwargs["metadata"] = sanitize_value(metadata)
            if usage_details:
                update_kwargs["usage_details"] = usage_details
            if cost_details:
                update_kwargs["cost_details"] = cost_details

            span_obs.update(**update_kwargs)
            span_obs.end()
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Failed to end Langfuse span: {e}")

    # ==========================================================================
    # 3. SPECIALIZED DOMAIN RECORDERS
    # ==========================================================================

    def record_llm_generation(
        self,
        trace_id: str,
        name: str,
        provider: str,
        model: str,
        prompt_text: str,
        completion_text: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        latency_ms: Optional[float] = None,
        cost_usd: Optional[float] = None,
        provider_request_id: Optional[str] = None,
        finish_reason: Optional[str] = None,
        is_mock: bool = False,
        fallback_occurred: bool = False,
        temperature: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Records an authentic LLM generation observation in Langfuse.
        Strictly preserves true token counts and pricing details.
        """
        if not self.is_operational:
            return

        clean_tid = to_langfuse_trace_id(trace_id)
        root_obs = self._active_observations.get(clean_tid)

        try:
            safe_prompt = sanitize_value(prompt_text) if self.capture_io else "[CAPTURE_DISABLED]"
            safe_completion = sanitize_value(completion_text) if self.capture_io else "[CAPTURE_DISABLED]"

            meta = sanitize_value(metadata or {})
            meta.update({
                "provider": provider,
                "is_mock": is_mock,
                "fallback_occurred": fallback_occurred,
                "provider_request_id": provider_request_id,
                "finish_reason": finish_reason,
                "latency_ms": latency_ms,
            })

            usage_details: Dict[str, int] = {}
            if input_tokens is not None:
                usage_details["input"] = input_tokens
            if output_tokens is not None:
                usage_details["output"] = output_tokens
            if total_tokens is not None:
                usage_details["total"] = total_tokens

            cost_details = {"total": round(cost_usd, 6)} if cost_usd is not None and cost_usd > 0.0 else None

            gen_kwargs = {
                "name": name,
                "as_type": "generation",
                "model": model,
                "model_parameters": {
                    "provider": provider,
                    "temperature": temperature,
                    "is_mock": is_mock,
                },
                "input": safe_prompt,
                "output": safe_completion,
                "metadata": meta,
                "usage_details": usage_details or None,
                "cost_details": cost_details,
            }

            if root_obs:
                gen_obs = root_obs.start_observation(**gen_kwargs)
            else:
                gen_obs = self.client.start_observation(
                    trace_context={"trace_id": clean_tid},
                    **gen_kwargs,
                )

            gen_obs.end()
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Failed to record LLM generation in Langfuse for trace {clean_tid}: {e}")

    def record_rag_retrieval(
        self,
        trace_id: str,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        strategy: str = "hybrid_bm25_dense_rrf",
        top_k: int = 3,
        latency_ms: Optional[float] = None,
        groundedness_verdict: Optional[str] = None,
    ) -> None:
        """
        Records an Agentic RAG retrieval observation.
        Adheres to privacy constraints: emits chunk IDs and summaries rather than full raw texts.
        """
        if not self.is_operational:
            return

        clean_tid = to_langfuse_trace_id(trace_id)
        root_obs = self._active_observations.get(clean_tid)

        try:
            safe_query = sanitize_value(query)
            # Privacy: serialize chunk references and scores, truncate raw content preview
            chunk_previews = []
            for c in retrieved_chunks:
                chunk_previews.append({
                    "chunk_id": c.get("chunk_id") or c.get("id"),
                    "filename": c.get("filename"),
                    "page_number": c.get("page_number"),
                    "relevance_score": c.get("score"),
                    "content_preview": sanitize_value(c.get("content", ""))[:160],
                })

            retriever_kwargs = {
                "name": "Hybrid RAG Retrieval",
                "as_type": "retriever",
                "input": {"query": safe_query, "strategy": strategy, "top_k": top_k},
                "output": {
                    "retrieved_count": len(retrieved_chunks),
                    "chunks": chunk_previews,
                    "groundedness_verdict": groundedness_verdict,
                },
                "metadata": {
                    "strategy": strategy,
                    "latency_ms": latency_ms,
                    "groundedness_verdict": groundedness_verdict,
                },
            }

            if root_obs:
                r_obs = root_obs.start_observation(**retriever_kwargs)
            else:
                r_obs = self.client.start_observation(
                    trace_context={"trace_id": clean_tid},
                    **retriever_kwargs,
                )
            r_obs.end()
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Failed to record RAG retrieval in Langfuse for trace {clean_tid}: {e}")

    def record_guardrail_decision(
        self,
        trace_id: str,
        stage: str,  # "INPUT_FIREWALL" | "OUTPUT_GUARD" | "INDIRECT_INJECTION"
        verdict: str,  # "ALLOW" | "BLOCK" | "REDACT" | "FLAG"
        violations: List[Dict[str, Any]],
        sanitized_sample: Optional[str] = None,
    ) -> None:
        """Records deterministic firewall and guardrail security decisions."""
        if not self.is_operational:
            return

        clean_tid = to_langfuse_trace_id(trace_id)
        root_obs = self._active_observations.get(clean_tid)

        try:
            is_blocked = verdict in ("BLOCK", "BLOCKED")
            safe_violations = sanitize_value(violations)

            guard_kwargs = {
                "name": f"Guardrail: {stage}",
                "as_type": "guardrail",
                "input": {"stage": stage},
                "output": {
                    "verdict": verdict,
                    "violations_count": len(violations),
                    "violations": safe_violations,
                    "sanitized_sample": sanitize_value(sanitized_sample)[:200] if sanitized_sample else None,
                },
                "level": "ERROR" if is_blocked else ("WARNING" if verdict == "FLAG" else "DEFAULT"),
                "status_message": f"Verdict: {verdict}",
                "metadata": {"stage": stage, "verdict": verdict},
            }

            if root_obs:
                g_obs = root_obs.start_observation(**guard_kwargs)
            else:
                g_obs = self.client.start_observation(
                    trace_context={"trace_id": clean_tid},
                    **guard_kwargs,
                )
            g_obs.end()
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Failed to record guardrail decision in Langfuse: {e}")

    def record_security_event(
        self,
        trace_id: str,
        event_type: str,
        severity: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Records a discrete security threat event in Langfuse."""
        if not self.is_operational:
            return

        clean_tid = to_langfuse_trace_id(trace_id)
        root_obs = self._active_observations.get(clean_tid)

        try:
            safe_details = sanitize_value(details or {})
            level = "ERROR" if severity in ("HIGH", "CRITICAL") else "WARNING"

            event_kwargs = {
                "name": f"Security Event: {event_type}",
                "input": {"event_type": event_type, "severity": severity, "action": action},
                "output": safe_details,
                "level": level,
                "status_message": f"Action Taken: {action}",
                "metadata": {"event_type": event_type, "severity": severity, "action": action},
            }

            if root_obs:
                root_obs.create_event(**event_kwargs)
            else:
                self.client.create_event(
                    trace_context={"trace_id": clean_tid},
                    **event_kwargs,
                )
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Failed to create security event in Langfuse: {e}")

    def record_evaluation_score(
        self,
        trace_id: str,
        name: str,
        value: Union[float, int, str],
        comment: Optional[str] = None,
        data_type: str = "NUMERIC",
    ) -> None:
        """Records an evaluation score (e.g. RAGAS Faithfulness, Relevancy, Precision) linked to a trace."""
        if not self.is_operational:
            return

        clean_tid = to_langfuse_trace_id(trace_id)
        try:
            self.client.create_score(
                trace_id=clean_tid,
                name=name,
                value=value,
                comment=comment,
                data_type=data_type,
            )
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Failed to record evaluation score '{name}' in Langfuse for trace {clean_tid}: {e}")

    # ==========================================================================
    # 4. HEALTH & TELEMETRY OBSERVABILITY
    # ==========================================================================

    async def health_check(self) -> Dict[str, Any]:
        """
        Performs a live connectivity and authentication check with the Langfuse server.
        Never throws; returns clean structured status.
        """
        if not self.enabled:
            return {
                "enabled": False,
                "configured": False,
                "status": "DISABLED",
                "host": self.host,
                "public_key_masked": mask_secret(self.public_key),
                "latency_ms": None,
                "message": "Langfuse is explicitly disabled (LANGFUSE_ENABLED=false)",
                "timestamp": time.time(),
            }

        if not self.configured or not self.client:
            return {
                "enabled": True,
                "configured": False,
                "status": "NOT_CONFIGURED",
                "host": self.host,
                "public_key_masked": mask_secret(self.public_key),
                "latency_ms": None,
                "message": "Langfuse credentials not set (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY missing)",
                "timestamp": time.time(),
            }

        start_t = time.perf_counter()
        try:
            # client.auth_check() is a synchronous call in Langfuse SDK
            is_valid = self.client.auth_check()
            latency = round((time.perf_counter() - start_t) * 1000, 2)

            if is_valid:
                return {
                    "enabled": True,
                    "configured": True,
                    "status": "HEALTHY",
                    "host": self.host,
                    "public_key_masked": mask_secret(self.public_key),
                    "latency_ms": latency,
                    "message": "Connected and authenticated with Langfuse Cloud",
                    "timestamp": time.time(),
                }
            else:
                return {
                    "enabled": True,
                    "configured": True,
                    "status": "UNREACHABLE",
                    "host": self.host,
                    "public_key_masked": mask_secret(self.public_key),
                    "latency_ms": latency,
                    "message": "Authentication failed (Invalid public or secret key)",
                    "timestamp": time.time(),
                }
        except Exception as e:
            latency = round((time.perf_counter() - start_t) * 1000, 2)
            self.last_error = str(e)
            return {
                "enabled": True,
                "configured": True,
                "status": "UNREACHABLE",
                "host": self.host,
                "public_key_masked": mask_secret(self.public_key),
                "latency_ms": latency,
                "message": f"Connection failed: {str(e)[:160]}",
                "timestamp": time.time(),
            }

    def get_trace_url(self, trace_id: str) -> Optional[str]:
        """Returns direct dashboard URL for a trace in Langfuse."""
        if not self.is_operational:
            return None
        clean_tid = to_langfuse_trace_id(trace_id)
        try:
            return self.client.get_trace_url(trace_id=clean_tid)
        except Exception:
            return f"{self.host}/trace/{clean_tid}"

    def flush(self) -> None:
        """Flushes buffered telemetry events to Langfuse."""
        if self.is_operational:
            try:
                self.client.flush()
            except Exception as e:
                logger.warning(f"Error during Langfuse flush: {e}")

    def shutdown(self) -> None:
        """Gracefully shuts down Langfuse client on application termination."""
        if self.is_operational:
            try:
                logger.info("Flushing and shutting down Langfuse client...")
                self.client.flush()
                self.client.shutdown()
            except Exception as e:
                logger.warning(f"Error during Langfuse shutdown: {e}")


# Singleton instance across the application
langfuse_service = LangfuseObservabilityService()
