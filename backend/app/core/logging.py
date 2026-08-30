"""Structured JSON logging. Secrets must never reach a log record; callers are
responsible for not passing them, and `SECRET_PATTERN` is a last-resort scrub.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time

_SECRET_PATTERN = re.compile(
    r"(?i)(password|api[_-]?key|token|secret|encryption[_-]?key|authorization)\S*[=:]\s*\S+"
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "component": record.name,
            "message": _SECRET_PATTERN.sub(r"\1=***", record.getMessage()),
        }
        for key in ("operation", "status", "correlation_id", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # uvicorn access logs are noisy JSON-in-JSON; let them ride on our handler.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers[:] = [handler]
        logging.getLogger(name).propagate = False
