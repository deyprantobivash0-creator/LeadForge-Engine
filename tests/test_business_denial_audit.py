"""P1-G: real commands, authoritative denial, explicit settlement and ownership."""

from contextlib import contextmanager
import json
import sqlite3
import time
from uuid import UUID

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from backend.core.exceptions import LeadForgeException
from backend.database.base import Base
from backend.models import AuditEvent, Lead
from backend.schemas.action_permission import ActionPermission as P, HumanAuthorizationContext
from tests.test_lead_lifecycle_audit import seed_case, transaction
from tests.test_lead_import_audit import CONTENT, SESSION_KEY, signed_token
from tests.test_rejection_recorder import recorder


SURFACES = ("create", "lifecycle", "import-first", "import-second")
ACTIONS = {"create": P.LEAD_CREATE, "lifecycle": P.LEAD_LIFECYCLE_CHANGE,
           "import-first": P.LEAD_IMPORT, "import-second": P.LEAD_IMPORT}


@pytest.fixture
def denial_engine(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "business-denials.db").as_posix())
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def prepare(engine):
    case = seed_case(engine)
    case.update(content=CONTENT)
    case["token"] = signed_token(case, CONTENT)
    return case


def narrow_policy(monkeypatch, surface):
    from backend.services.action_permission_service import ActionPermissionService
    original = ActionPermissionService.human_context
    grants = (frozenset({P.LEAD_IMPORT}) if surface == "import-second" else
              frozenset({P.LEAD_CREATE}) if surface == "import-first" else frozenset())
    def narrowed(service, principal):
        context = original(service, principal)
        return (HumanAuthorizationContext(principal, context.role, grants)
                if context is not None else None)
    monkeypatch.setattr(ActionPermissionService, "human_context", narrowed)


def invoke(db, case, surface, writer=None, *, audit_operation=None, **overrides):
    # Delayed application imports preserve the PostgreSQL fixture's settings.
    if surface == "create":
        from backend.services.lead_service import LeadService
        args = dict(principal=case["principal"], organization_id=case["ids"]["org"],
                    company="Private submitted company", email="submitted@example.com", source="private source")
        service = LeadService(db, rejection_recorder=writer)
        command = service.create_lead
    elif surface == "lifecycle":
        from backend.services.lead_lifecycle_service import LeadLifecycleService
        args = dict(principal=case["principal"], organization_id=case["ids"]["org"],
                    lead_id=case["ids"]["lead"], status="Qualified", notes="private submitted notes")
        service = LeadLifecycleService(db, rejection_recorder=writer)
        command = service.update_lifecycle
    else:
        from backend.services.lead_import_service import LeadImportService
        args = dict(principal=case["principal"], organization_id=case["ids"]["org"],
                    user_id=case["ids"]["user"], content=case["content"], token=case["token"],
                    session_key=SESSION_KEY)
        service = LeadImportService(db, rejection_recorder=writer)
        command = service.confirm
    args.update(overrides)
    return command(**args, audit_operation=audit_operation)


def rows(engine, case):
    with Session(engine) as db:
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.organization_id == case["ids"]["org"])))
        leads = [(x.id, x.status, x.notes) for x in db.scalars(select(Lead).where(
            Lead.organization_id == case["ids"]["org"]))]
        foreign = list(db.scalars(select(AuditEvent).where(AuditEvent.organization_id == case["ids"]["foreign_org"])))
        return audits, leads, foreign


def assert_denial_row(audit, case, surface, tenant=False):
    assert UUID(audit.event_id).version == 4
    assert audit.organization_id == case["ids"]["org"] and audit.actor_id == str(case["ids"]["user"])
    assert audit.action == ACTIONS[surface] and audit.outcome == "DENIED"
    assert audit.target_id is None and audit.details == {}
    assert audit.correlation_id == case["principal"].correlation_id
    assert audit.event_type == ("security.command.rejected" if tenant else "permission.denied")
    assert audit.reason_code == ("EXECUTION_TENANT_MISMATCH" if tenant else "ACTION_PERMISSION_DENIED")
    expected = ([] if tenant else
                [dict(permission=P.LEAD_IMPORT, decision="PERMIT", reason_code="PERMITTED_BY_ROLE")]
                if surface == "import-second" else [])
    if not tenant:
        expected += [dict(permission=P.LEAD_CREATE if surface == "import-second" else ACTIONS[surface],
                          decision="DENY", reason_code="DENIED_PERMISSION_NOT_GRANTED")]
    assert audit.authorization_evidence == expected
    assert audit.authority_role == (None if tenant else "member")
    payload = json.dumps({c.name: str(getattr(audit, c.name)) for c in AuditEvent.__table__.columns})
    for secret in ("private submitted", "submitted@example.com", case["token"], SESSION_KEY,
                   "company,email,source", "Foreign synthetic", "private original note"):
        assert secret.lower() not in payload.lower()


