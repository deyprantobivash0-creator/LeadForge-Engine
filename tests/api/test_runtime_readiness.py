"""Readiness must fail closed without hiding independent process liveness."""

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.database.session import SessionLocal
from backend.repositories.runtime_readiness_repository import RuntimeReadinessRepository
from backend.services.runtime_readiness_service import expected_heads


def test_ready_requires_current_migration_and_releases_session(client, caplog):
    assert client.get("/ready").status_code == 503
    assert any(getattr(record, "reason", None) == "schema_not_ready" for record in caplog.records)
    with SessionLocal() as db:
        db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("INSERT INTO alembic_version VALUES ('outdated')"))
        db.commit()
    try:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["database"] == "schema_outdated"
        with SessionLocal() as db:
            db.execute(text("DELETE FROM alembic_version"))
            for head in expected_heads():
                db.execute(text("INSERT INTO alembic_version VALUES (:head)"), {"head": head})
            db.commit()
        assert client.get("/ready").json() == {
            "success": True, "status": "ready", "database": "ok",
        }
        assert client.get("/ready").status_code == 200
    finally:
        with SessionLocal() as db:
            db.execute(text("DROP TABLE alembic_version"))
            db.commit()


def test_database_failure_returns_503_but_health_remains_live(client, monkeypatch):
    def unavailable(_repository):
        raise OperationalError("SELECT 1", {}, RuntimeError("unavailable"))

    monkeypatch.setattr(RuntimeReadinessRepository, "migration_heads", unavailable)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "success": False, "status": "not_ready", "database": "unavailable",
    }
    assert client.get("/health").status_code == 200
