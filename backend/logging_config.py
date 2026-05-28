"""
Structured logging with request-id tracing.
"""
import logging
import sys
import time
import uuid
from contextvars import ContextVar

# Context-local request ID — accessible from any module without passing it around
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(rid: str | None = None) -> str:
    rid = rid or uuid.uuid4().hex[:12]
    _request_id.set(rid)
    return rid


def get_request_id() -> str:
    return _request_id.get()


class _StructuredFormatter(logging.Formatter):
    """Key=value structured log format, parseable by log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created))
        ms = int((record.created - int(record.created)) * 1000)
        rid = get_request_id()
        return (
            f"ts={ts}.{ms:03d} "
            f"level={record.levelname} "
            f"rid={rid} "
            f"logger={record.name} "
            f"msg={record.getMessage()}"
        )


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_StructuredFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to avoid duplicates
    root.handlers.clear()
    root.addHandler(handler)
    # Quiet down noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