@contextmanager
def sqlite_outcome(writer, mode, monkeypatch):
    from backend.database.rejection_storage import Attempt, DeadlineSQLite, active_attempt, attempt_scope
    if mode == "NOT_RECORDED":
        with attempt_scope(Attempt()), writer._storage.audit_bind.connect():
            yield
    elif mode.startswith("UNKNOWN"):
        commit = DeadlineSQLite.commit
        def lost_ack(connection):
            state = active_attempt()
            if mode == "UNKNOWN_COMMITTED":
                commit(connection)
            state.commit_started, state.acknowledged = True, False
            raise sqlite3.OperationalError("Synthetic lost COMMIT acknowledgement")
        with monkeypatch.context() as patch:
            patch.setattr(DeadlineSQLite, "commit", lost_ack)
            yield
    else:
        yield


def exercise_matrix(engine, monkeypatch, surface, mode, *, fault_context=None, tenant=False):
    from backend.database.transactions import in_service_transaction
    from backend.database.transaction_policy import current_root
    from backend.repositories.audit_repository import AuditRepository
    from backend.services import action_permission_service, execution_identity
    case = prepare(engine)
    if not tenant:
        narrow_policy(monkeypatch, surface)
    expected = LeadForgeException("Execution organization mismatch." if tenant else "Action not permitted.",
        status_code=403, error_code="EXECUTION_TENANT_MISMATCH" if tenant else "ACTION_PERMISSION_DENIED")
    monkeypatch.setattr(execution_identity if tenant else action_permission_service,
                        "LeadForgeException", lambda *_a, **_k: expected)
    before = rows(engine, case)[1]
    writer, chronology, calls, results, audit_sessions, audit_connections = recorder(engine), [], [], [], [], []
    try:
        with Session(engine, autoflush=False) as business:
            roots, connections = [], []
            def begun(_db, tx, connection):
                if tx.parent is None:
                    roots.append(tx)
                    connections.append(connection)
            def settled(_db, tx):
                if tx.parent is None:
                    chronology.append("business.rollback")
            event.listen(business, "after_begin", begun)
            event.listen(business, "after_soft_rollback", settled)
            # A real existing read root, like HTTP authentication, must be adopted.
            business.scalar(select(Lead.id))
            original_append = AuditRepository.append
            def appended(repo, draft):
                assert chronology[-1] == "recorder.call"
                assert repo.db is not business and not business.in_transaction()
                assert not in_service_transaction(business)
                root = current_root(repo.db)
                assert root is not None and root.authority.connection not in connections
                assert repo.db.get_transaction() not in roots
                def independent(_db, tx, connection):
                    assert tx not in roots and connection not in connections
                    assert chronology == ["business.rollback", "recorder.call"]
                    audit_connections.append(connection)
                if root.authority.connection is not None:
                    independent(repo.db, repo.db.get_transaction(), root.authority.connection)
                else:
                    event.listen(repo.db, "after_begin", independent, once=True)
                audit_sessions.append(repo.db)
                return original_append(repo, draft)
            monkeypatch.setattr(AuditRepository, "append", appended)
            original_record = writer.record_after_settlement
            def recorded(handle):
                assert chronology == ["business.rollback"]
                assert not business.in_transaction() and not in_service_transaction(business)
                assert roots and all(not tx.is_active for tx in roots)
                chronology.append("recorder.call")
                calls.append(handle)
                # Prove audit does not execute on the old business Session.
                for method in ("execute", "scalar", "flush"):
                    monkeypatch.setattr(business, method, lambda *_a, **_k: pytest.fail("Business Session reused"))
                if mode == "RAISE":
                    raise RuntimeError("private fault must not replace denial")
                started = time.monotonic()
                result = original_record(handle)
                assert time.monotonic() - started <= 5.0
                results.append(result)
                return result
            monkeypatch.setattr(writer, "record_after_settlement", recorded)
            context = fault_context(writer) if fault_context else sqlite_outcome(writer, mode, monkeypatch)
            started = time.monotonic()
            with context, pytest.raises(LeadForgeException) as raised:
                invoke(business, case, surface, writer, **(
                    {"organization_id": case["ids"]["foreign_org"]} if tenant else {}))
            assert raised.value is expected
            assert time.monotonic() - started <= 5.0
        audits, leads, foreign = rows(engine, case)
        assert leads == before and not foreign and len(calls) == 1
        assert all(not db.in_transaction() for db in audit_sessions)
        persisted = mode in {"RECORDED", "UNKNOWN_COMMITTED"}
        if mode in {"RECORDED", "UNKNOWN_ABSENT", "UNKNOWN_COMMITTED"}:
            assert audit_connections
        assert len(audits) == int(persisted)
        if persisted:
            assert audits[0].event_id == calls[0].draft.event_id
            assert_denial_row(audits[0], case, surface, tenant)
        if mode != "RAISE":
            assert results[0].status == ("OUTCOME_UNKNOWN" if mode.startswith("UNKNOWN") else mode)
            assert results[0].settlement is calls[0]
        if mode.startswith("UNKNOWN"):
            # No regenerated UUID or automatic retry. Reconcile only explicitly.
            confirmed = writer.reconcile_rejection(calls[0], case["principal"])
            assert confirmed.status == ("RECORDED" if persisted else "OUTCOME_UNKNOWN")
            assert confirmed.settlement.draft.event_id == calls[0].draft.event_id
            assert len(rows(engine, case)[0]) == int(persisted) and len(calls) == 1
    finally:
        writer.close()


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("mode", ["RECORDED", "NOT_RECORDED", "UNKNOWN_ABSENT", "UNKNOWN_COMMITTED", "RAISE"])
def test_business_denial_outcome_matrix(denial_engine, monkeypatch, surface, mode):
    exercise_matrix(denial_engine, monkeypatch, surface, mode)


