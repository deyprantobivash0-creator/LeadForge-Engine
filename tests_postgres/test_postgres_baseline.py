"""Opt-in production-dialect checks against a freshly migrated disposable database."""

import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier, Lock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select


@pytest.fixture
def workspace(pg_database):
    from contextlib import ExitStack

    from backend.core.passwords import hash_password
    from backend.core.rate_limit import limiter
    from backend.database.session import SessionLocal
    from backend.main import app
    from backend.models import Lead, LeadAnalysis, Organization, OrganizationMembership, User

    limiter.reset()
    suffix = uuid4().hex[:12]
    password = "postgres fixture password"
    with SessionLocal() as db:
        org_a = Organization(name="Postgres Alpha", slug=f"pg-alpha-{suffix}")
        org_b = Organization(name="Postgres Beta", slug=f"pg-beta-{suffix}")
        user_a = User(email=f"pg-a-{suffix}@example.com", password_hash=hash_password(password))
        user_b = User(email=f"pg-b-{suffix}@example.com", password_hash=hash_password(password))
        db.add_all([org_a, org_b, user_a, user_b])
        db.flush()
        db.add_all([
            OrganizationMembership(organization_id=org_a.id, user_id=user_a.id, role="owner"),
            OrganizationMembership(organization_id=org_b.id, user_id=user_b.id, role="owner"),
        ])
        lead_a = Lead(organization_id=org_a.id, company="Alpha", email="shared@example.com", source="fixture")
        lead_b = Lead(organization_id=org_b.id, company="Beta", email="shared@example.com", source="fixture")
        db.add_all([lead_a, lead_b])
        db.flush()
        now = datetime.utcnow()
        db.add_all([
            LeadAnalysis(organization_id=org_a.id, lead_id=lead_a.id, company="Alpha", email=lead_a.email,
                         priority="Hot", lead_score=80, result={}, created_at=now - timedelta(minutes=2)),
            LeadAnalysis(organization_id=org_a.id, lead_id=lead_a.id, company="Alpha", email=lead_a.email,
                         priority="Warm", lead_score=60, result={}, created_at=now - timedelta(minutes=1)),
            LeadAnalysis(organization_id=org_a.id, company="=LEGACY()", email="legacy@example.com",
                         priority="Cold", lead_score=20, result={}, created_at=now),
            LeadAnalysis(organization_id=org_b.id, lead_id=lead_b.id, company="Beta", email=lead_b.email,
                         priority="Hot", lead_score=99, result={}, created_at=now),
        ])
        db.commit()
        ids = {"a": org_a.id, "b": org_b.id, "lead_a": lead_a.id, "lead_b": lead_b.id,
               "user_a": user_a.id}

    with ExitStack() as stack:
        clients = {key: stack.enter_context(TestClient(app, base_url="https://testserver")) for key in ("a", "b")}
        for key, client in clients.items():
            response = client.post("/api/auth/login", json={"email": f"pg-{key}-{suffix}@example.com", "password": password})
            assert response.status_code == 200, response.text
        yield {"clients": clients, "ids": ids, "email_a": f"pg-a-{suffix}@example.com"}
    limiter.reset()


def header(workspace, key):
    return {"X-Organization-ID": str(workspace["ids"][key])}


def test_direct_create_race_classifies_only_tenant_email_and_recovers_session(workspace, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from backend.database.session import SessionLocal
    from backend.models import Lead
    from backend.repositories.lead_repository import LeadRepository
    from backend.services.lead_service import LeadService

    original = LeadRepository.create_lead
    barrier = Barrier(2)
    violations = []
    lock = Lock()

    def concurrent_create(repository, lead):
        barrier.wait(timeout=15)
        try:
            return original(repository, lead)
        except IntegrityError as exc:
            with lock:
                violations.append((exc.orig.sqlstate, exc.orig.diag.constraint_name))
            raise

    monkeypatch.setattr(LeadRepository, 'create_lead', concurrent_create)
    org_id = workspace['ids']['a']

    def create(_):
        with SessionLocal() as db:
            try:
                LeadService(db).create_lead('Race Synthetic', 'direct-race@example.com', 'fixture', org_id)
                result = 'accepted'
            except ValueError as exc:
                assert str(exc) == 'A lead with this email already exists in this organization.'
                result = 'duplicate'
            assert db.scalar(select(Lead.id).where(Lead.organization_id == org_id, Lead.email == 'direct-race@example.com'))
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, range(2))) == ['accepted', 'duplicate']
    assert violations == [('23505', 'uq_leads_organization_email')]

    def invalid_create(repository, lead):
        lead.company = None
        return original(repository, lead)

    monkeypatch.setattr(LeadRepository, 'create_lead', invalid_create)
    with SessionLocal() as db:
        with pytest.raises(IntegrityError) as failure:
            LeadService(db).create_lead('Invalid Synthetic', 'not-null@example.com', 'fixture', org_id)
        assert failure.value.orig.sqlstate == '23502'
        assert db.scalar(select(Lead.id).where(Lead.organization_id == org_id, Lead.email == 'not-null@example.com')) is None


