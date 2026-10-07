"""Isolate the supported pytest suite from local data and AI providers."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


# conftest loads before tests are imported, so application settings and its
# module-level engine see this disposable database even during collection.
_repo_root = Path(__file__).resolve().parents[1]
_test_directory = TemporaryDirectory(prefix=".leadforge-pytest-", dir=_repo_root)
_test_db = Path(_test_directory.name) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db.as_posix()}"
os.environ["AI_PROVIDER"] = "mock"
os.environ["ENVIRONMENT"] = "development"
os.environ.pop("LEADFORGE_ENV_FILE", None)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from backend.database.base import Base
    from backend.database.session import engine
    import backend.models  # Register all tables in Base.metadata.
    from backend.main import app

    assert Path(engine.url.database).resolve() == _test_db.resolve()
    Base.metadata.create_all(bind=engine)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def tenant_workspace(client):
    """Two isolated customers with real sessions and distinguishable lead data."""
    from contextlib import ExitStack
    from datetime import timedelta

    from fastapi.testclient import TestClient

    from backend.core.config import settings
    from backend.core.passwords import hash_password
    from backend.core.rate_limit import limiter
    from backend.database.session import SessionLocal
    from backend.main import app
    from backend.models import Lead, LeadAnalysis, Organization, OrganizationMembership, User
    from backend.services.authentication_service import utc_now

    limiter.reset()


    password = "tenant fixture password"
    password_hash = hash_password(password)
    with SessionLocal() as db:
        users = {
            "a": User(email="user-a@example.com", password_hash=password_hash),
            "b": User(email="user-b@example.com", password_hash=password_hash),
            "admin": User(email="admin@example.com", password_hash=password_hash),
        }
        organizations = {
            "a": Organization(name="Tenant A", slug="tenant-a"),
            "b": Organization(name="Tenant B", slug="tenant-b"),
        }
        db.add_all([*users.values(), *organizations.values()])
        db.flush()
        db.add_all([
            OrganizationMembership(user_id=users["a"].id, organization_id=organizations["a"].id, role="owner"),
            OrganizationMembership(user_id=users["b"].id, organization_id=organizations["b"].id, role="member"),
            OrganizationMembership(user_id=users["admin"].id, organization_id=organizations["a"].id, role="admin"),
        ])
        leads = {
            "a": Lead(organization_id=organizations["a"].id, company="Alpha Company", email="alpha-lead@example.com", source="fixture", next_follow_up=utc_now() + timedelta(days=2)),
            "b": Lead(organization_id=organizations["b"].id, company="Beta Company", email="beta-lead@example.com", source="fixture", next_follow_up=utc_now() + timedelta(days=2)),
        }
        db.add_all(leads.values())
        db.flush()
        db.add_all([
            LeadAnalysis(organization_id=organizations["a"].id, lead_id=leads["a"].id, company="Alpha Company", email="alpha-lead@example.com", priority="Hot", lead_score=80, result={"tenant": "a"}),
            LeadAnalysis(organization_id=organizations["b"].id, lead_id=leads["b"].id, company="Beta Company", email="beta-lead@example.com", priority="Cold", lead_score=20, result={"tenant": "b"}),
        ])
        db.commit()
        ids = {
            "users": {key: value.id for key, value in users.items()},
            "organizations": {key: value.id for key, value in organizations.items()},
            "leads": {key: value.id for key, value in leads.items()},
        }

    with ExitStack() as stack:
        clients = {
            key: stack.enter_context(TestClient(app, base_url="https://testserver"))
            for key in users
        }
        for key, test_client in clients.items():
            response = test_client.post(
                "/api/auth/login",
                json={"email": f"{('user-' + key) if key in {'a', 'b'} else key}@example.com", "password": password},
            )
            assert response.status_code == 200
        yield {"clients": clients, "ids": ids, "csrf_cookie": settings.CSRF_COOKIE_NAME}
    limiter.reset()


@pytest.fixture
def analytics_workspace(tenant_workspace, monkeypatch):
    """Mixed-tenant analyses with an overlapping email and an empty workspace."""
    from datetime import datetime, timedelta

    from sqlalchemy import select
    from backend.database.session import SessionLocal
    from backend.models import LeadAnalysis, Organization, OrganizationMembership
    from backend.reports.report_service import ReportService

    workspace = tenant_workspace
    org_a = workspace["ids"]["organizations"]["a"]
    org_b = workspace["ids"]["organizations"]["b"]
    now = datetime(2026, 10, 2, 13, 0)
    monkeypatch.setattr(ReportService, "_now", staticmethod(lambda: now))
    with SessionLocal() as db:
        for row in db.scalars(select(LeadAnalysis)):
            row.created_at = now - timedelta(minutes=30)
        empty_org = Organization(name="Empty Tenant", slug="tenant-empty")
        db.add(empty_org)
        db.flush()
        empty_id = empty_org.id
        db.add(OrganizationMembership(
            user_id=workspace["ids"]["users"]["a"],
            organization_id=empty_id,
            role="member",
        ))
        db.add_all([
            LeadAnalysis(organization_id=org_a, company="Alpha Second", email="alpha-second@example.com", priority="Hot", lead_score=60, result={}, created_at=now - timedelta(hours=1)),
            LeadAnalysis(organization_id=org_a, company="Shared Alpha", email="shared@example.com", priority="Warm", lead_score=40, result={}, created_at=now - timedelta(hours=2)),
            LeadAnalysis(organization_id=org_a, company="Alpha Cold", email="alpha-cold@example.com", priority="Cold", lead_score=10, result={}, created_at=now - timedelta(hours=3)),
            LeadAnalysis(organization_id=org_b, company="Beta Highest", email="beta-high@example.com", priority="Hot", lead_score=99, result={}, created_at=now - timedelta(hours=1)),
            LeadAnalysis(organization_id=org_b, company="Shared Beta", email="shared@example.com", priority="Warm", lead_score=95, result={}, created_at=now - timedelta(hours=2)),
        ])
        db.commit()
    workspace["ids"]["organizations"]["empty"] = empty_id
    workspace["analytics_now"] = now
    return workspace