@pytest.mark.parametrize("surface", ["create", "lifecycle", "import-first"])
@pytest.mark.parametrize("mode", ["RECORDED", "NOT_RECORDED", "UNKNOWN_COMMITTED"])
def test_trusted_tenant_mismatch_matrix(denial_engine, monkeypatch, surface, mode):
    exercise_matrix(denial_engine, monkeypatch, surface, mode, tenant=True)


@pytest.mark.parametrize("surface", ["create", "lifecycle", "import-first"])
def test_success_never_invokes_rejection_recorder(denial_engine, monkeypatch, surface):
    case, writer = prepare(denial_engine), recorder(denial_engine)
    monkeypatch.setattr(writer, "record_after_settlement", lambda *_: pytest.fail("Success recorded as rejection"))
    try:
        with Session(denial_engine, autoflush=False) as db:
            invoke(db, case, surface, writer)
        audits = rows(denial_engine, case)[0]
        assert len(audits) == 1 and audits[0].outcome == "SUCCEEDED"
    finally:
        writer.close()


@pytest.mark.parametrize("caught", [False, True])
def test_explicit_composition_records_only_first_denial_after_outer_rollback(denial_engine, monkeypatch, caught):
    from backend.database.transactions import TransactionAborted
    from backend.services.application_audit import application_audit_boundary
    case, writer = prepare(denial_engine), recorder(denial_engine)
    before, calls = rows(denial_engine, case)[1], []
    original = writer.record_after_settlement
    def recorded(handle):
        assert rows(denial_engine, case)[1] == before
        calls.append(handle)
        return original(handle)
    monkeypatch.setattr(writer, "record_after_settlement", recorded)
    try:
        with Session(denial_engine, autoflush=False) as db:
            with pytest.raises(TransactionAborted if caught else LeadForgeException):
                with application_audit_boundary(db, writer) as operation:
                    with transaction(db):
                        invoke(db, case, "create", writer, audit_operation=operation)
                        narrow_policy(monkeypatch, "lifecycle")
                        if caught:
                            with pytest.raises(LeadForgeException):
                                invoke(db, case, "lifecycle", writer, audit_operation=operation)
                            # A later nested call cannot replace the first decisive draft.
                            with pytest.raises(Exception):
                                invoke(db, case, "import-first", writer, audit_operation=operation)
                        else:
                            invoke(db, case, "lifecycle", writer, audit_operation=operation)
            assert operation.result.status == "RECORDED"
        audits, leads, _ = rows(denial_engine, case)
        assert leads == before and len(audits) == len(calls) == 1
        assert audits[0].event_id == operation.result.settlement.draft.event_id
        assert_denial_row(audits[0], case, "lifecycle")
    finally:
        writer.close()