def test_fresh_migration_matches_mapped_tables(pg_database):
    from backend.database.base import Base
    from backend.database.session import engine
    import backend.models  # noqa: F401

    inspector = inspect(engine)
    assert set(Base.metadata.tables).issubset(set(inspector.get_table_names()))
    for table in Base.metadata.tables.values():
        actual = {column["name"] for column in inspector.get_columns(table.name)}
        assert set(table.columns.keys()) == actual, table.name
        actual_columns = {column["name"]: column for column in inspector.get_columns(table.name)}
        for column in table.columns:
            assert bool(actual_columns[column.name]["nullable"]) == bool(column.nullable), (table.name, column.name)
        actual_uniques = {constraint["name"] for constraint in inspector.get_unique_constraints(table.name)}
        expected_uniques = {constraint.name for constraint in table.constraints
                            if constraint.__class__.__name__ == "UniqueConstraint" and constraint.name}
        assert expected_uniques.issubset(actual_uniques), table.name
        actual_indexes = {index["name"] for index in inspector.get_indexes(table.name)}
        expected_indexes = {index.name for index in table.indexes}
        assert expected_indexes.issubset(actual_indexes), table.name
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "e5d4c3b2a1f0"
    analysis_links = inspector.get_foreign_keys("lead_analysis")
    assert any(link["referred_table"] == "leads"
               and link["constrained_columns"] == ["organization_id", "lead_id"]
               and link["referred_columns"] == ["organization_id", "id"]
               for link in analysis_links)


def test_auth_tenant_current_analytics_and_reports(workspace):
    from backend.main import app

    a = workspace["clients"]["a"]
    b = workspace["clients"]["b"]
    with TestClient(app, base_url="https://testserver") as anonymous:
        assert anonymous.get("/api/reports/v2/overview", headers=header(workspace, "a")).status_code == 401
    assert a.get("/api/reports/v2/overview", headers=header(workspace, "b")).status_code == 403
    assert a.get(f"/api/leads/{workspace['ids']['lead_b']}", headers=header(workspace, "a")).status_code == 404

    dashboard = a.get("/api/dashboard/v2/overview", headers=header(workspace, "a"))
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["pipeline"]["total_leads"] == 1
    assert dashboard.json()["pipeline"]["average_current_score"] == 60
    assert dashboard.json()["recent_analysis_activity"]

    report = a.get("/api/reports/v2/overview", headers=header(workspace, "a"))
    assert report.status_code == 200, report.text
    summary = report.json()["summary"]
    assert summary["analysis_events"] == 3
    assert summary["unique_analyzed_leads"] == 1
    assert summary["average_analysis_score"] == pytest.approx(53.33, abs=0.01)
    assert report.json()["top_opportunities"][0]["score"] == 80
    assert "Beta" not in report.text
    assert b.get("/api/reports/v2/overview", headers=header(workspace, "b")).json()["summary"]["analysis_events"] == 1

    for preset in ("today", "7d", "30d"):
        selected = a.get("/api/reports/v2/overview", params={"preset": preset}, headers=header(workspace, "a"))
        assert selected.status_code == 200, selected.text
        assert selected.json()["summary"]["analysis_events"] == 3
    today = datetime.utcnow().date().isoformat()
    custom = a.get("/api/reports/v2/overview", params={"preset": "custom", "start": today, "end": today},
                   headers=header(workspace, "a"))
    assert custom.status_code == 200, custom.text
    assert custom.json()["summary"]["analysis_events"] == 3
    empty = a.get("/api/reports/v2/overview", params={"preset": "custom", "start": "2020-01-01", "end": "2020-01-01"},
                  headers=header(workspace, "a"))
    assert empty.status_code == 200 and empty.json()["summary"]["analysis_events"] == 0

    export = a.get("/api/reports/v2/export.csv", headers=header(workspace, "a"))
    assert export.status_code == 200, export.text
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert len(rows) == 3
    assert any(row["company"] == "'=LEGACY()" for row in rows)
    assert all(row["company"] != "Beta" for row in rows)


