"""P2-B snapshot history, explicit recording and immutable storage contracts."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, delete, event, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import DecisionLedger, Lead, LeadAnalysis, User
from backend.schemas.decision_ledger import DecisionLedgerRecord
from tests.test_lead_lifecycle_audit import seed_case, transaction
from tests.test_opportunity_decision import lead_case, seed_decision, snapshot


ROOT = Path(__file__).resolve().parents[1]
HEAD = "31e5e19bd71f"
PUBLISHED = "5d59e6268f43"


def configured_engine(url):
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def foreign_keys(dbapi, _record):
            dbapi.execute("PRAGMA foreign_keys=ON")
    return engine


@pytest.fixture(scope="module")
def ledger_database(tmp_path_factory):
    from backend.core.config import settings
    url = "sqlite:///" + (tmp_path_factory.mktemp("decision-ledger") / "history.db").as_posix()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "DATABASE_URL", url)
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    return url


@pytest.fixture
def ledger_engine(ledger_database):
    engine = configured_engine(ledger_database)
    try:
        yield engine
    finally:
        engine.dispose()


def prepare(engine, state="none"):
    case = seed_case(engine)
    with Session(engine) as db, transaction(db):
        lead = db.get(Lead, case["ids"]["lead"])
        lead.status = "Meeting"
        if state != "none":
            seed_decision(db, lead)
            analysis = db.scalar(select(LeadAnalysis).where(LeadAnalysis.lead_id == lead.id,
                LeadAnalysis.organization_id == lead.organization_id))
            result = deepcopy(analysis.result)
            if state == "partial":
                result["intent"]["evidence"] = []
            analysis.result = result
    return case


def service(db):
    from backend.services.decision_ledger_service import DecisionLedgerService
    return DecisionLedgerService(db)


def record(db, case):
    return service(db).record(case["principal"], case["ids"]["lead"], case["ids"]["org"])


def projection(decision):
    return dict(organization_id=decision.organization_id, lead_id=decision.lead_id,
        decision_version=decision.decision_version, opportunity_score=decision.opportunity_score,
        fit_score=decision.fit_score, readiness_score=decision.readiness_score,
        confidence=decision.confidence, recommended_action=decision.recommended_action,
        human_review_required=decision.human_review_required, reasons=decision.reasons,
        evidence=[e.model_dump() for e in decision.evidence], risk_flags=decision.risk_flags,
        missing_signals=decision.missing_signals)


def raw_values(dto):
    values = dto.model_dump(mode="json")
    values.update(decision_generated_at=dto.decision_generated_at, recorded_at=dto.recorded_at)
    return values


def migration_rows(engine):
    """Compare only tables that exist at this historical migration target."""
    from backend.database.base import Base
    names = set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        return {table.name: sorted(repr(tuple(r)) for r in connection.execute(select(table)))
                for table in Base.metadata.sorted_tables if table.name in names}


@pytest.mark.parametrize("state", ["none", "partial", "full"])
def test_exact_canonical_snapshot_one_compute_and_truthfulness(ledger_engine, monkeypatch, state):
    from backend.services.opportunity_decision_service import OpportunityDecisionService
    case = prepare(ledger_engine, state)
    calls = []
    original = OpportunityDecisionService.get_decision
    def observed(self, *args):
        decision = original(self, *args)
        calls.append(decision)
        return decision
    monkeypatch.setattr(OpportunityDecisionService, "get_decision", observed)
    with Session(ledger_engine) as db:
        commits = []
        event.listen(db, "before_commit", lambda *_: commits.append(True))
        result = record(db, case)
        assert commits == [True] and not db.in_transaction()
    assert len(calls) == 1
    assert projection(result) == projection(calls[0])
    assert result.decision_generated_at == calls[0].generated_at
    assert result.recorded_at >= result.decision_generated_at and result.id.version == 4
    with Session(ledger_engine) as db:
        loaded = service(db).get(case["ids"]["lead"], case["ids"]["org"], result.id)
        assert loaded == result
    entries = {e.signal: e for e in loaded.evidence}
    if state == "none":
        assert entries["intent_assessment"].source == entries["qualification"].source == "policy"
        assert "stored intent" not in " ".join(loaded.reasons).lower()
    elif state == "partial":
        assert entries["company_assessment"].source == "stored_assessment"
        assert entries["intent_assessment"].source == entries["qualification"].source == "policy"
    else:
        assert not loaded.missing_signals and entries["qualification"].source == "stored_assessment"


def test_history_is_stable_after_authorized_lifecycle_change(ledger_engine):
    from backend.services.lead_lifecycle_service import LeadLifecycleService
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db:
        first = record(db, case)
    frozen = first.model_dump(mode="json")
    with Session(ledger_engine) as db:
        LeadLifecycleService(db).update_lifecycle(case["principal"], lead_id=case["ids"]["lead"],
            organization_id=case["ids"]["org"], status="New")
        second = record(db, case)
    assert second.readiness_score != first.readiness_score and second.reasons != first.reasons
    with Session(ledger_engine) as db:
        assert service(db).get(first.lead_id, first.organization_id, first.id).model_dump(mode="json") == frozen


def test_identical_current_decisions_append_distinct_events_and_detached_lists(ledger_engine):
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db:
        first, second = record(db, case), record(db, case)
    assert first.id != second.id and projection(first) == projection(second)
    expected = list(first.reasons)
    first.reasons.append("Caller-local list edit")
    with Session(ledger_engine) as db:
        history = service(db).history(first.lead_id, first.organization_id)
        assert history.total == 2 and {r.id for r in history.items} == {first.id, second.id}
        assert service(db).get(first.lead_id, first.organization_id, first.id).reasons == expected


def test_policy_history_and_tied_timestamp_order_are_stored_not_live(ledger_engine):
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    from backend.services.opportunity_decision_service import OpportunityDecisionService
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db, transaction(db):
        decision = OpportunityDecisionService(db).get_decision(case["ids"]["lead"], case["ids"]["org"])
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = []
        for suffix in (1, 2, 3):
            dto = DecisionLedgerRecord.capture(decision, stamp).model_copy(update={
                "id": UUID(f"00000000-0000-4000-8000-{suffix:012d}"),
                "decision_version": "fixture_previous_policy" if suffix == 1 else "revenue_brain_v1"})
            rows.append(DecisionLedgerRepository(db).append(dto))
    with Session(ledger_engine) as db:
        page = service(db).history(decision.lead_id, decision.organization_id, 1, 1)
        assert page.total == 3 and page.items[0].id == rows[1].id
        assert service(db).get(decision.lead_id, decision.organization_id, rows[0].id).decision_version == "fixture_previous_policy"


@pytest.mark.parametrize("operation", ["orm_update", "orm_delete", "sql_update", "sql_delete"])
def test_immutable_orm_and_database_guards(ledger_engine, operation):
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db:
        dto = record(db, case)
    before = snapshot(ledger_engine)
    with pytest.raises((ValueError, IntegrityError)):
        with Session(ledger_engine) as db, transaction(db):
            if operation.startswith("orm"):
                row = db.get(DecisionLedger, str(dto.id))
                if operation == "orm_update": row.opportunity_score = 0
                else: db.delete(row)
                db.flush()
            elif operation == "sql_update":
                db.execute(update(DecisionLedger).where(DecisionLedger.id == str(dto.id)).values(decision_version="overwritten"))
            else:
                db.execute(delete(DecisionLedger).where(DecisionLedger.id == str(dto.id)))
    assert snapshot(ledger_engine) == before


def test_tenant_lead_fk_restrict_and_scoped_reads(ledger_engine):
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db:
        dto = record(db, case)
        assert service(db).history(case["ids"]["foreign_lead"], dto.organization_id) is None
        assert service(db).get(case["ids"]["foreign_lead"], dto.organization_id, dto.id) is None
        assert service(db).get(dto.lead_id, case["ids"]["foreign_org"], dto.id) is None
        assert service(db).get(dto.lead_id, dto.organization_id, uuid4()) is None
    bad = raw_values(dto)
    bad.update(id=str(uuid4()), lead_id=case["ids"]["foreign_lead"])
    with pytest.raises(IntegrityError):
        with Session(ledger_engine) as db, transaction(db): db.execute(DecisionLedger.__table__.insert(), bad)
    with pytest.raises(IntegrityError):
        with Session(ledger_engine) as db, transaction(db): db.execute(delete(Lead).where(Lead.id == dto.lead_id))


def test_failure_after_flush_rolls_back_without_lead_or_audit_mutation(ledger_engine, monkeypatch):
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    case = prepare(ledger_engine)
    before = snapshot(ledger_engine)
    original = DecisionLedgerRepository.append
    def failed(self, draft):
        original(self, draft)
        raise RuntimeError("Synthetic persistence failure after insert")
    monkeypatch.setattr(DecisionLedgerRepository, "append", failed)
    with Session(ledger_engine) as db:
        with pytest.raises(RuntimeError): record(db, case)
        assert not db.in_transaction()
    assert snapshot(ledger_engine) == before


def test_nested_failure_is_rollback_only_even_if_caught(ledger_engine, monkeypatch):
    from backend.database.transactions import TransactionAborted
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    case = prepare(ledger_engine)
    before = snapshot(ledger_engine)
    original = DecisionLedgerRepository.append
    def failed(self, draft):
        original(self, draft)
        raise RuntimeError("Synthetic ledger failure")
    monkeypatch.setattr(DecisionLedgerRepository, "append", failed)
    with Session(ledger_engine) as db, pytest.raises(TransactionAborted), transaction(db):
        try: record(db, case)
        except RuntimeError: pass
    assert snapshot(ledger_engine) == before


@pytest.mark.parametrize("state", ["missing_principal", "machine", "revoked_user", "tenant_mismatch"])
def test_record_service_requires_user_identity_and_fresh_membership(ledger_engine, state):
    from backend.core.exceptions import LeadForgeException
    from backend.schemas.execution_principal import ExecutionPrincipal
    case = prepare(ledger_engine)
    principal, org = case["principal"], case["ids"]["org"]
    if state == "missing_principal": principal = None
    elif state == "machine": principal = ExecutionPrincipal.for_system("fixture", org)
    elif state == "tenant_mismatch": org = case["ids"]["foreign_org"]
    else:
        with Session(ledger_engine) as db, transaction(db):
            db.get(User, case["ids"]["user"]).is_active = False
    before = snapshot(ledger_engine)
    with Session(ledger_engine) as db, pytest.raises(LeadForgeException):
        service(db).record(principal, case["ids"]["lead"], org)
    assert snapshot(ledger_engine) == before


@pytest.mark.parametrize("score", [0, 100])
def test_extreme_score_and_exact_json_timestamp_roundtrip(ledger_engine, score):
    from backend.decision.opportunity_policy import evaluate, extract_features
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    case = prepare(ledger_engine)
    lead, analysis = lead_case(score, score, score, id=case["ids"]["lead"], organization_id=case["ids"]["org"], status="New")
    dto = DecisionLedgerRecord.capture(evaluate(extract_features(lead, analysis)), datetime.now(timezone.utc))
    with Session(ledger_engine) as db, transaction(db):
        saved = DecisionLedgerRepository(db).append(dto)
    with Session(ledger_engine) as db:
        assert service(db).get(dto.lead_id, dto.organization_id, dto.id) == saved == dto


@pytest.mark.parametrize("invalid", ["raw_dict", "nan", "too_many_reasons", "unsafe_evidence"])
def test_repository_revalidates_typed_bounded_snapshot(ledger_engine, invalid):
    from pydantic import ValidationError
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    from backend.schemas.opportunity_decision import DecisionEvidence
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db:
        dto = record(db, case)
    if invalid == "raw_dict": candidate = raw_values(dto)
    elif invalid == "nan": candidate = dto.model_copy(update={"confidence": float("nan")})
    elif invalid == "too_many_reasons": candidate = dto.model_copy(update={"reasons": ["Reason"] * 13})
    else:
        evidence = DecisionEvidence.model_construct(signal="x" * 10000, observed_value="unsafe", effect="unsafe", source="policy")
        candidate = dto.model_copy(update={"evidence": [evidence]})
    before = snapshot(ledger_engine)
    with pytest.raises((ValueError, ValidationError)):
        with Session(ledger_engine) as db, transaction(db):
            DecisionLedgerRepository(db).append(candidate)
    assert snapshot(ledger_engine) == before


def test_repository_cannot_settle_an_ungoverned_insert(ledger_engine):
    from backend.repositories.decision_ledger_repository import DecisionLedgerRepository
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db: dto = record(db, case)
    before = snapshot(ledger_engine)
    with Session(ledger_engine) as db, pytest.raises(ValueError, match="caller-owned"):
        DecisionLedgerRepository(db).append(dto)
    assert snapshot(ledger_engine) == before


@pytest.mark.parametrize("field,value", [("opportunity_score", -1), ("fit_score", 101), ("confidence", float("nan")),
    ("confidence", float("inf")), ("confidence", -.1), ("confidence", 1.1), ("decision_version", ""),
    ("recommended_action", "SEND_EMAIL"), ("reasons", ["x"] * 40000)])
def test_storage_constraints_reject_invalid_raw_inserts(ledger_engine, field, value):
    case = prepare(ledger_engine)
    with Session(ledger_engine) as db: dto = record(db, case)
    values = raw_values(dto)
    values.update(id=str(uuid4()), **{field: value})
    with pytest.raises(IntegrityError):
        with Session(ledger_engine) as db, transaction(db): db.execute(DecisionLedger.__table__.insert(), values)


@pytest.mark.parametrize("state", ["none", "partial", "full"])
def test_authenticated_record_history_and_current_get_no_write(tenant_workspace, monkeypatch, state):
    from backend.ai.providers.router import AIRouter
    from backend.database.session import SessionLocal, engine
    from backend.schemas.decision_ledger import DecisionLedgerHistory
    from tests.api.test_tenant_leads import headers
    w = tenant_workspace
    lead_id, org = w["ids"]["leads"]["a"], w["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        db.execute(delete(LeadAnalysis).where(LeadAnalysis.organization_id == org, LeadAnalysis.lead_id == lead_id))
        if state != "none":
            seed_decision(db, db.get(Lead, lead_id))
            row = db.scalar(select(LeadAnalysis).where(LeadAnalysis.organization_id == org, LeadAnalysis.lead_id == lead_id))
            data = deepcopy(row.result)
            if state == "partial": data["intent"]["evidence"] = []
            row.result = data
        another = Lead(organization_id=org, company="Another owned lead", email="another-ledger@example.com", source="fixture")
        db.add(another)
        db.flush()
        other_id = another.id
        db.commit()
    def forbidden(*a, **k): raise AssertionError("Recording requested an external provider")
    monkeypatch.setattr(AIRouter, "get_provider", forbidden)
    client, url = w["clients"]["a"], f"/api/leads/{lead_id}/opportunity-decisions"
    foreign_url = f"/api/leads/{w['ids']['leads']['b']}/opportunity-decisions"
    foreign_record = w["clients"]["b"].post(foreign_url, headers=headers(w, "b", csrf=True))
    assert foreign_record.status_code == 201
    before = snapshot(engine)
    current = [client.get(f"/api/leads/{lead_id}/opportunity-decision", headers=headers(w, "a")) for _ in range(2)]
    assert all(r.status_code == 200 for r in current) and snapshot(engine) == before
    assert client.post(url, headers=headers(w, "a")).status_code == 403
    assert client.post(url, headers=headers(w, "a", csrf=True), json={"opportunity_score": 100}).status_code == 422
    first, second = [client.post(url, headers=headers(w, "a", csrf=True)) for _ in range(2)]
    assert first.status_code == second.status_code == 201
    a, b = DecisionLedgerRecord.model_validate(first.json()), DecisionLedgerRecord.model_validate(second.json())
    assert a.id != b.id
    actual = current[0].json()
    for key, value in projection(a).items():
        assert value == actual[key]
    page_response = client.get(url + "?limit=1&offset=0", headers=headers(w, "a"))
    page = DecisionLedgerHistory.model_validate(page_response.json())
    assert page.total == 2 and len(page.items) == 1
    single = client.get(url + "/" + str(a.id), headers=headers(w, "a"))
    assert single.status_code == 200 and single.json() == first.json()
    assert client.get(url + "/" + str(uuid4()), headers=headers(w, "a")).status_code == 404
    assert client.get(url + "/" + foreign_record.json()["id"], headers=headers(w, "a")).status_code == 404
    assert client.get(f"/api/leads/{w['ids']['leads']['b']}/opportunity-decisions/{a.id}", headers=headers(w, "a")).status_code == 404
    foreign = f"/api/leads/{w['ids']['leads']['b']}/opportunity-decisions"
    assert client.post(foreign, headers=headers(w, "a", csrf=True)).status_code == 404
    assert client.get(foreign, headers=headers(w, "a")).status_code == 404
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app, base_url="https://testserver") as anonymous:
        assert anonymous.get(url).status_code == 401
        assert anonymous.post(url).status_code == 401
    assert client.get(f"/api/leads/{other_id}/opportunity-decisions/{a.id}", headers=headers(w, "a")).status_code == 404
    for query in ("limit=0", "limit=101", "offset=-1", "offset=100000001"):
        assert client.get(url + "?" + query, headers=headers(w, "a")).status_code == 422
    assert client.patch(url + "/" + str(a.id), headers=headers(w, "a", csrf=True), json={}).status_code == 405
    assert client.delete(url + "/" + str(a.id), headers=headers(w, "a", csrf=True)).status_code == 405
    after = snapshot(engine)
    assert {k: v for k, v in after.items() if k != "decision_ledger"} == {k: v for k, v in before.items() if k != "decision_ledger"}


def test_migration_populated_upgrade_downgrade_and_no_backfill(tmp_path, monkeypatch):
    from backend.core.config import settings
    url = "sqlite:///" + (tmp_path / "upgrade.db").as_posix()
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, PUBLISHED)
    engine = configured_engine(url)
    case = seed_case(engine)
    before = migration_rows(engine)
    engine.dispose()
    command.upgrade(config, HEAD)
    engine = configured_engine(url)
    try:
        after = migration_rows(engine)
        assert after["decision_ledger"] == []
        assert {k: v for k, v in after.items() if k != "decision_ledger"} == before
        with Session(engine) as db: record(db, case)
    finally:
        engine.dispose()
    command.downgrade(config, PUBLISHED)
    engine = configured_engine(url)
    assert "decision_ledger" not in inspect(engine).get_table_names()
    assert migration_rows(engine) == before
    engine.dispose()
    command.upgrade(config, HEAD)
    engine = configured_engine(url)
    assert snapshot(engine)["decision_ledger"] == []
    engine.dispose()
