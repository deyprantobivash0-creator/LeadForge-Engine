"""Decision -> later observation contracts, on isolated migrated storage and HTTP."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from pydantic import ValidationError
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.models import DecisionLedger, DecisionOutcome, User
from backend.schemas.decision_outcome import OutcomeInput
from tests.test_decision_ledger import ledger_database, ledger_engine, prepare, record, transaction


def outcome_service(db):
    from backend.services.decision_outcome_service import DecisionOutcomeService
    return DecisionOutcomeService(db)


def setup(engine):
    case = prepare(engine)
    with Session(engine) as db:
        decision = record(db, case)
    return case, decision


def payload(kind="Meeting", **extra):
    return OutcomeInput(kind=kind, observed_at=datetime.now(timezone.utc), **extra)


def append(db, case, decision, value):
    return outcome_service(db).record(case["principal"], decision.lead_id, decision.id,
                                           decision.organization_id, value)


def test_roundtrip_order_pages_actor_and_immutable_decision(ledger_engine):
    case, decision = setup(ledger_engine)
    with Session(ledger_engine) as db:
        svc = outcome_service(db)
        assert svc.history(decision.lead_id, decision.id, decision.organization_id).effectiveness == "Outcome pending"
        first = append(db, case, decision, payload("Contacted"))
        second = append(db, case, decision, payload("Won", note="Manually confirmed result"))
        page = svc.history(decision.lead_id, decision.id, decision.organization_id, 1, 0)
        assert page.total == 2 and page.items == [second] and page.effectiveness == "Positive outcome"
        assert svc.history(decision.lead_id, decision.id, decision.organization_id, 1, 1).items == [first]
        assert first.note is None and first.recorded_by_user_id == case["principal"].actor_id
        assert first.source == "manual_user_report" and first.recorded_at >= first.observed_at >= decision.recorded_at
        from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
        assert DecisionLedgerRepository(db).get(decision.organization_id, decision.lead_id, decision.id) == decision


@pytest.mark.parametrize("kind,label", [("Contacted", "Inconclusive"), ("Qualified", "Positive outcome"),
    ("Meeting", "Positive outcome"), ("Won", "Positive outcome"), ("Lost", "Negative outcome")])
def test_effectiveness_is_observation_not_recommendation_accuracy(ledger_engine, kind, label):
    case, decision = setup(ledger_engine)
    with Session(ledger_engine) as db:
        append(db, case, decision, payload(kind))
        assert outcome_service(db).history(decision.lead_id, decision.id, decision.organization_id).effectiveness == label


@pytest.mark.parametrize("delta", [-1, 86400])
def test_observation_must_follow_decision_and_not_be_future(ledger_engine, delta):
    from backend.services.decision_outcome_service import OutcomeTimeError
    case, decision = setup(ledger_engine)
    with Session(ledger_engine) as db, pytest.raises(OutcomeTimeError):
        append(db, case, decision, OutcomeInput(kind="Won", observed_at=decision.recorded_at + timedelta(seconds=delta)))
    with Session(ledger_engine) as db:
        assert outcome_service(db).history(decision.lead_id, decision.id, decision.organization_id).total == 0


@pytest.mark.parametrize("target", ["missing_lead", "wrong_lead", "missing_decision", "foreign_org"])
def test_scoped_relationship_not_found(ledger_engine, target):
    case, decision = setup(ledger_engine)
    lead, org, ident = decision.lead_id, decision.organization_id, decision.id
    if target == "missing_lead": lead += 100000
    elif target == "wrong_lead": lead = case["ids"]["foreign_lead"]
    elif target == "missing_decision": ident = uuid4()
    else: org = case["ids"]["foreign_org"]
    with Session(ledger_engine) as db:
        assert outcome_service(db).history(lead, ident, org) is None
        if target != "foreign_org":
            assert outcome_service(db).record(case["principal"], lead, ident, org, payload()) is None


@pytest.mark.parametrize("state", ["machine", "inactive", "tenant_mismatch"])
def test_record_requires_fresh_user_membership(ledger_engine, state):
    from backend.schemas.execution_principal import ExecutionPrincipal
    from backend.core.exceptions import LeadForgeException
    case, decision = setup(ledger_engine)
    if state == "machine": case["principal"] = ExecutionPrincipal.for_system("fixture", decision.organization_id)
    elif state == "tenant_mismatch": case["principal"] = ExecutionPrincipal.for_user(case["ids"]["user"], case["ids"]["foreign_org"])
    else:
        with Session(ledger_engine) as db, transaction(db): db.get(User, case["ids"]["user"]).is_active = False
    with Session(ledger_engine) as db, pytest.raises(LeadForgeException): append(db, case, decision, payload())


@pytest.mark.parametrize("field,value", [("kind", "New"), ("kind", "SEND_EMAIL"), ("note", "x" * 1001),
    ("note", "a\x00b"), ("note", 1), ("observed_at", "2026-01-01T00:00:00"), ("extra", "ignored")])
def test_strict_input(field, value):
    data = dict(kind="Meeting", observed_at=datetime.now(timezone.utc))
    data[field] = value
    with pytest.raises(ValidationError): OutcomeInput.model_validate(data)


@pytest.mark.parametrize("mutation", ["update", "delete", "orm"])
def test_outcomes_cannot_be_overwritten(ledger_engine, mutation):
    case, decision = setup(ledger_engine)
    with Session(ledger_engine) as db: saved = append(db, case, decision, payload())
    with Session(ledger_engine) as db, pytest.raises((IntegrityError, ValueError)), transaction(db):
        if mutation == "update": db.execute(update(DecisionOutcome).where(DecisionOutcome.id == str(saved.id)).values(kind="Lost"))
        elif mutation == "delete": db.execute(delete(DecisionOutcome).where(DecisionOutcome.id == str(saved.id)))
        else:
            db.get(DecisionOutcome, str(saved.id)).kind = "Lost"
            db.flush()


def test_http_validation_tenant_csrf_and_read_only_history(tenant_workspace):
    from tests.api.test_tenant_leads import headers
    w = tenant_workspace
    a, b = w["clients"]["a"], w["clients"]["b"]
    lead = w["ids"]["leads"]["a"]
    base = f"/api/leads/{lead}/opportunity-decisions"
    decision = a.post(base, headers=headers(w, "a", csrf=True), json={})
    assert decision.status_code == 201
    url = base + "/" + decision.json()["id"] + "/outcomes"
    assert a.get(url, headers=headers(w, "a")).json()["total"] == 0
    data = dict(kind="Meeting", observed_at=datetime.now(timezone.utc).isoformat(), note="<script>synthetic</script>")
    assert a.post(url, headers=headers(w, "a"), json=data).status_code == 403
    assert b.get(url, headers=headers(w, "b")).status_code == 404
    assert b.post(url, headers=headers(w, "b", csrf=True), json=data).status_code == 404
    assert a.post(url, headers=headers(w, "a", csrf=True), json={**data, "organization_id": 2}).status_code == 422
    saved = a.post(url, headers=headers(w, "a", csrf=True), json=data)
    assert saved.status_code == 201
    page = a.get(url, headers=headers(w, "a"))
    assert page.status_code == 200 and page.json()["items"] == [saved.json()]
    assert a.get(base + "/" + decision.json()["id"], headers=headers(w, "a")).json() == decision.json()
    a.cookies.clear()
    assert a.get(url, headers=headers(w, "a")).status_code == 401


def test_additive_migration_preserves_populated_decisions_and_roundtrips(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from backend.core.config import settings
    from tests.test_decision_ledger import configured_engine
    from sqlalchemy import inspect
    url = "sqlite:///" + (tmp_path / "outcome-migration.db").as_posix()
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "31e5e19bd71f")
    engine = configured_engine(url)
    case, decision = setup(engine)
    engine.dispose()
    command.upgrade(config, "head")
    engine = configured_engine(url)
    with Session(engine) as db:
        assert outcome_service(db).history(decision.lead_id, decision.id, decision.organization_id).total == 0
        append(db, case, decision, payload(note="x" * 1000))
    engine.dispose()
    command.downgrade(config, "31e5e19bd71f")
    engine = configured_engine(url)
    assert "decision_outcomes" not in inspect(engine).get_table_names()
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    with Session(engine) as db:
        assert DecisionLedgerRepository(db).get(decision.organization_id, decision.lead_id, decision.id) == decision
    engine.dispose()
    command.upgrade(config, "head")
    engine = configured_engine(url)
    with Session(engine) as db:
        assert outcome_service(db).history(decision.lead_id, decision.id, decision.organization_id).total == 0
    engine.dispose()


def test_append_failure_rolls_back_without_decision_mutation(ledger_engine, monkeypatch):
    from backend.repositories.decision_outcome_repository import DecisionOutcomeRepository
    case, decision = setup(ledger_engine)
    original = DecisionOutcomeRepository.append
    def fail(self, values):
        original(self, values)
        raise RuntimeError("Synthetic outcome persistence failure")
    monkeypatch.setattr(DecisionOutcomeRepository, "append", fail)
    with Session(ledger_engine) as db, pytest.raises(RuntimeError): append(db, case, decision, payload())
    with Session(ledger_engine) as db:
        assert outcome_service(db).history(decision.lead_id, decision.id, decision.organization_id).total == 0


def test_database_scoped_foreign_key_rejects_cross_decision_link(ledger_engine):
    case, decision = setup(ledger_engine)
    with Session(ledger_engine) as db: row = append(db, case, decision, payload())
    with Session(ledger_engine) as db, pytest.raises(IntegrityError), transaction(db):
        values = dict(id=str(uuid4()), organization_id=case["ids"]["foreign_org"], lead_id=decision.lead_id,
            decision_id=str(decision.id), kind="Meeting", observed_at=row.observed_at, recorded_at=row.recorded_at,
            recorded_by_user_id=row.recorded_by_user_id)
        db.execute(DecisionOutcome.__table__.insert(), values)
