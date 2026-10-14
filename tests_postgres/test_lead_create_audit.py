"""Real-dialect I3A atomicity using the existing guarded disposable migration fixture."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.test_lead_create_audit import (
    test_create_uses_actual_decision_and_same_context_once as success_case,
    test_required_audit_failure_after_lead_flush_rolls_back as failure_case,
    test_nested_create_shares_session_and_one_root_settlement as nested_case,
)


@pytest.fixture
def i3a_db(pg_database):
    engine = create_engine(pg_database["url"])
    try:
        with Session(engine, autoflush=False) as db:
            yield db
    finally:
        engine.dispose()


def test_postgres_create_and_actual_authority_json_commit(i3a_db, monkeypatch):
    success_case(i3a_db, monkeypatch, "USER")


def test_postgres_audit_constraint_failure_rolls_back_flushed_lead(i3a_db, monkeypatch):
    failure_case(i3a_db, monkeypatch, "flush")


def test_postgres_outer_rollback_removes_lead_and_audit(i3a_db, monkeypatch):
    nested_case(i3a_db, monkeypatch, "outer_failure")
