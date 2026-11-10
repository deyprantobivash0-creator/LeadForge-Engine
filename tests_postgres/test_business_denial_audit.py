"""Real PostgreSQL 16.15 command adoption, rollback ordering and lost ACKs."""

from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import threading
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from tests.test_business_denial_audit import (
    SURFACES, exercise_matrix, machine_denial_case,
    test_success_never_invokes_rejection_recorder as success_case,
    test_explicit_composition_records_only_first_denial_after_outer_rollback as composition_case,
    test_uncontextualized_nested_denial_defers_without_opening_audit_root as deferred_case,
)
from tests_postgres.test_rejection_recorder import _CommitProxy, _proxy_source


@pytest.fixture(scope="module")
def denial_database(pg_database):
    # Existing storage tests intentionally retain historical rows for synthetic
    # org IDs such as 101. New command tests must not advance the shared
    # business sequence into that unrelated fixture namespace.
    url = make_url(pg_database["url"])
    name = "leadforge_p1g_" + uuid4().hex[:12]
    connect = dict(host=url.host, port=url.port, user=url.username, password=url.password,
                   dbname="leadforge_dev", connect_timeout=3, autocommit=True)
    with psycopg.connect(**connect) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    private = url.set(database=name).render_as_string(hide_password=False)
    try:
        env = os.environ.copy()
        env.update(DATABASE_URL=private, AI_PROVIDER="mock", ENVIRONMENT="test", LEADFORGE_ENV_FILE="")
        migrated = subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, timeout=60)
        assert migrated.returncode == 0, "Owned P1-G database migration failed (private output withheld)"
        with psycopg.connect(**{**connect, "dbname": name}) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchall() == [("31e5e19bd71f",)]
        yield private
    finally:
        with psycopg.connect(**connect) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def denial_engine(denial_database):
    options = {"connect_timeout": 3, "options": "-c lock_timeout=5000 -c statement_timeout=8000"}
    engine = create_engine(denial_database, connect_args=options, pool_timeout=3)
    engine._test_rejection_connect_args = options
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("mode", ["RECORDED", "NOT_RECORDED", "RAISE"])
def test_postgres_command_denial_outcomes(denial_engine, monkeypatch, surface, mode):
    exercise_matrix(denial_engine, monkeypatch, surface, mode)


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("committed", [False, True])
def test_postgres_ambiguous_commit_keeps_original_denial_and_one_identity(denial_engine, monkeypatch, surface, committed):
    relay = _CommitProxy(denial_engine.url, "pass").start()
    source = _proxy_source(denial_engine, relay)
    @contextmanager
    def lost_ack(_writer):
        relay.mode = "committed" if committed else "absent"
        try:
            yield
        finally:
            relay.mode = "pass"
    try:
        exercise_matrix(source, monkeypatch, surface,
                        "UNKNOWN_COMMITTED" if committed else "UNKNOWN_ABSENT", fault_context=lost_ack)
    finally:
        source.dispose()
        relay.close()


@pytest.mark.parametrize("surface", ["create", "lifecycle", "import-first"])
def test_postgres_trusted_tenant_denial_is_in_principal_tenant_only(denial_engine, monkeypatch, surface):
    exercise_matrix(denial_engine, monkeypatch, surface, "RECORDED", tenant=True)


