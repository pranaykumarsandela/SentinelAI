import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import SecurityEvent, SecuritySeverity, SecurityEventType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SecurityEventRecorder:
    """
    Audit and Event Persistence Recorder for SentinelAI Security Engine.
    Ensures:
    - Sensitive evidence is redacted before database persistence.
    - Full traceability with trace_id, agent_id, and request_id.
    - Zero synthetic or random events (Mandatory Data Integrity Policy).
    """

    REDACTION_PATTERNS = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
        (r"\b\d{13,19}\b", "[REDACTED_PAN]"),
        (r"\b(sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})\b", "[REDACTED_API_KEY]"),
        (r"(?i)(password|secret|token)\s*[:=]\s*['\"][^'\"]+['\"]", r"\1=[REDACTED]"),
    ]

    def _sanitize_details(self, details: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Recursively sanitizes dictionary payloads to redact raw secrets."""
        if not details:
            return None

        sanitized = {}
        for k, v in details.items():
            if isinstance(v, str):
                cleaned_str = v
                for pattern, repl in self.REDACTION_PATTERNS:
                    cleaned_str = re.sub(pattern, repl, cleaned_str)
                sanitized[k] = cleaned_str
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_details(v)
            else:
                sanitized[k] = v
        return sanitized

    async def record_event(
        self,
        session: AsyncSession,
        trace_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        request_id: Optional[str] = None,
        event_type: str = SecurityEventType.PROMPT_INJECTION.value,
        severity: str = SecuritySeverity.HIGH.value,
        confidence_score: float = 1.0,
        detector_name: str = "SecurityGateway",
        detection_method: str = "DETERMINISTIC_HEURISTIC",
        action_taken: str = "BLOCKED",
        details: Optional[Dict[str, Any]] = None,
    ) -> SecurityEvent:
        """Persists a verified security incident with sensitive evidence redaction."""
        cleaned_details = self._sanitize_details(details)

        event = SecurityEvent(
            trace_id=trace_id,
            request_id=request_id,
            agent_id=agent_id,
            event_type=event_type,
            severity=severity,
            confidence_score=round(confidence_score, 4),
            detector_name=detector_name,
            detection_method=detection_method,
            action_taken=action_taken,
            details=cleaned_details,
            created_at=utc_now(),
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event


security_event_recorder = SecurityEventRecorder()
