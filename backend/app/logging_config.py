from __future__ import annotations

import json
import logging
import logging.config
import os
from datetime import datetime, timezone

from .logging_context import get_job_id, get_request_id, get_session_id

_LOGGING_CONFIGURED = False


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.job_id = get_job_id()
        record.session_id = get_session_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.request_id:
            payload["request_id"] = record.request_id
        if record.job_id:
            payload["job_id"] = record.job_id
        if record.session_id:
            payload["session_id"] = record.session_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "context": {"()": "backend.app.logging_config.ContextFilter"},
        },
        "formatters": {
            "json": {"()": "backend.app.logging_config.JsonFormatter"},
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["context"],
            }
        },
        "root": {
            "handlers": ["default"],
            "level": log_level,
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": log_level, "propagate": False},
            "uvicorn.error": {
                "handlers": ["default"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": log_level,
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)
    _LOGGING_CONFIGURED = True
