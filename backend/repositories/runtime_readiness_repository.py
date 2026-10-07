"""Database checks for runtime readiness; no customer data is accessed."""

from sqlalchemy import text

from backend.database.session import SessionLocal


class RuntimeReadinessRepository:
    def migration_heads(self) -> set[str]:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            return set(db.scalars(text("SELECT version_num FROM alembic_version")))