def test_current_analysis_tie_and_cross_tenant_writes(workspace):
    from backend.core.config import settings
    from backend.database.session import SessionLocal
    from backend.models import LeadAnalysis
    from backend.repositories.lead_analysis_repository import LeadAnalysisRepository

    a = workspace["clients"]["a"]
    lead_a = workspace["ids"]["lead_a"]
    lead_b = workspace["ids"]["lead_b"]
    headers = header(workspace, "a")
    assert a.get(f"/api/leads/{lead_b}/intelligence", headers=headers).status_code == 404
    assert a.get(f"/api/leads/{lead_b}/analyses", headers=headers).status_code == 404
    csrf = a.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf
    denied = a.patch(f"/api/leads/{lead_b}/lifecycle", json={"status": "Contacted"},
                     headers={**headers, "X-CSRF-Token": csrf})
    assert denied.status_code == 404
    assert a.post(f"/api/leads/{lead_b}/process", headers={**headers, "X-CSRF-Token": csrf}).status_code == 404
    with SessionLocal() as db:
        repository = LeadAnalysisRepository()
        previous = repository.get_current_for_lead(db, lead_a, workspace["ids"]["a"])
        same_time = previous.created_at
        next_analysis = LeadAnalysis(organization_id=workspace["ids"]["a"], lead_id=lead_a,
                                     company="Alpha", email="shared@example.com", priority="Cold",
                                     lead_score=10, result={}, created_at=same_time)
        db.add(next_analysis)
        db.commit()
        assert repository.get_current_for_lead(db, lead_a, workspace["ids"]["a"]).id == next_analysis.id
        assert repository.get_current_for_lead(db, lead_b, workspace["ids"]["a"]) is None
    current = a.get(f"/api/leads/{lead_a}/intelligence", headers=headers)
    assert current.status_code == 200, current.text
    assert current.json()["analysis"]["lead_score"] == 10
    dashboard = a.get("/api/dashboard/v2/overview", headers=headers).json()
    assert dashboard["pipeline"]["total_leads"] == 1
    assert dashboard["pipeline"]["average_current_score"] == 10


def test_postgres_session_membership_and_csrf(workspace):
    from datetime import timedelta

    from backend.database.session import SessionLocal
    from backend.models import AuthSession, Organization, OrganizationMembership, User
    from backend.services.authentication_service import utc_now

    a = workspace["clients"]["a"]
    b = workspace["clients"]["b"]
    assert a.get("/api/auth/me").status_code == 200
    assert a.post("/api/auth/logout").status_code == 403
    assert a.get("/api/dashboard/v2/overview", headers=header(workspace, "b")).status_code == 403
    with SessionLocal() as db:
        membership = db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.user_id == workspace["ids"]["user_a"],
            OrganizationMembership.organization_id == workspace["ids"]["a"],
        ))
        membership_id = membership.id
        membership.is_active = False
        db.commit()
    assert a.get("/api/dashboard/v2/overview", headers=header(workspace, "a")).status_code == 403
    with SessionLocal() as db:
        db.get(OrganizationMembership, membership_id).is_active = True
        db.get(Organization, workspace["ids"]["a"]).is_active = False
        db.commit()
    assert a.get("/api/reports/v2/overview", headers=header(workspace, "a")).status_code == 403
    with SessionLocal() as db:
        db.get(Organization, workspace["ids"]["a"]).is_active = True
        db.get(User, workspace["ids"]["user_a"]).is_active = False
        db.commit()
    assert a.get("/api/auth/me").status_code == 401
    assert b.get("/api/auth/me").status_code == 200
    with SessionLocal() as db:
        db.get(User, workspace["ids"]["user_a"]).is_active = True
        sessions = list(db.scalars(select(AuthSession).where(AuthSession.user_id == workspace["ids"]["user_a"])))
        assert len(sessions) == 1
        sessions[0].expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert a.get("/api/auth/me").status_code == 401
    relogin = a.post("/api/auth/login", json={"email": workspace["email_a"],
                                                "password": "postgres fixture password"})
    assert relogin.status_code == 200
    from backend.core.config import settings
    csrf = a.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf
    assert a.post("/api/auth/logout", headers={settings.CSRF_HEADER_NAME: csrf}).status_code == 200
    assert a.get("/api/auth/me").status_code == 401


