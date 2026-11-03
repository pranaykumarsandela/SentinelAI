import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for SentinelAI."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom fields attached to log record
        for key in ["trace_id", "span_id", "agent_id", "tenant_id", "request_id", "is_mock"]:
            val = getattr(record, key, None)
            if val is not None:
                log_obj[key] = val

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_structured_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("sentinelai")
    logger.setLevel(level)
    
    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


sentinel_logger = setup_structured_logging()

