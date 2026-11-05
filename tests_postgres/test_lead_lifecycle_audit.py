"""Real PostgreSQL lifecycle history, E02 atomicity and observed row-lock waits."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.models import AuditEvent, Lead
from backend.schemas.execution_principal import ExecutionPrincipal
from tests.test_lead_lifecycle_audit import (
    change, readback, seed_case, transaction,
    test_exact_content_and_same_authorization as success_case,
    test_audit_failure_rolls_back_already_flushed_lifecycle as audit_failure_case,
    test_outer_settlement_owns_both_writes as outer_failure_case,
    test_stale_caller_uses_committed_authoritative_before as stale_case,
    test_lifecycle_write_failure_has_no_success_audit as mutation_failure_case,
    test_changed_fields_and_existing_noop_semantics as noop_case,
    test_changed_fields_compare_database_normalized_dates as date_case,
)
from tests_postgres.test_lead_lifecycle_locking import wait_for_row_lock


@pytest.fixture
def audit_engine(pg_database):
    engine = create_engine(pg_database["url"], connect_args={
        "connect_timeout": 3, "options": "-c lock_timeout=5000 -c statement_timeout=8000",
    }, pool_timeout=3)
    try:
        yield engine
    finally:
        engine.dispose()


def test_postgres_exact_lifecycle_audit(audit_engine, monkeypatch):
    success_case(audit_engine, monkeypatch, "USER")


@pytest.mark.parametrize("failure", ["construction", "flush"])
def test_postgres_audit_failure_rolls_back_lifecycle(audit_engine, monkeypatch, failure):
    audit_failure_case(audit_engine, monkeypatch, failure)


@pytest.mark.parametrize("failure", ["outer_failure", "savepoint_release"])
def test_postgres_outer_rollback_removes_both(audit_engine, monkeypatch, failure):
    outer_failure_case(audit_engine, monkeypatch, failure)


def test_postgres_stale_cached_state_has_authoritative_audit(audit_engine):
    stale_case(audit_engine)


def test_postgres_lifecycle_constraint_failure_has_no_audit(audit_engine):
    mutation_failure_case(audit_engine, "constraint")


def test_postgres_noop_is_one_accepted_command_event(audit_engine):
    noop_case(audit_engine, {"status": "New"}, [])


def test_postgres_changed_fields_use_stored_date_representation(audit_engine):
    date_case(audit_engine)


@pytest.mark.parametrize("rollback", [False, True], ids=["owner_commit", "owner_rollback"])
def test_postgres_serialized_transitions_audit_actual_history(audit_engine, rollback):
    case = seed_case(audit_engine)
    contender_case = dict(case, principal=ExecutionPrincipal.for_user(
        case["ids"]["user"], case["ids"]["org"], correlation_id="postgres-contender"))
    ready, pids = Event(), []

    def contender():
        with Session(audit_engine, autoflush=False) as db, transaction(db):
            cached = db.get(Lead, case["ids"]["lead"])
            original = cached.status
            pid = db.scalar(select(func.pg_backend_pid()))
            pids.append(pid)
            ready.set()
            result = change(db, contender_case, status="Contacted")
            return original, result.status, result is cached, pid

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = None
        with Session(audit_engine, autoflush=False) as owner:
            def operation():
                nonlocal future
                with transaction(owner):
                    change(owner, case)
                    owner_pid = owner.scalar(select(func.pg_backend_pid()))
                    assert owner.scalar(select(AuditEvent.event_id).where(
                        AuditEvent.organization_id == case["ids"]["org"])) is not None
                    future = pool.submit(contender)
                    assert ready.wait(3), "Contender did not reach acquisition"
                    assert pids[0] != owner_pid
                    wait_for_row_lock(audit_engine, pids[0], owner_pid, future)
                    before, audits = readback(audit_engine, case)
                    assert before.status == "New" and audits == []
                    if rollback:
                        raise RuntimeError("Owner rollback")
            if rollback:
                with pytest.raises(RuntimeError, match="Owner rollback"):
                    operation()
            else:
                operation()
        original, final, same_object, _pid = future.result(timeout=10)
    assert (original, final, same_object) == ("New", "Contacted", True)
    lead, audits = readback(audit_engine, case)
    assert lead.status == "Contacted" and len(audits) == (1 if rollback else 2)
    assert all(a.action == "lead.lifecycle.change" and a.target_id == str(lead.id) for a in audits)
    b = next(a for a in audits if a.correlation_id == "postgres-contender")
    assert b.details == dict(status_before="New" if rollback else "Qualified",
                             status_after="Contacted", changed_fields=["status"])
    if not rollback:
        a = next(a for a in audits if a.correlation_id == "p1c-command")
        assert a.details == dict(status_before="New", status_after="Qualified", changed_fields=["status"])