@pytest.mark.parametrize("surface", SURFACES)
def test_uncontextualized_nested_denial_defers_without_opening_audit_root(denial_engine, monkeypatch, surface):
    from backend.services import application_audit
    case, writer, logs = prepare(denial_engine), recorder(denial_engine), []
    narrow_policy(monkeypatch, surface)
    monkeypatch.setattr(application_audit, "event", lambda name, **_kw: logs.append(name))
    monkeypatch.setattr(writer, "record_after_settlement", lambda *_: pytest.fail("Unsettled outer root recorded"))
    before = rows(denial_engine, case)[1]
    try:
        with Session(denial_engine, autoflush=False) as db, pytest.raises(LeadForgeException):
            with transaction(db):
                db.add(Lead(organization_id=case["ids"]["org"], company="Provisional",
                            email="provisional@example.com", source="test"))
                db.flush()
                invoke(db, case, surface, writer)
        audits, leads, _ = rows(denial_engine, case)
        assert leads == before and not audits
        assert "audit.rejection.recording_deferred_unavailable" in logs
    finally:
        writer.close()


@pytest.mark.parametrize("failure", ["configuration", "draft", "capture", "diagnostic", "owned-close"])
def test_evidence_failure_cannot_override_original_denial(denial_engine, monkeypatch, failure):
    from backend.services import command_audit, application_audit
    from backend.services.application_audit import AuditOperation
    case, writer = prepare(denial_engine), recorder(denial_engine)
    narrow_policy(monkeypatch, "lifecycle")
    def broken(*_a, **_kw):
        raise RuntimeError("Private configuration or database detail")
    monkeypatch.setattr(command_audit, "_application_recorder", broken if failure == "configuration" else lambda _: writer)
    if failure == "draft": monkeypatch.setattr(command_audit.AuditEventBuilder, "permission_denied", broken)
    if failure == "capture": monkeypatch.setattr(AuditOperation, "capture_rejection", broken)
    if failure == "diagnostic":
        monkeypatch.setattr(application_audit, "event", broken)
        monkeypatch.setattr(writer, "record_after_settlement", broken)
    close = writer.close
    if failure == "owned-close": monkeypatch.setattr(writer, "close", broken)
    try:
        with Session(denial_engine, autoflush=False) as db, pytest.raises(LeadForgeException) as raised:
            invoke(db, case, "lifecycle")
        assert raised.value.error_code == "ACTION_PERMISSION_DENIED" and raised.value.status_code == 403
        assert str(raised.value) == "Action not permitted."
        assert len(rows(denial_engine, case)[0]) == int(failure == "owned-close")
    finally:
        close()


@pytest.mark.parametrize("scenario", ["missing", "foreign", "invalid-status", "bad-token", "bad-csv", "wrong-import-user"])
def test_non_structural_rejections_do_not_invent_a_denial_event(denial_engine, monkeypatch, scenario):
    from backend.services.lead_import_service import ImportValidationError
    case, writer = prepare(denial_engine), recorder(denial_engine)
    monkeypatch.setattr(writer, "record_after_settlement", lambda *_: pytest.fail("Excluded taxonomy recorded"))
    try:
        with Session(denial_engine, autoflush=False) as db:
            if scenario in {"missing", "foreign"}:
                assert invoke(db, case, "lifecycle", writer, lead_id=(
                    case["ids"]["foreign_lead"] if scenario == "foreign" else 9223372036854775807)) is None
            elif scenario == "invalid-status":
                with pytest.raises(ValueError, match="Invalid status"):
                    invoke(db, case, "lifecycle", writer, status="made-up")
            else:
                kwargs = {"token": "invalid"} if scenario == "bad-token" else (
                    {"content": b"invalid CSV", "token": signed_token(case, b"invalid CSV")} if scenario == "bad-csv"
                    else {"user_id": case["ids"]["user"] + 1})
                with pytest.raises(ImportValidationError): invoke(db, case, "import-first", writer, **kwargs)
        assert not rows(denial_engine, case)[0]
    finally:
        writer.close()


