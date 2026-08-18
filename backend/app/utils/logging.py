"""Structured JSON logging setup.

Every module logs via `logger = get_logger(__name__)`; the root handler
emits one JSON object per line, so logs are directly consumable by Cloud
Logging / CloudWatch without a separate shipping agent.

`get_logger()` returns a `StructuredLogger` subclass that accepts arbitrary
keyword fields (e.g. `logger.info("request", method="GET", path="/x")`) and
forwards them into the LogRecord's `extra` dict, where the JSON formatter
picks them up.
"""
import json
import logging
import sys
from datetime import datetime, timezone

_RESERVED_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
    "message",
    "timestamp",
    "level",
    "logger",
    "line",
}

# LogRecord attributes we set ourselves and want in the JSON payload.
_BASE_FIELDS = {"timestamp", "level", "logger", "module", "line", "message"}

_ALWAYS_PASSED = {"exc_info", "stack_info", "stacklevel", "extra"}


class StructuredLogger(logging.Logger):
    """Logger that treats trailing keyword arguments as structured fields."""

    def _log_structured(self, level: int, msg: str, args: tuple, kwargs: dict) -> None:
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        for key, value in list(kwargs.items()):
            if key not in _ALWAYS_PASSED:
                kwargs["extra"].setdefault(key, value)
                del kwargs[key]
        super()._log(level, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        if self.isEnabledFor(logging.INFO):
            self._log_structured(logging.INFO, msg, args, kwargs)

    def warning(self, msg, *args, **kwargs):
        if self.isEnabledFor(logging.WARNING):
            self._log_structured(logging.WARNING, msg, args, kwargs)

    def error(self, msg, *args, **kwargs):
        if self.isEnabledFor(logging.ERROR):
            self._log_structured(logging.ERROR, msg, args, kwargs)

    def debug(self, msg, *args, **kwargs):
        if self.isEnabledFor(logging.DEBUG):
            self._log_structured(logging.DEBUG, msg, args, kwargs)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_KEYS and key not in _BASE_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            try:
                payload["exc_info"] = self.formatException(record.exc_info)
            except Exception:
                payload["exc_info"] = str(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: int = logging.INFO) -> None:
    """Idempotent: installs the JSON formatter + StructuredLogger class once."""
    logging.setLoggerClass(StructuredLogger)
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
