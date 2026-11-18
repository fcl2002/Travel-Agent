"""JSON application logs with request context and explicitly allowed fields."""

from contextvars import ContextVar
from datetime import UTC, datetime
import json
import logging
import sys
import traceback

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        identifier = request_id.get()
        if identifier is not None:
            entry["request_id"] = identifier
        for name in ("method", "route", "status_code", "duration_ms", "error_type"):
            if hasattr(record, name):
                entry[name] = getattr(record, name)
        if record.exc_info:
            exception_type, _, exception_traceback = record.exc_info
            entry["error_type"] = exception_type.__name__
            # Exception messages and source lines can contain credentials or SQL values.
            entry["traceback"] = [
                {"file": frame.filename, "line": frame.lineno, "function": frame.name}
                for frame in traceback.extract_tb(exception_traceback)
            ]
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Configure only application logs, leaving third-party loggers to their owners."""
    logger = logging.getLogger("app")
    logger.setLevel(level)
    logger.propagate = False
    if not any(handler.name == "travel_agent_json" for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.set_name("travel_agent_json")
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
