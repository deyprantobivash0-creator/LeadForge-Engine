"""Real PG row-savepoint recovery, command summaries and root-owned durability."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import AuditEvent, Lead
from backend.schemas.execution_principal import ExecutionPrincipal
from tests.test_lead_import_audit import (
    assert_summary, confirm, import_service, readback, seed_case, signed_token,
    test_exact_summary_uses_same_two_authorization_evaluations as exact_case,
    test_actual_batch_categories_and_noop_are_one_event as category_case,
    test_audit_failure_rolls_back_entire_flushed_batch as audit_failure_case,
    test_fatal_second_row_rolls_back_released_first_savepoint as business_failure_case,
    test_outer_root_owns_business_and_audit_durability as outer_failure_case,
    test_authorization_and_tenant_failures_have_no_audit as denial_case,
)


@pytest.fixture
def import_engine(pg_database):
    engine = create_engine(pg_database["url"], connect_args={
        "connect_timeout": 3, "options": "-c lock_timeout=5000 -c statement_timeout=8000",
    }, pool_timeout=3)
    try:
        yield engine
    finally:
        engine.dispose()


def test_postgres_exact_import_audit_and_tenant_boundary(import_engine, monkeypatch):
    exact_case(import_engine, monkeypatch)


@pytest.mark.parametrize("category", ["mixed", "all_duplicates", "all_invalid"])
def test_postgres_partial_and_noop_summary(import_engine, category):
    category_case(import_engine, category)


@pytest.mark.parametrize("failure", ["construction", "constraint"])
def test_postgres_audit_failure_removes_released_row_savepoints(import_engine, monkeypatch, failure):
    audit_failure_case(import_engine, monkeypatch, failure)


def test_postgres_not_null_failure_rolls_back_batch(import_engine, monkeypatch):
    business_failure_case(import_engine, monkeypatch, "constraint")


@pytest.mark.parametrize("failure", ["outer", "caught_nested", "savepoint_release"])
def test_postgres_outer_root_rollback_removes_import_and_audit(import_engine, monkeypatch, failure):
    outer_failure_case(import_engine, monkeypatch, failure)


def test_postgres_tenant_mismatch_has_no_success_audit(import_engine, monkeypatch):
    denial_case(import_engine, monkeypatch, "tenant")


def test_postgres_real_duplicate_race_recovers_and_audits_each_actual_result(import_engine, monkeypatch):
    from backend.repositories.lead_import_repository import LeadImportRepository
    case = seed_case(import_engine)
    cases = []
    for index in (0, 1):
        content = ("company,email,source\nShared,race@example.com,csv\n"
                   f"Unique {index},unique{index}@example.com,csv\n").encode()
        cases.append(dict(case, content=content, token=signed_token(case, content),
            principal=ExecutionPrincipal.for_user(case["ids"]["user"], case["ids"]["org"],
                                                   correlation_id=f"p1e-race-{index}")))
    barrier, mutex = Barrier(2), Lock()
    original, pids, violations = LeadImportRepository.add, [], []

    def synchronized_add(repo, org, company, email, source):
        if email == "race@example.com":
            # Both command prechecks have completed before either write wins.
            with mutex: pids.append(repo.db.scalar(select(func.pg_backend_pid())))
            barrier.wait(timeout=5)
        try:
            return original(repo, org, company, email, source)
        except IntegrityError as exc:
            with mutex: violations.append((exc.orig.sqlstate, exc.orig.diag.constraint_name))
            raise

    monkeypatch.setattr(LeadImportRepository, "add", synchronized_add)
    def worker(index):
        with Session(import_engine, autoflush=False) as db:
            return confirm(db, cases[index])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, index) for index in (0, 1)]
        results = [future.result(timeout=15) for future in futures]
    assert len(pids) == len(set(pids)) == 2
    assert violations == [("23505", "uq_leads_organization_email")]
    assert sorted((r.imported, r.duplicates) for r in results) == [(1, 1), (2, 0)]
    leads, audits = readback(import_engine, case)
    assert {lead.email for lead in leads} == {"race@example.com", "unique0@example.com", "unique1@example.com"}
    assert len(audits) == 2 and len({a.event_id for a in audits}) == 2
    for index, result in enumerate(results):
        audit = next(a for a in audits if a.correlation_id == cases[index]["principal"].correlation_id)
        assert_summary(audit, cases[index], result.model_dump())
    assert sum(a.details["imported"] for a in audits) == len(leads) == 3
