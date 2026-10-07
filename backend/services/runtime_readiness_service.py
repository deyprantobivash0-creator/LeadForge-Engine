"""Require the runtime database to match the shipped Alembic head."""

import logging
from backend.core.logger import event
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import SQLAlchemyError

from backend.repositories.runtime_readiness_repository import RuntimeReadinessRepository


@lru_cache(maxsize=1)
def expected_heads() -> frozenset[str]:
    root = Path(__file__).resolve().parents[2]
    return frozenset(ScriptDirectory.from_config(Config(str(root / "alembic.ini"))).get_heads())


class RuntimeReadinessService:
    def status(self) -> dict:
        try:
            actual = RuntimeReadinessRepository().migration_heads()
        except SQLAlchemyError as exc:
            original = getattr(exc, "orig", None)
            schema_missing = (getattr(original, "sqlstate", None) == "42P01"
                              or (getattr(original, "sqlite_errorcode", None) == 1
                                  and "alembic_version" in (getattr(exc, "statement", "") or "")))
            event("readiness.failed", level=logging.WARNING,
                  reason="schema_not_ready" if schema_missing else "database_unavailable",
                  exception_type=type(exc).__name__)
            return {"success": False, "status": "not_ready", "database": "unavailable"}
        if actual != expected_heads():
            event("readiness.failed", level=logging.WARNING, reason="schema_not_ready")
            return {"success": False, "status": "not_ready", "database": "schema_outdated"}
        return {"success": True, "status": "ready", "database": "ok"}
