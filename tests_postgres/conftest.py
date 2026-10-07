"""Opt-in PostgreSQL tests; never imports or writes the SQLite test database."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
ADMIN_ENV = "LEADFORGE_POSTGRES_ADMIN_URL"


@pytest.fixture(scope="session")
def pg_database():
    raw = os.environ.get(ADMIN_ENV)
    if not raw:
        pytest.skip(f"Set {ADMIN_ENV} to the disposable local Docker database URL")
    url = make_url(raw)
    if (url.drivername != "postgresql+psycopg" or url.host not in {"localhost", "127.0.0.1"}
            or url.database != "leadforge_dev" or url.username != "leadforge_dev" or url.port != 55432):
        pytest.fail(f"{ADMIN_ENV} must identify the disposable local LeadForge PostgreSQL service")
    name = f"leadforge_test_{uuid4().hex[:12]}"
    connect = dict(host=url.host, port=url.port, dbname=url.database,
                   user=url.username, password=url.password, connect_timeout=5)
    with psycopg.connect(**connect, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    test_url = url.set(database=name).render_as_string(hide_password=False)
    previous = {key: os.environ.get(key) for key in ("DATABASE_URL", "AI_PROVIDER", "ENVIRONMENT")}
    os.environ["DATABASE_URL"] = test_url
    os.environ["AI_PROVIDER"] = "mock"
    os.environ["ENVIRONMENT"] = "test"
    try:
        from alembic import command
        from alembic.config import Config

        config = Config(str(ROOT / "alembic.ini"))
        command.upgrade(config, "head")
        yield {"url": test_url, "name": name}
    finally:
        try:
            from backend.database.session import engine
            engine.dispose()
        except ImportError:
            pass
        with psycopg.connect(**connect, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def pg_client(pg_database):
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app, base_url="https://testserver") as client:
        yield client
