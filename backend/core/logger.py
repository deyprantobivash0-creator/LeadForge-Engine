"""Canonical JSON logging with deliberately bounded, content-free diagnostics."""
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from time import perf_counter

from backend.core.config import settings
from backend.core.redaction import redact

request_id_context = ContextVar("request_id", default=None)
FIELDS = {"method", "path", "status_code", "duration_ms", "organization_id", "user_id",
          "lead_id", "analysis_id", "provider_name", "reason", "exception_type", "stack",
          "version", "database_dialect", "target_revision", "total", "ready", "imported",
          "duplicates", "invalid", "rows", "processing_status",
          "principal_type", "actor_id", "correlation_id", "permission", "permission_result"}


def safe_stack(exc):
    frames = []
    tb = exc.__traceback__
    while tb:
        frames.append({"file": Path(tb.tb_frame.f_code.co_filename).name,
                       "function": tb.tb_frame.f_code.co_name, "line": tb.tb_lineno})
        tb = tb.tb_next
    return frames[-20:]


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {"timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat().replace("+00:00", "Z"),
                "level": record.levelname, "logger": record.name, "event": getattr(record, "event", "runtime.log"),
                "message": getattr(record, "event", "Runtime diagnostic"),
                "environment": settings.ENVIRONMENT,
                "service": "leadforge-migration" if record.name.startswith("alembic") or getattr(record, "event", "").startswith("migration.") else "leadforge-backend"}
        correlation = getattr(record, "request_id", request_id_context.get())
        if correlation:
            data["request_id"] = correlation
        for key in FIELDS:
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exception_type"] = record.exc_info[0].__name__
            data["stack"] = safe_stack(record.exc_info[1])
        # No arbitrary third-party message/exception text, locals or source lines.
        def clean(value):
            if isinstance(value, str):
                return redact(value)
            if isinstance(value, dict):
                return {key: clean(item) for key, item in value.items()}
            if isinstance(value, list):
                return [clean(item) for item in value]
            return value
        return json.dumps(clean(data), ensure_ascii=True, separators=(",", ":"))


def configure_logging():
    root = logging.getLogger()
    root.handlers = [handler for handler in root.handlers if getattr(handler, "leadforge_owned", False) or type(handler).__name__ == "LogCaptureHandler"]
    owned = [handler for handler in root.handlers if getattr(handler, "leadforge_owned", False)]
    if not owned:
        handler = logging.StreamHandler(sys.stdout)
        handler.leadforge_owned = True
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    root.setLevel(getattr(logging, settings.LOG_LEVEL))
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "alembic", "sqlalchemy.engine"):
        component = logging.getLogger(name)
        component.handlers.clear()
        component.propagate = True
    for name, component in logging.Logger.manager.loggerDict.items():
        if (name == "leadforge" or name.startswith("leadforge.")) and isinstance(component, logging.Logger):
            component.disabled = False
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


configure_logging()
logger = logging.getLogger("leadforge")


def event(name, *, level=logging.INFO, exc=None, **fields):
    extra = {"event": name, "request_id": request_id_context.get(), **{key: value for key, value in fields.items() if key in FIELDS}}
    if exc is not None:
        extra.update(exception_type=type(exc).__name__, stack=safe_stack(exc))
    logger.log(level, name, extra=extra)


def operation(name, *, success=True):
    """Log lifecycle metadata only; arguments/results have no generic trust grant.

    Domain IDs and counters belong in explicitly validated application events.
    Request correlation comes from the existing framework-owned context, not
    command arguments. ``success=False`` retains failure-only instrumentation.
    """
    def decorate(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            started = perf_counter()
            if success:
                event(name + ".started")
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                event(name + ".failed", level=logging.WARNING, exception_type=type(exc).__name__,
                      duration_ms=round((perf_counter()-started)*1000, 2))
                raise
            if success:
                event(name + ".completed", duration_ms=round((perf_counter()-started)*1000, 2))
            return result
        return wrapper
    return decorate
