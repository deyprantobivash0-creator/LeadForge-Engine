"""Canonical lifecycle audit atomicity; every database and identity is disposable."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError, OperationalError
from sqlalchemy.orm import Session

from backend.database.base import Base
from backend.models import AuditEvent, Lead, Organization, OrganizationMembership, User
from backend.schemas.action_permission import (
    ActionPermission as P, MachineAuthorizationContext, PermissionReason,
)
from backend.schemas.execution_principal import ActorReference, ExecutionPrincipal, PrincipalType


def transaction(db):
    from backend.database.transactions import service_transaction
    return service_transaction(db)


def lifecycle_service(db):
    # PostgreSQL's guarded fixture configures settings before this import.
    from backend.services.lead_lifecycle_service import LeadLifecycleService
    return LeadLifecycleService(db)


@pytest.fixture
def audit_engine(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "lifecycle-audit.db").as_posix(),
                           connect_args={"timeout": 0})
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def seed_case(engine, kind="USER"):
    suffix = uuid4().hex
    with Session(engine, autoflush=False) as db, transaction(db):
        org = Organization(name="Lifecycle owner", slug="lifecycle-" + suffix)
        foreign = Organization(name="Lifecycle foreign", slug="foreign-" + suffix)
        account = User(email=suffix + "@example.invalid", password_hash="unused-synthetic-hash")
        db.add_all([org, foreign, account])
        db.flush()
        db.add(OrganizationMembership(organization_id=org.id, user_id=account.id, role="member"))
        lead = Lead(organization_id=org.id, company="Private synthetic company",
                    email=suffix + "@example.invalid", source="test", status="New",
                    notes="private original note")
        other = Lead(organization_id=foreign.id, company="Foreign synthetic company",
                     email=suffix + "@example.invalid", source="test", status="New")
        db.add_all([lead, other])
        db.flush()
        ids = dict(org=org.id, foreign_org=foreign.id, lead=lead.id, foreign_lead=other.id,
                   user=account.id)
    if kind == "USER":
        principal = ExecutionPrincipal.for_user(ids["user"], ids["org"], correlation_id="p1c-command")
        context = None
    else:
        extra = dict(workflow_run_id="parent-workflow", integration_id="parent-integration") if kind == "AGENT" else {}
        principal = getattr(ExecutionPrincipal, "for_" + kind.lower())(
            "p1c-" + kind.lower(), ids["org"], correlation_id="p1c-command",
            delegated_by=ActorReference(principal_type=PrincipalType.USER, actor_id=ids["user"]), **extra)
        context = MachineAuthorizationContext(principal, frozenset({P.LEAD_LIFECYCLE_CHANGE}))
    return dict(ids=ids, principal=principal, context=context)


def change(db, case, **overrides):
    kwargs = dict(lead_id=case["ids"]["lead"], organization_id=case["ids"]["org"],
                  status="Qualified", machine_context=case["context"])
    kwargs.update(overrides)
    return lifecycle_service(db).update_lifecycle(case["principal"], **kwargs)


def readback(engine, case):
    with Session(engine) as observer:
        lead = observer.scalar(select(Lead).where(Lead.organization_id == case["ids"]["org"],
                                                   Lead.id == case["ids"]["lead"]))
        audits = list(observer.scalars(select(AuditEvent).where(
            AuditEvent.organization_id == case["ids"]["org"])))
        return lead, audits


@pytest.mark.parametrize("kind", ["USER", "SYSTEM", "AGENT", "WORKFLOW", "INTEGRATION"])
def test_exact_content_and_same_authorization(audit_engine, monkeypatch, kind):
    import backend.services.action_permission_service as permission_module
    from backend.services import lead_lifecycle_service as module
    case = seed_case(audit_engine, kind)
    evaluations, captures = [], []
    evaluate, capture = permission_module.evaluate_permission, module.capture_authorization_receipt

    def evaluated(principal, authority, permission, org):
        result = evaluate(principal, authority, permission, org)
        evaluations.append((result, authority))
        return result

    def captured(principal, decision, authority):
        assert decision is evaluations[0][0] and authority is evaluations[0][1]
        captures.append(True)
        return capture(principal, decision, authority)

    monkeypatch.setattr(permission_module, "evaluate_permission", evaluated)
    monkeypatch.setattr(module, "capture_authorization_receipt", captured)
    when = datetime(2026, 11, 1, 12)
    with Session(audit_engine, autoflush=False) as db:
        result = change(db, case, notes="private changed note", last_contacted=when, next_follow_up=when)
        assert result.id == case["ids"]["lead"] and result.status == "Qualified"
    lead, audits = readback(audit_engine, case)
    assert lead.notes == "private changed note" and lead.last_contacted == lead.next_follow_up == when
    assert len(audits) == len(evaluations) == len(captures) == 1
    audit, principal = audits[0], case["principal"]
    assert audit.details == dict(status_before="New", status_after="Qualified",
        changed_fields=["status", "notes", "last_contacted", "next_follow_up"])
    assert audit.organization_id == case["ids"]["org"]
    assert audit.target_type == "lead" and audit.target_id == str(lead.id)
    assert audit.event_type == "business.command.completed" and audit.action == "lead.lifecycle.change"
    assert audit.outcome == "SUCCEEDED" and audit.reason_code == "COMMAND_COMPLETED"
    assert audit.principal_type == kind and audit.actor_id == str(principal.actor_id)
    assert audit.correlation_id == principal.correlation_id and audit.schema_version == 1
    assert audit.authority_role == ("member" if kind == "USER" else None)
    reason = PermissionReason.PERMITTED_BY_ROLE if kind == "USER" else PermissionReason.PERMITTED_BY_CAPABILITY
    assert audit.authorization_evidence == [dict(permission=P.LEAD_LIFECYCLE_CHANGE.value,
                                                decision="PERMIT", reason_code=reason.value)]
    assert audit.occurred_at.tzinfo is not None and audit.recorded_at >= audit.occurred_at
    parent = principal.delegated_by
    assert audit.delegated_by_type == (parent.principal_type.value if parent else None)
    assert audit.delegated_by_actor_id == (str(parent.actor_id) if parent else None)
    for field in ("agent_id", "workflow_run_id", "integration_id"):
        assert getattr(audit, field) == getattr(principal, field)
    serialized = str(audit.details) + str(audit.authorization_evidence)
    assert lead.company not in serialized and lead.email not in serialized and lead.notes not in serialized
    assert "private original note" not in serialized


@pytest.mark.parametrize("updates,fields", [
    ({"status": "New"}, []),
    ({"status": None, "notes": None, "last_contacted": None, "next_follow_up": None}, []),
    ({"status": None, "notes": "changed"}, ["notes"]),
    ({"status": None, "last_contacted": datetime(2026, 11, 1),
      "next_follow_up": datetime(2026, 11, 2)}, ["last_contacted", "next_follow_up"]),
    ({"status": "Qualified"}, ["status"]),
])
def test_changed_fields_and_existing_noop_semantics(audit_engine, updates, fields):
    case = seed_case(audit_engine)
    with Session(audit_engine, autoflush=False) as db:
        assert change(db, case, **updates) is not None
    lead, audits = readback(audit_engine, case)
    assert len(audits) == 1
    assert audits[0].details == dict(status_before="New", status_after=lead.status, changed_fields=fields)
    if updates.get("notes") is None:
        assert lead.notes == "private original note"  # None still means leave unchanged.


@pytest.mark.parametrize("missing", [False, True])
def test_invalid_status_precedence_and_no_success_audit(audit_engine, missing):
    case = seed_case(audit_engine)
    with Session(audit_engine, autoflush=False) as db:
        with pytest.raises(ValueError, match="Invalid status"):
            change(db, case, status="invalid", **({"lead_id": case["ids"]["lead"] + 100000} if missing else {}))
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and audits == []


@pytest.mark.parametrize("foreign", [False, True], ids=["missing", "foreign_tenant"])
def test_unowned_target_has_no_mutation_or_audit(audit_engine, foreign):
    case = seed_case(audit_engine)
    target = case["ids"]["foreign_lead"] if foreign else case["ids"]["lead"] + 100000
    with Session(audit_engine, autoflush=False) as db:
        assert change(db, case, lead_id=target) is None
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and audits == []
    with Session(audit_engine) as db:
        other = db.scalar(select(Lead).where(Lead.organization_id == case["ids"]["foreign_org"],
                                             Lead.id == case["ids"]["foreign_lead"]))
        assert other.status == "New"
        assert list(db.scalars(select(AuditEvent).where(
            AuditEvent.organization_id == case["ids"]["foreign_org"]))) == []


@pytest.mark.parametrize("denial", ["inactive_membership", "machine_capability", "tenant", "identity"])
def test_authorization_failures_have_no_success_or_denial_audit(audit_engine, denial):
    from backend.core.exceptions import LeadForgeException
    case = seed_case(audit_engine, "SYSTEM" if denial == "machine_capability" else "USER")
    overrides = {}
    if denial == "inactive_membership":
        with Session(audit_engine) as db, transaction(db):
            membership = db.scalar(select(OrganizationMembership).where(
                OrganizationMembership.user_id == case["ids"]["user"],
                OrganizationMembership.organization_id == case["ids"]["org"]))
            membership.is_active = False
    elif denial == "machine_capability":
        overrides["machine_context"] = MachineAuthorizationContext(case["principal"], frozenset())
    elif denial == "tenant":
        overrides["organization_id"] = case["ids"]["foreign_org"]
    else:
        case["principal"] = None
    with Session(audit_engine, autoflush=False) as db:
        with pytest.raises(LeadForgeException) as rejected:
            change(db, case, **overrides)
    assert rejected.value.error_code == {"tenant": "EXECUTION_TENANT_MISMATCH",
        "identity": "EXECUTION_IDENTITY_REQUIRED"}.get(denial, "ACTION_PERMISSION_DENIED")
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and audits == []


@pytest.mark.parametrize("autoflush", [False, True])
@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_permission_reads_cannot_autoflush_before_acquisition(audit_engine, autoflush, pending):
    case = seed_case(audit_engine)
    with Session(audit_engine, autoflush=autoflush) as db:
        with pytest.raises(RuntimeError, match="abort pending test"):
            with transaction(db):
                other = (Lead(organization_id=case["ids"]["org"], company=None,
                              email="invalid@example.invalid", source="test") if pending == "new"
                         else db.get(Lead, case["ids"]["foreign_lead"]))
                if pending == "new": db.add(other)
                elif pending == "dirty": other.notes = "retain pending value"
                else: db.delete(other)
                statements = []
                def observe(_conn, _cursor, sql, *_args): statements.append(sql)
                event.listen(audit_engine, "before_cursor_execute", observe)
                try:
                    with pytest.raises(InvalidRequestError, match="Flush pending"):
                        change(db, case)
                finally:
                    event.remove(audit_engine, "before_cursor_execute", observe)
                assert other in getattr(db, pending) and db.autoflush is autoflush
                if pending == "dirty": assert other.notes == "retain pending value"
                assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)
                raise RuntimeError("abort pending test")
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and audits == []


def test_stale_caller_uses_committed_authoritative_before(audit_engine):
    case = seed_case(audit_engine)
    with Session(audit_engine, autoflush=False) as reader, Session(audit_engine, autoflush=False) as writer:
        cached = reader.get(Lead, case["ids"]["lead"])
        change(writer, case)
        assert cached.status == "New"
        acquired = change(reader, case, status="Contacted")
        assert acquired is cached and acquired.status == "Contacted"
    lead, audits = readback(audit_engine, case)
    assert lead.status == "Contacted" and len(audits) == 2
    assert {(a.details["status_before"], a.details["status_after"]) for a in audits} == {
        ("New", "Qualified"), ("Qualified", "Contacted")}


def test_changed_fields_compare_database_normalized_dates(audit_engine):
    case = seed_case(audit_engine)
    when = datetime(2026, 11, 1, 12)
    with Session(audit_engine, autoflush=False) as db:
        change(db, case, status=None, last_contacted=when, next_follow_up=when)
    before, _audits = readback(audit_engine, case)
    with Session(audit_engine, autoflush=False) as db:
        change(db, case, status=None, last_contacted=when.replace(tzinfo=timezone.utc),
               next_follow_up=when.replace(tzinfo=timezone.utc))
    after, audits = readback(audit_engine, case)
    assert before.last_contacted == after.last_contacted == when
    assert before.next_follow_up == after.next_follow_up == when
    assert len(audits) == 2
    assert sorted((audit.details["changed_fields"] for audit in audits), key=len) == [
        [], ["last_contacted", "next_follow_up"]]
    assert all(a.details["status_before"] == a.details["status_after"] == "New" for a in audits)


@pytest.mark.parametrize("failure", ["construction", "append", "flush"])
def test_audit_failure_rolls_back_already_flushed_lifecycle(audit_engine, monkeypatch, failure):
    from backend.repositories.audit_repository import AuditRepository
    from backend.schemas.audit_event import AuditValidationError
    from backend.services.audit_event_builder import AuditEventBuilder
    case = seed_case(audit_engine)
    with Session(audit_engine, autoflush=False) as db:
        observed = []
        def see_mutation():
            assert db.scalar(select(Lead.status).where(Lead.organization_id == case["ids"]["org"],
                                                       Lead.id == case["ids"]["lead"])) == "Qualified"
            assert readback(audit_engine, case)[0].status == "New"
            observed.append(True)
        def fail_construction(*_args, **_kwargs):
            see_mutation()
            raise AuditValidationError("Synthetic audit construction failure.")
        def fail_append(repo, _draft):
            assert repo.db is db
            see_mutation()
            raise RuntimeError("Synthetic audit append failure")
        def fail_constraint(_mapper, _connection, audit):
            see_mutation()
            audit.schema_version = 0
        if failure == "construction": monkeypatch.setattr(AuditEventBuilder, "lifecycle_completed", fail_construction)
        elif failure == "append": monkeypatch.setattr(AuditRepository, "append", fail_append)
        else: event.listen(AuditEvent, "before_insert", fail_constraint)
        try:
            with pytest.raises({"construction": AuditValidationError, "append": RuntimeError,
                                "flush": IntegrityError}[failure]):
                change(db, case)
        finally:
            if failure == "flush": event.remove(AuditEvent, "before_insert", fail_constraint)
        assert observed == [True] and db.is_active
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and audits == []


@pytest.mark.parametrize("failure", ["constraint", "exception"])
def test_lifecycle_write_failure_has_no_success_audit(audit_engine, failure):
    case = seed_case(audit_engine)
    def reject(_mapper, _connection, lead):
        if failure == "constraint": lead.company = None
        else: raise RuntimeError("Synthetic lifecycle write failure")
    event.listen(Lead, "before_update", reject)
    try:
        with Session(audit_engine, autoflush=False) as db:
            with pytest.raises(IntegrityError if failure == "constraint" else RuntimeError):
                change(db, case)
    finally:
        event.remove(Lead, "before_update", reject)
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and lead.company == "Private synthetic company" and audits == []


@pytest.mark.parametrize("failure", ["outer_failure", "caught_nested_failure", "savepoint_release", "commit_failure"])
def test_outer_settlement_owns_both_writes(audit_engine, monkeypatch, failure):
    from backend.database.transactions import TransactionAborted
    from backend.database.transaction_policy import service_savepoint
    case = seed_case(audit_engine)
    with Session(audit_engine, autoflush=False) as db:
        if failure == "commit_failure":
            def fail_commit(): raise RuntimeError("Synthetic commit failure")
            monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(TransactionAborted if failure == "caught_nested_failure" else RuntimeError):
            with transaction(db):
                change(db, case)
                assert db.scalar(select(AuditEvent.event_id).where(
                    AuditEvent.organization_id == case["ids"]["org"])) is not None
                assert readback(audit_engine, case)[0].status == "New"
                assert readback(audit_engine, case)[1] == []
                if failure == "savepoint_release":
                    # P1-A acquisition stays root-only. Releasing later subordinate
                    # work must not publish the already-flushed business/audit pair.
                    with service_savepoint(db):
                        db.add(Lead(organization_id=case["ids"]["org"], company="Subordinate",
                                    email="subordinate@example.invalid", source="test"))
                        db.flush()
                    assert readback(audit_engine, case)[1] == []
                if failure == "caught_nested_failure":
                    try:
                        with transaction(db): raise ValueError("Nested failure")
                    except ValueError: pass
                elif failure != "commit_failure":
                    raise RuntimeError("Synthetic outer failure")
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and audits == []
    with Session(audit_engine) as db:
        assert db.scalar(select(Lead.id).where(Lead.organization_id == case["ids"]["org"],
                                              Lead.email == "subordinate@example.invalid")) is None


def test_acquisition_inside_savepoint_remains_rejected(audit_engine):
    from backend.database.transaction_policy import service_savepoint
    case = seed_case(audit_engine)
    with Session(audit_engine, autoflush=False) as db:
        with pytest.raises(InvalidRequestError, match="savepoint"):
            with transaction(db):
                with service_savepoint(db):
                    change(db, case)
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and audits == []


def test_before_details_are_immutable_and_independent_of_later_orm_mutation(audit_engine, monkeypatch):
    from backend.services.audit_event_builder import AuditEventBuilder
    case = seed_case(audit_engine)
    drafts = []
    build = AuditEventBuilder.lifecycle_completed
    def capture(*args, **kwargs):
        draft = build(*args, **kwargs)
        drafts.append(draft)
        return draft
    monkeypatch.setattr(AuditEventBuilder, "lifecycle_completed", capture)
    with Session(audit_engine, autoflush=False) as db:
        with pytest.raises(RuntimeError, match="discard test mutation"):
            with transaction(db):
                lead = change(db, case)
                snapshot = drafts[0].details
                with pytest.raises(FrozenInstanceError): snapshot.status_before = snapshot.status_after
                payload = db.scalar(select(AuditEvent.details).where(
                    AuditEvent.organization_id == case["ids"]["org"]))
                lead.status = "Lost"
                db.flush()
                copied = snapshot.as_json()
                copied["changed_fields"].clear()
                assert snapshot.as_json() == payload == dict(
                    status_before="New", status_after="Qualified", changed_fields=["status"])
                raise RuntimeError("discard test mutation")
    lead, audits = readback(audit_engine, case)
    assert lead.status == "New" and audits == []


@pytest.mark.parametrize("rollback", [False, True], ids=["owner_commit", "owner_rollback"])
def test_sqlite_contention_cannot_audit_stale_state(audit_engine, rollback):
    case = seed_case(audit_engine)
    contender_case = dict(case, principal=ExecutionPrincipal.for_user(
        case["ids"]["user"], case["ids"]["org"], correlation_id="sqlite-contender"))
    failed, settled = Event(), Event()
    def contender():
        with Session(audit_engine, autoflush=False) as db:
            cached = db.get(Lead, case["ids"]["lead"])
            original = cached.status
            with pytest.raises(OperationalError) as rejected:
                change(db, contender_case, status="Contacted")
            assert getattr(rejected.value.orig, "sqlite_errorname", None) == "SQLITE_BUSY"
            failed.set()
            assert settled.wait(5), "Owner did not settle"
            result = change(db, contender_case, status="Contacted")
            return original, result.status, result is cached
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = None
        try:
            with Session(audit_engine, autoflush=False) as db:
                def operation():
                    nonlocal future
                    with transaction(db):
                        change(db, case)
                        future = pool.submit(contender)
                        if not failed.wait(3):
                            future.result(timeout=1)
                            pytest.fail("Contender did not report writer contention")
                        assert readback(audit_engine, case)[1] == []
                        if rollback: raise RuntimeError("Owner rollback")
                if rollback:
                    with pytest.raises(RuntimeError, match="Owner rollback"): operation()
                else: operation()
        finally:
            settled.set()
        assert future.result(timeout=8) == ("New", "Contacted", True)
    lead, audits = readback(audit_engine, case)
    assert lead.status == "Contacted" and len(audits) == (1 if rollback else 2)
    contender_audit = next(a for a in audits if a.correlation_id == "sqlite-contender")
    assert contender_audit.details == dict(status_before="New" if rollback else "Qualified",
                                         status_after="Contacted", changed_fields=["status"])


@pytest.mark.parametrize("audit_failure", [False, True])
def test_http_lifecycle_uses_atomic_command(tenant_workspace, monkeypatch, audit_failure):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database.session import SessionLocal
    from backend.repositories.audit_repository import AuditRepository
    from tests.api.test_tenant_leads import headers
    workspace = tenant_workspace
    if audit_failure:
        def fail(*_args): raise RuntimeError("Synthetic route audit failure")
        monkeypatch.setattr(AuditRepository, "append", fail)
    client = workspace["clients"]["a"]
    h = {**headers(workspace, "a", csrf=True), "X-Request-ID": "p1c-http", "X-Role": "admin"}
    lead_id, org = workspace["ids"]["leads"]["a"], workspace["ids"]["organizations"]["a"]
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as request_client:
        request_client.cookies.update(client.cookies)
        result = request_client.patch(f"/api/leads/{lead_id}/lifecycle", headers=h,
                                      json={"status": "Qualified"})
    assert result.status_code == (500 if audit_failure else 200)
    with SessionLocal() as db:
        status = db.scalar(select(Lead.status).where(Lead.organization_id == org, Lead.id == lead_id))
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.organization_id == org,
                                                         AuditEvent.correlation_id == "p1c-http")))
        if audit_failure:
            assert status == "New" and audits == []
        else:
            assert status == result.json()["status"] == "Qualified" and len(audits) == 1
            assert audits[0].actor_id == str(workspace["ids"]["users"]["a"])
            assert audits[0].authority_role == "owner"
            assert audits[0].details == dict(status_before="New", status_after="Qualified", changed_fields=["status"])
