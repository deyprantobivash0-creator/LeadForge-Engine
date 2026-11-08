"""P2-A real PostgreSQL acquisition, parity, and no business/auth/audit writes."""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.test_opportunity_decision import decide, seed_decision, semantics, snapshot


@pytest.fixture(scope="module")
def decision_database(pg_database):
    # Keep new IDs out of pre-existing storage-test synthetic tenant namespaces.
    url = make_url(pg_database["url"])
    name = "leadforge_p2a_" + uuid4().hex[:12]
    connect = dict(host=url.host, port=url.port, user=url.username, password=url.password,
                   dbname="leadforge_dev", connect_timeout=3, autocommit=True)
    with psycopg.connect(**connect) as admin:
        assert admin.execute("SHOW server_version").fetchone()[0].split()[0] == "16.15"
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    private = url.set(database=name).render_as_string(hide_password=False)
    try:
        env = os.environ.copy()
        env.update(DATABASE_URL=private, AI_PROVIDER="mock", ENVIRONMENT="test", LEADFORGE_ENV_FILE="")
        result = subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, timeout=60)
        assert result.returncode == 0, "Owned P2-A disposable migration failed; private output withheld"
        with psycopg.connect(**{**connect, "dbname": name}) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchall() == [("5d59e6268f43",)]
        yield private
    finally:
        with psycopg.connect(**connect) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def decision_rows(decision_database):
    from backend.models import Lead, Organization
    from backend.database.transactions import service_transaction
    engine = create_engine(decision_database)
    with Session(engine) as db, service_transaction(db):
        suffix = uuid4().hex
        own, foreign = Organization(name="P2-A own", slug="p2a-own-" + suffix), Organization(name="P2-A other", slug="p2a-other-" + suffix)
        db.add_all([own, foreign])
        db.flush()
        lead = Lead(organization_id=own.id, company="Initial", email=suffix + "@example.invalid", source="fixture")
        db.add(lead)
        db.flush()
        seed_decision(db, lead)
        ids = lead.id, own.id, foreign.id
    try:
        yield engine, ids
    finally:
        engine.dispose()


def test_real_postgres_tenant_privacy_and_no_existence_disclosure(decision_rows):
    from backend.services.opportunity_decision_service import OpportunityDecisionService
    engine, (lead, own, foreign) = decision_rows
    with Session(engine) as db:
        service = OpportunityDecisionService(db)
        assert service.get_decision(lead, own).lead_id == lead
        assert service.get_decision(lead, foreign) is None
        assert service.get_decision(9223372036854775807, own) is None


def test_real_postgres_read_only_same_policy_and_no_settlement(decision_rows):
    from backend.services.opportunity_decision_service import OpportunityDecisionService
    engine, (lead, own, _) = decision_rows
    before, statements = snapshot(engine), []
    def collect(_c, _cursor, statement, *_args): statements.append(statement)
    def prohibited(*_args): raise AssertionError("Decisioning attempted transaction settlement")
    with Session(engine) as db:
        event.listen(engine, "before_cursor_execute", collect)
        for name in ("before_commit", "before_flush", "after_rollback"):
            event.listen(db, name, prohibited)
        try:
            service = OpportunityDecisionService(db)
            first, second = service.get_decision(lead, own), service.get_decision(lead, own)
            expected = decide(id=lead, organization_id=own)
            assert semantics(first) == semantics(second) == semantics(expected)
            assert len(statements) == 4 and all(s.lstrip().upper().startswith("SELECT") for s in statements)
            assert not db.new and not db.dirty and not db.deleted
        finally:
            event.remove(engine, "before_cursor_execute", collect)
            for name in ("before_commit", "before_flush", "after_rollback"):
                event.remove(db, name, prohibited)
    assert snapshot(engine) == before