@pytest.mark.parametrize("surface", ["create", "lifecycle", "import-first"])
@pytest.mark.parametrize("outcome", ["RECORDED", "NOT_RECORDED", "OUTCOME_UNKNOWN"])
def test_http_denial_is_identical_for_every_recorder_result(tenant_workspace, monkeypatch, surface, outcome):
    from backend.services import command_audit
    from backend.services.rejection_recorder import RejectionRecorder, RejectionRecordingResult
    from backend.schemas.action_permission import PermissionResult
    from backend.database.session import SessionLocal
    workspace = tenant_workspace
    client, ids = workspace["clients"]["a"], workspace["ids"]
    headers = {"X-Organization-ID": str(ids["organizations"]["a"]),
               "X-CSRF-Token": client.cookies.get(workspace["csrf_cookie"]), "X-Request-ID": "p1g-http-denial"}
    narrow_policy(monkeypatch, surface)
    def send():
        if surface == "create":
            return client.post("/api/leads/", headers=headers,
                               json=dict(company="Private", email="denied@example.com", source="test"))
        if surface == "lifecycle":
            return client.patch(f"/api/leads/{ids['leads']['a']}/lifecycle", headers=headers, json=dict(status="Qualified"))
        return client.post("/api/imports/leads/confirm", headers={**headers, "X-Import-Preview-Token": "synthetic",
                           "Content-Type": "text/csv"}, content=CONTENT)
    with monkeypatch.context() as patch:
        patch.setattr(command_audit, "_application_recorder", lambda _: None)
        baseline = send()
    calls, record = [], RejectionRecorder.record_after_settlement
    def observed(writer, handle):
        calls.append(handle)
        if outcome == "RECORDED": return record(writer, handle)
        return RejectionRecordingResult(outcome, handle, None, outcome)
    monkeypatch.setattr(RejectionRecorder, "record_after_settlement", observed)
    response = send()
    assert response.status_code == baseline.status_code == 403
    assert response.json() == baseline.json()
    for name in ("Cache-Control", "Content-Type", "X-Request-ID", "X-Content-Type-Options"):
        assert response.headers.get(name) == baseline.headers.get(name)
    assert len(calls) == 1
    assert calls[0].draft.receipts[-1].evidence.decision == PermissionResult.DENY
    with SessionLocal() as db:
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.organization_id == ids["organizations"]["a"])))
        assert len(audits) == int(outcome == "RECORDED")


@pytest.mark.parametrize("path", ["missing", "foreign", "foreign-org", "csrf", "selector", "unauthenticated"])
def test_http_privacy_and_pre_principal_exclusions(tenant_workspace, monkeypatch, path):
    from backend.services.rejection_recorder import RejectionRecorder
    from backend.database.session import SessionLocal
    workspace = tenant_workspace
    client, ids = workspace["clients"]["a"], workspace["ids"]
    headers = {"X-Organization-ID": str(ids["organizations"]["a"]),
               "X-CSRF-Token": client.cookies.get(workspace["csrf_cookie"])}
    monkeypatch.setattr(RejectionRecorder, "record_after_settlement", lambda *_: pytest.fail("Out-of-scope HTTP denial recorded"))
    target = ids["leads"]["b"] if path in {"foreign", "foreign-org"} else 9223372036854775807
    if path == "foreign-org": headers["X-Organization-ID"] = str(ids["organizations"]["b"])
    if path == "csrf": headers.pop("X-CSRF-Token")
    if path == "selector": headers.pop("X-Organization-ID")
    if path == "unauthenticated":
        client.cookies.clear()
    response = client.patch(f"/api/leads/{target}/lifecycle", headers=headers, json=dict(status="Qualified"))
    assert response.status_code == {"missing": 404, "foreign": 404, "foreign-org": 403,
                                    "csrf": 403, "selector": 400, "unauthenticated": 401}[path]
    if path in {"missing", "foreign"}: assert response.json() == {"detail": "Lead not found"}
    assert "Beta" not in response.text and "beta-lead" not in response.text
    with SessionLocal() as db:
        assert list(db.scalars(select(AuditEvent))) == []