@pytest.mark.parametrize("surface", ["create", "lifecycle", "import-first"])
def test_postgres_real_audit_lock_never_delays_or_replaces_business_denial(denial_engine, monkeypatch, surface):
    @contextmanager
    def locked(_writer):
        stop, seen, errors = threading.Event(), threading.Event(), []
        with denial_engine.connect() as blocker:
            pid = blocker.exec_driver_sql("SELECT pg_backend_pid()").scalar()
            blocker.exec_driver_sql("LOCK TABLE audit_events IN ACCESS EXCLUSIVE MODE")
            def observe():
                try:
                    with denial_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                        while not stop.is_set():
                            found = observer.exec_driver_sql(
                                "SELECT pid FROM pg_stat_activity WHERE datname=current_database() "
                                "AND %s = ANY(pg_blocking_pids(pid))", (pid,)).scalars().all()
                            if found:
                                assert pid not in found
                                seen.set()
                                return
                            stop.wait(.01)
                except BaseException as exc:
                    errors.append(type(exc).__name__)
            worker = threading.Thread(target=observe)
            worker.start()
            try:
                yield
                assert seen.is_set() and not errors
            finally:
                stop.set()
                worker.join(2)
                assert not worker.is_alive()
                blocker.rollback()
    exercise_matrix(denial_engine, monkeypatch, surface, "NOT_RECORDED", fault_context=locked)


@pytest.mark.parametrize("surface", ["create", "lifecycle", "import-first"])
def test_postgres_success_keeps_atomic_success_audit(denial_engine, monkeypatch, surface):
    success_case(denial_engine, monkeypatch, surface)


@pytest.mark.parametrize("caught", [False, True])
def test_postgres_composition_has_one_post_rollback_recording_owner(denial_engine, monkeypatch, caught):
    composition_case(denial_engine, monkeypatch, caught)


@pytest.mark.parametrize("surface", SURFACES)
def test_postgres_missing_outer_context_never_records_inside_business_root(denial_engine, monkeypatch, surface):
    deferred_case(denial_engine, monkeypatch, surface)


@pytest.mark.parametrize("kind", ["SYSTEM", "AGENT", "WORKFLOW", "INTEGRATION"])
def test_postgres_machine_denials_do_not_snapshot_wrong_authority(denial_engine, monkeypatch, kind):
    machine_denial_case(denial_engine, monkeypatch, kind, "mismatched")


def test_default_request_recorder_uses_observed_hostname_endpoint_without_dns(denial_database, monkeypatch):
    import socket
    from sqlalchemy import event, select
    from sqlalchemy.orm import sessionmaker
    from backend.database import session as canonical, dependencies
    from backend.core.exceptions import LeadForgeException
    from backend.services.rejection_recorder import RejectionRecorder
    from tests.test_business_denial_audit import prepare, narrow_policy, invoke, rows
    from backend.models import Lead
    options = {"connect_timeout": 3, "options": "-c statement_timeout=8000"}
    source = create_engine(make_url(denial_database).set(host="localhost"), connect_args=options)
    checkouts = []
    event.listen(source, "checkout", lambda *_: checkouts.append(True))
    case = prepare(source)
    factory = sessionmaker(bind=source, autoflush=False)
    monkeypatch.setattr(canonical, "engine", source)
    monkeypatch.setattr(canonical, "SessionLocal", factory)
    monkeypatch.setattr(canonical, "connect_args", options)
    monkeypatch.setattr(dependencies, "SessionLocal", factory)
    narrow_policy(monkeypatch, "lifecycle")
    calls, original = [], RejectionRecorder.record_after_settlement
    def observed(writer, handle):
        result = original(writer, handle)
        calls.append(result)
        return result
    monkeypatch.setattr(RejectionRecorder, "record_after_settlement", observed)
    request_db = dependencies.get_db()
    db = next(request_db)
    try:
        assert dependencies.canonical_audit_connections(db) == ()
        db.scalar(select(Lead.id))  # Existing authenticated-request read, before denial.
        endpoints = dependencies.canonical_audit_connections(db)
        assert len(endpoints) == 1 and endpoints[0].engine is source
        established_checkouts = len(checkouts)
        monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: pytest.fail("Recorder introduced DNS"))
        with pytest.raises(LeadForgeException): invoke(db, case, "lifecycle")
        assert len(calls) == 1 and calls[0].status == "RECORDED"
        assert len(checkouts) == established_checkouts  # No endpoint-discovery checkout.
        assert len(rows(source, case)[0]) == 1
    finally:
        request_db.close()
        assert dependencies.canonical_audit_connections(db) == ()
        source.dispose()
