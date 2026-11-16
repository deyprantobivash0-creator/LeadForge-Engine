from datetime import timedelta
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import event
from tests.test_decision_ledger import ledger_database, ledger_engine, prepare, record, snapshot
from tests.test_decision_outcome import payload, append


def evaluation(db):
    from backend.services.decision_evaluation_service import DecisionEvaluationService
    return DecisionEvaluationService(db)


def test_empty_and_pending(ledger_engine):
    case = prepare(ledger_engine)
    org = case["ids"]["org"]
    with Session(ledger_engine) as db:
        empty = evaluation(db).summary(org)
        assert empty.eligible == empty.evaluated == empty.pending == 0 and empty.coverage is None
        decision = record(db, case)
        result = evaluation(db).summary(org)
        assert result.eligible == result.pending == 1 and result.evaluated == 0 and result.coverage is None
        assert result.evidence_context == "No outcome evidence"
        assert evaluation(db).page(org).items[0].decision_id == decision.id


@pytest.mark.parametrize("kind,field", [("Meeting", "positive"), ("Qualified", "positive"), ("Won", "positive"), ("Lost", "negative"), ("Contacted", "inconclusive")])
def test_latest_evidence_and_denominators(ledger_engine, kind, field):
    case = prepare(ledger_engine)
    org = case["ids"]["org"]
    with Session(ledger_engine) as db:
        first = record(db, case)
        record(db, case)
        append(db, case, first, payload(kind))
        result = evaluation(db).summary(org)
        assert result.eligible == 2 and result.evaluated == result.pending == 1
        assert result.coverage == .5 and getattr(result, field) == 1
        assert result.positive + result.negative + result.inconclusive == result.evaluated
        assert sum(c.eligible for c in result.categories) == result.eligible
        assert sum(c.evaluated for c in result.categories) == result.evaluated
        assert result.evidence_context == "Limited evidence"
        assert evaluation(db).summary(org) == result


def test_multiple_outcomes_latest_observation_and_one_query(ledger_engine):
    case = prepare(ledger_engine)
    org = case["ids"]["org"]
    with Session(ledger_engine) as db:
        decision = record(db, case)
        append(db, case, decision, payload("Won"))
        older = payload("Lost").model_copy(update={"observed_at": decision.recorded_at})
        append(db, case, decision, older)
        queries = []
        def counted(_c, _cur, statement, *_args): queries.append(statement)
        event.listen(ledger_engine, "before_cursor_execute", counted)
        try: result = evaluation(db).summary(org)
        finally: event.remove(ledger_engine, "before_cursor_execute", counted)
        assert len(queries) == 1 and result.evaluated == result.positive == 1 and result.negative == 0
        assert evaluation(db).summary(case["ids"]["foreign_org"]).eligible == 0
        page = evaluation(db).page(org, 1)
        assert page.items[0].kind == "Won" and not page.has_more


def test_api_authorization_filters_and_foreign_evidence(tenant_workspace):
    from tests.api.test_tenant_leads import headers
    w = tenant_workspace
    a, b = w["clients"]["a"], w["clients"]["b"]
    lead = w["ids"]["leads"]["a"]
    decision = a.post(f"/api/leads/{lead}/opportunity-decisions", headers=headers(w, "a", csrf=True)).json()
    url = "/api/dashboard/decision-evaluation"
    assert a.get(url, headers=headers(w, "a")).json()["pending"] == 1
    assert b.get(url, headers=headers(w, "b")).json()["eligible"] == 0
    assert b.get(url + "/evidence", headers=headers(w, "b")).json()["items"] == []
    for query in ["?days=30", "?organization_id=2"]:
        assert a.get(url + query, headers=headers(w, "a")).status_code == 422
    for query in ["?limit=0", "?offset=-1", "?category=bad"]:
        assert a.get(url + "/evidence" + query, headers=headers(w, "a")).status_code == 422
    row = a.get(url + "/evidence", headers=headers(w, "a")).json()["items"][0]
    assert row["decision_id"] == decision["id"] and row["outcome_id"] is None
    a.cookies.clear()
    assert a.get(url, headers=headers(w, "a")).status_code == 401


def test_ties_use_recorded_time_then_uuid_without_double_count(ledger_engine):
    from backend.models import DecisionOutcome
    from tests.test_decision_ledger import transaction
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db:
        decision = record(db, case)
        saved = append(db, case, decision, payload("Won"))
    with Session(ledger_engine) as db, transaction(db):
        db.add(DecisionOutcome(id="ffffffff-ffff-4fff-bfff-ffffffffffff", organization_id=decision.organization_id,
            lead_id=decision.lead_id, decision_id=str(decision.id), kind="Lost", observed_at=saved.observed_at,
            recorded_at=saved.recorded_at, recorded_by_user_id=saved.recorded_by_user_id))
    with Session(ledger_engine) as db:
        result = evaluation(db).summary(decision.organization_id)
        assert result.evaluated == result.negative == 1 and result.positive == 0


def test_all_categories_reconcile_and_page_bounds(ledger_engine):
    from backend.schemas.opportunity_decision import RecommendedAction
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    from tests.test_decision_ledger import transaction
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db:
        template = record(db, case)
        from uuid import uuid4
        with transaction(db):
            for kind in RecommendedAction:
                row = template.model_copy(update={"id": uuid4(), "recommended_action": kind})
                DecisionLedgerRepository(db).append(row)
        result = evaluation(db).summary(template.organization_id)
        assert len(result.categories) == 6 and all(c.eligible >= 1 for c in result.categories)
        assert result.eligible == result.pending == 7
        page = evaluation(db).page(template.organization_id, 2, 0)
        assert len(page.items) == 2 and page.has_more
        assert evaluation(db).page(template.organization_id, 2, 100).items == []
        rows, _total = DecisionLedgerRepository(db).history(template.organization_id, template.lead_id, 20, 0)
        for row, kind in zip(rows[:6], ["Meeting", "Lost", "Contacted", "Qualified", "Won", "Lost"]):
            append(db, case, row, payload(kind))
        mixed = evaluation(db).summary(template.organization_id)
        assert (mixed.eligible, mixed.evaluated, mixed.pending) == (7, 6, 1)
        assert (mixed.positive, mixed.negative, mixed.inconclusive) == (3, 2, 1)
        assert mixed.coverage == 6 / 7
        assert sum(c.positive for c in mixed.categories) == mixed.positive
        before = snapshot(ledger_engine)
        assert evaluation(db).summary(template.organization_id) == mixed
        assert snapshot(ledger_engine) == before
        for limit, offset in [(0, 0), (101, 0), (1, -1)]:
            with pytest.raises(ValueError): evaluation(db).page(template.organization_id, limit, offset)