def test_postgres_import_uniqueness_and_tenant_boundary(workspace, monkeypatch):
    from backend.core.config import settings
    from backend.database.session import SessionLocal
    from backend.models import Lead
    from backend.services.lead_import_service import LeadImportService

    org_id = workspace["ids"]["a"]
    user_id = workspace["ids"]["user_a"]
    with SessionLocal() as db:
        db.add(Lead(organization_id=workspace["ids"]["b"], company="Beta Only",
                    email="beta-only@example.com", source="fixture"))
        db.commit()
    client = workspace["clients"]["a"]
    preview_csv = b"company,email,source\nOther Tenant,beta-only@example.com,csv\n"
    preview_headers = {**header(workspace, "a"), settings.CSRF_HEADER_NAME: client.cookies[settings.CSRF_COOKIE_NAME],
                       "Content-Type": "text/csv"}
    api_preview = client.post("/api/imports/leads/preview", content=preview_csv, headers=preview_headers)
    assert api_preview.status_code == 200, api_preview.text
    assert api_preview.json()["summary"]["ready"] == 1
    with SessionLocal() as db:
        assert db.scalar(select(Lead.id).where(Lead.organization_id == org_id,
                                               Lead.email == "beta-only@example.com")) is None
    session_key = "a" * 64
    contents = [
        b"company,email,source\nShared,concurrent@example.com,csv\nOne,one@example.com,csv\n",
        b"company,email,source\nShared,concurrent@example.com,csv\nTwo,two@example.com,csv\n",
    ]
    with SessionLocal() as db:
        previews = [LeadImportService(db).preview(content, org_id, user_id, session_key) for content in contents]
    barrier = Barrier(2)
    from backend.repositories.lead_import_repository import LeadImportRepository
    from sqlalchemy.exc import IntegrityError

    original = LeadImportRepository.add
    violations = []
    arrivals = []
    lock = Lock()

    def synchronized_add(repository, organization_id, company, email, source):
        if email == "concurrent@example.com":
            # Both advisory prechecks completed; race only the shared-email writes.
            with lock:
                arrivals.append(repository.db.connection().exec_driver_sql(
                    "SELECT pg_backend_pid()"
                ).scalar_one())
            barrier.wait(timeout=15)
        try:
            return original(repository, organization_id, company, email, source)
        except IntegrityError as exc:
            with lock:
                violations.append((exc.orig.sqlstate, exc.orig.diag.constraint_name))
            raise

    monkeypatch.setattr(LeadImportRepository, "add", synchronized_add)

    def confirm(index):
        with SessionLocal() as db:
            db.connection().exec_driver_sql("SET LOCAL lock_timeout = '10s'")
            db.connection().exec_driver_sql("SET LOCAL statement_timeout = '20s'")
            return LeadImportService(db).confirm(contents[index], previews[index].token,
                                                 org_id, user_id, session_key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm, index) for index in (0, 1)]
        results = []
        failures = []
        for future in futures:
            try:
                results.append(future.result(timeout=30))
            except Exception as exc:
                failures.append(exc)
        if failures:
            raise ExceptionGroup("Concurrent import worker failures", failures)
    assert len(arrivals) == 2 and len(set(arrivals)) == 2
    assert violations == [("23505", "uq_leads_organization_email")]
    assert sorted(result.imported for result in results) == [1, 2]
    assert sorted(result.duplicates for result in results) == [0, 1]
    with SessionLocal() as db:
        a_emails = list(db.scalars(select(Lead.email).where(Lead.organization_id == org_id)))
        b_emails = list(db.scalars(select(Lead.email).where(Lead.organization_id == workspace["ids"]["b"])))
    assert a_emails.count("concurrent@example.com") == 1
    assert {"one@example.com", "two@example.com"}.issubset(a_emails)
    assert set(b_emails) == {"shared@example.com", "beta-only@example.com"}

    # An unrelated NOT NULL violation must roll back the operation, not become
    # a duplicate merely because a different row already owns this email.
    def invalid_company(repository, organization_id, company, email, source):
        return original(repository, organization_id, None, "shared@example.com", source)

    monkeypatch.setattr(LeadImportRepository, "add", invalid_company)
    with SessionLocal() as db:
        service = LeadImportService(db)
        preview = service.preview(preview_csv, org_id, user_id, session_key)
        with pytest.raises(IntegrityError) as error:
            service.confirm(preview_csv, preview.token, org_id, user_id, session_key)
        assert error.value.orig.sqlstate == "23502"
        assert db.scalar(select(Lead.id).where(
            Lead.organization_id == org_id, Lead.email == "beta-only@example.com"
        )) is None