def machine_denial_case(engine, monkeypatch, kind, mode):
    from backend.schemas.execution_principal import ExecutionPrincipal
    from backend.schemas.action_permission import MachineAuthorizationContext
    case, writer = prepare(engine), recorder(engine)
    principal = getattr(ExecutionPrincipal, "for_" + kind.lower())(
        "p1g-" + kind.lower(), case["ids"]["org"], correlation_id="p1g-machine")
    context = None
    if mode == "empty": context = MachineAuthorizationContext(principal, frozenset())
    if mode == "raw": context = {"capabilities": [P.LEAD_LIFECYCLE_CHANGE.value], "private": "never serialize"}
    if mode == "mismatched":
        other = getattr(ExecutionPrincipal, "for_" + kind.lower())(
            "different-owner", case["ids"]["org"], correlation_id="p1g-machine")
        context = MachineAuthorizationContext(other, frozenset({P.LEAD_LIFECYCLE_CHANGE}))
    calls, record = [], writer.record_after_settlement
    def observed(handle):
        calls.append(handle)
        return record(handle)
    monkeypatch.setattr(writer, "record_after_settlement", observed)
    try:
        with Session(engine, autoflush=False) as db, pytest.raises(LeadForgeException) as raised:
            invoke(db, case, "lifecycle", writer, principal=principal, machine_context=context)
        assert raised.value.error_code == "ACTION_PERMISSION_DENIED"
        audits = rows(engine, case)[0]
        assert len(audits) == len(calls) == 1
        row = audits[0]
        assert row.organization_id == principal.organization_id and row.actor_id == principal.actor_id
        assert row.principal_type == kind and row.authority_role is None and row.target_id is None
        assert row.details == {} and row.event_type == "permission.denied"
        reason = {"empty": "DENIED_PERMISSION_NOT_GRANTED", "mismatched": "DENIED_PRINCIPAL_MISMATCH"}.get(
            mode, "DENIED_INVALID_CONTEXT")
        assert row.authorization_evidence == [dict(permission=P.LEAD_LIFECYCLE_CHANGE, decision="DENY", reason_code=reason)]
        assert "never serialize" not in str(row.authorization_evidence)
    finally:
        writer.close()


@pytest.mark.parametrize("kind", ["SYSTEM", "AGENT", "WORKFLOW", "INTEGRATION"])
@pytest.mark.parametrize("mode", ["missing", "empty", "raw", "mismatched"])
def test_machine_structural_denials_keep_actual_reason_without_untrusted_authority(denial_engine, monkeypatch, kind, mode):
    machine_denial_case(denial_engine, monkeypatch, kind, mode)


@pytest.mark.parametrize("surface", ["create", "lifecycle", "import-first"])
def test_revoked_membership_records_null_role_without_reauthorization(denial_engine, monkeypatch, surface):
    from backend.models import OrganizationMembership
    from backend.services.action_permission_service import ActionPermissionService
    case, writer = prepare(denial_engine), recorder(denial_engine)
    with Session(denial_engine) as db, transaction(db):
        membership = db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.user_id == case["ids"]["user"]))
        membership.is_active = False
    original, lookups = ActionPermissionService.human_context, []
    def looked_up(service, principal):
        lookups.append(principal)
        return original(service, principal)
    monkeypatch.setattr(ActionPermissionService, "human_context", looked_up)
    try:
        with Session(denial_engine, autoflush=False) as db, pytest.raises(LeadForgeException):
            invoke(db, case, surface, writer)
        audits = rows(denial_engine, case)[0]
        assert len(audits) == len(lookups) == 1
        assert audits[0].authority_role is None
        assert audits[0].authorization_evidence[-1]["reason_code"] == "DENIED_INVALID_CONTEXT"
    finally:
        writer.close()


