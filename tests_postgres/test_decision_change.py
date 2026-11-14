"""P2-C read composition on guarded, migrated PostgreSQL 16.15."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from tests import test_decision_ledger as support
from tests_postgres.test_decision_ledger import ledger_database, ledger_engine


def test_real_postgres_comparison_without_history(ledger_engine):
    from backend.services.decision_comparison_service import DecisionComparisonService
    case = support.prepare(ledger_engine)
    before = support.snapshot(ledger_engine)
    with Session(ledger_engine) as db:
        result = DecisionComparisonService(db).get_change(case["ids"]["lead"], case["ids"]["org"])
        assert result.current_decision.lead_id == case["ids"]["lead"]
        assert result.latest_recorded_decision is None and result.change is None and result.history.total == 0
    assert support.snapshot(ledger_engine) == before


@pytest.mark.parametrize("state", ["none", "partial", "full"])
def test_real_postgres_current_latest_roundtrip_is_read_only(ledger_engine, state):
    from backend.decision.decision_change import compare_decisions
    from backend.services.decision_comparison_service import DecisionComparisonService
    from backend.services.lead_lifecycle_service import LeadLifecycleService
    case = support.prepare(ledger_engine, state)
    with Session(ledger_engine) as db:
        previous = support.record(db, case)
        LeadLifecycleService(db).update_lifecycle(case["principal"], lead_id=previous.lead_id,
            organization_id=previous.organization_id, status="New")
    before = support.snapshot(ledger_engine)
    with Session(ledger_engine) as db:
        result = DecisionComparisonService(db).get_change(previous.lead_id, previous.organization_id)
        assert result.latest_recorded_decision == previous and result.history.items == [previous]
        assert result.change == compare_decisions(previous, result.current_decision)
        assert result.change.readiness_score_delta < 0
    assert support.snapshot(ledger_engine) == before


def test_real_postgres_foreign_and_large_ids_do_not_disclose_history(ledger_engine):
    from backend.services.decision_comparison_service import DecisionComparisonService
    case = support.prepare(ledger_engine)
    with Session(ledger_engine) as db: previous = support.record(db, case)
    before = support.snapshot(ledger_engine)
    with Session(ledger_engine) as db:
        service = DecisionComparisonService(db)
        assert service.get_change(previous.lead_id, case["ids"]["foreign_org"]) is None
        assert service.get_change(case["ids"]["foreign_lead"], previous.organization_id) is None
        assert service.get_change(2**63 - 1, previous.organization_id) is None
    assert support.snapshot(ledger_engine) == before


def test_real_postgres_preview_is_bounded_latest_and_four_selects(ledger_engine):
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    from backend.schemas.decision_ledger import DecisionLedgerRecord
    from backend.services.decision_comparison_service import DecisionComparisonService
    from backend.services.opportunity_decision_service import OpportunityDecisionService
    case = support.prepare(ledger_engine)
    rows = []
    with Session(ledger_engine) as db, support.transaction(db):
        current = OpportunityDecisionService(db).get_decision(case["ids"]["lead"], case["ids"]["org"])
        for index in range(7):
            stamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index // 2)
            rows.append(DecisionLedgerRepository(db).append(DecisionLedgerRecord.capture(current, stamp)))
    expected = sorted(rows, key=lambda r: (r.recorded_at, str(r.id)), reverse=True)
    before, statements = support.snapshot(ledger_engine), []
    def collect(_c, _cursor, statement, *_args): statements.append(statement)
    def forbidden(*_args): raise AssertionError("Comparison attempted settlement or flush")
    with Session(ledger_engine) as db:
        event.listen(ledger_engine, "before_cursor_execute", collect)
        for name in ["before_commit", "before_flush", "after_rollback"]: event.listen(db, name, forbidden)
        try:
            result = DecisionComparisonService(db).get_change(current.lead_id, current.organization_id)
            assert len(statements) == 4 and all(s.lstrip().upper().startswith("SELECT") for s in statements)
            assert result.latest_recorded_decision == expected[0]
            assert result.history.items == expected[:5] and result.history.total == 7 and result.history.limit == 5
        finally:
            event.remove(ledger_engine, "before_cursor_execute", collect)
            for name in ["before_commit", "before_flush", "after_rollback"]: event.remove(db, name, forbidden)
    assert support.snapshot(ledger_engine) == before
