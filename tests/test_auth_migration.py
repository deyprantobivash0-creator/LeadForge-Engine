"""Exercise the new revision against disposable SQLite databases only."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.core.config import settings


PRE_AUTH = "24b5b28b09b7"
AUTH = "c3b2a1d0e9f8"
HEAD = "e5d4c3b2a1f0"
ROOT = Path(__file__).resolve().parents[1]


def _config(monkeypatch, db_path):
    assert db_path.parent.name.startswith("test_")
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    return Config(str(ROOT / "alembic.ini"))


def test_clean_upgrade_and_auth_downgrade(tmp_path, monkeypatch):
    db_path = tmp_path / "clean.db"
    config = _config(monkeypatch, db_path)
    command.upgrade(config, "head")
    engine = create_engine(settings.DATABASE_URL)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"organizations", "leads", "lead_analysis", "ingestion_jobs", "users", "organization_memberships", "auth_sessions"} <= tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    finally:
        engine.dispose()

    command.downgrade(config, PRE_AUTH)
    engine = create_engine(settings.DATABASE_URL)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"users", "organization_memberships", "auth_sessions"}.isdisjoint(tables)
        assert {"organizations", "leads", "lead_analysis", "ingestion_jobs"} <= tables
    finally:
        engine.dispose()


def test_populated_pre_auth_upgrade_preserves_existing_data(tmp_path, monkeypatch):
    db_path = tmp_path / "populated.db"
    config = _config(monkeypatch, db_path)
    command.upgrade(config, PRE_AUTH)
    engine = create_engine(settings.DATABASE_URL)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO organizations (id, name, slug, plan, monthly_lead_limit, is_active, created_at) VALUES (101, 'Fixture Org', 'fixture-org', 'standard', 500, 1, CURRENT_TIMESTAMP)"))
            connection.execute(text("INSERT INTO leads (id, organization_id, company, email, source, status, created_at) VALUES (201, 101, 'Fixture Co', 'lead@example.com', 'test', 'New', CURRENT_TIMESTAMP)"))
            connection.execute(text("INSERT INTO lead_analysis (id, organization_id, company, email, priority, lead_score, result, created_at) VALUES (301, 101, 'Fixture Co', 'lead@example.com', 'Warm', 50, '{}', CURRENT_TIMESTAMP)"))
            connection.execute(text("INSERT INTO ingestion_jobs (id, organization_id, filename, source_type, status, total_rows, processed_rows, successful_rows, failed_rows, created_at) VALUES (401, 101, 'sample.csv', 'csv', 'completed', 1, 1, 1, 0, CURRENT_TIMESTAMP)"))
    finally:
        engine.dispose()

    command.upgrade(config, AUTH)
    engine = create_engine(settings.DATABASE_URL)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT name FROM organizations WHERE id=101")) == "Fixture Org"
            assert connection.scalar(text("SELECT company FROM leads WHERE id=201")) == "Fixture Co"
            assert connection.scalar(text("SELECT lead_score FROM lead_analysis WHERE id=301")) == 50
            assert connection.scalar(text("SELECT successful_rows FROM ingestion_jobs WHERE id=401")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == AUTH
    finally:
        engine.dispose()