@pytest.mark.parametrize("surface", ["create", "lifecycle", "import-first"])
def test_recorder_setup_failure_never_changes_success(denial_engine, monkeypatch, surface):
    from backend.services import command_audit
    def unavailable(_db): raise RuntimeError("Private recorder configuration failure")
    monkeypatch.setattr(command_audit, "_application_recorder", unavailable)
    case = prepare(denial_engine)
    with Session(denial_engine, autoflush=False) as db:
        invoke(db, case, surface)
    audits = rows(denial_engine, case)[0]
    assert len(audits) == 1 and audits[0].outcome == "SUCCEEDED"


@pytest.mark.parametrize("organization_id", [True, -1, 0, "untrusted-selector"])
def test_malformed_explicit_tenant_is_not_fabricated_as_trusted_event(denial_engine, organization_id):
    case, writer = prepare(denial_engine), recorder(denial_engine)
    try:
        with Session(denial_engine, autoflush=False) as db, pytest.raises(LeadForgeException) as raised:
            invoke(db, case, "lifecycle", writer, organization_id=organization_id)
        assert raised.value.error_code == "EXECUTION_TENANT_MISMATCH" and not rows(denial_engine, case)[0]
    finally:
        writer.close()


@pytest.mark.parametrize("committed", [False, True])
def test_outer_owner_retains_original_unknown_handle_for_explicit_reconciliation(denial_engine, monkeypatch, committed):
    from backend.services.application_audit import application_audit_boundary
    case, writer = prepare(denial_engine), recorder(denial_engine)
    narrow_policy(monkeypatch, "lifecycle")
    try:
        with Session(denial_engine, autoflush=False) as db:
            with sqlite_outcome(writer, "UNKNOWN_COMMITTED" if committed else "UNKNOWN_ABSENT", monkeypatch):
                with pytest.raises(LeadForgeException):
                    with application_audit_boundary(db, writer) as operation:
                        with transaction(db):
                            invoke(db, case, "lifecycle", writer, audit_operation=operation)
            first = operation.result
            assert first.status == "OUTCOME_UNKNOWN" and first.settlement is not None
            resolved = writer.reconcile_rejection(first.settlement, case["principal"])
            assert resolved.status == ("RECORDED" if committed else "OUTCOME_UNKNOWN")
            assert resolved.settlement is first.settlement
    finally:
        writer.close()


def test_request_endpoint_metadata_is_passive_and_released_with_session(denial_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from backend.database import dependencies
    monkeypatch.setattr(dependencies, "SessionLocal", sessionmaker(bind=denial_engine, autoflush=False))
    reads = []
    def statement(*_): reads.append(True)
    event.listen(denial_engine, "before_cursor_execute", statement)
    request_db = dependencies.get_db()
    db = next(request_db)
    try:
        assert not reads and dependencies.canonical_audit_connections(db) == ()
        db.scalar(select(Lead.id))
        count = len(reads)
        assert len(dependencies.canonical_audit_connections(db)) == 1
        assert len(dependencies.canonical_audit_connections(db)) == 1 and len(reads) == count
        assert not any("operation" in key for key in db.info)
    finally:
        request_db.close()
        assert dependencies.canonical_audit_connections(db) == ()
        event.remove(denial_engine, "before_cursor_execute", statement)


def test_request_endpoint_metadata_does_not_cross_request_sessions(denial_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from backend.database import dependencies
    monkeypatch.setattr(dependencies, "SessionLocal", sessionmaker(bind=denial_engine, autoflush=False))
    first, second = dependencies.get_db(), dependencies.get_db()
    a, b = next(first), next(second)
    try:
        a.scalar(select(Lead.id))
        assert len(dependencies.canonical_audit_connections(a)) == 1
        assert dependencies.canonical_audit_connections(b) == ()
        b.scalar(select(Lead.id))
        assert dependencies.canonical_audit_connections(a)[0] is not dependencies.canonical_audit_connections(b)[0]
        first.close()
        assert dependencies.canonical_audit_connections(a) == ()
        assert len(dependencies.canonical_audit_connections(b)) == 1
    finally:
        first.close()
        second.close()
