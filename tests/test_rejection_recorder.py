"""Disposable architecture tests; no production business denial wiring."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.database.base import Base
from backend.models import AuditEvent, Lead
from backend.schemas.action_permission import ActionPermission as P, HumanAuthorizationContext, MachineAuthorizationContext
from backend.schemas.audit_event import AuditValidationError
from backend.schemas.execution_principal import ExecutionPrincipal
from tests.test_lead_import_audit import seed_case, readback, transaction


@pytest.fixture
def cleanup_rejection_storage(monkeypatch):
    from backend.database import rejection_storage
    engines = []
    create = rejection_storage.create_engine
    def tracked(*args, **kwargs):
        engine = create(*args, **kwargs)
        engines.append(engine)
        return engine
    monkeypatch.setattr(rejection_storage, "create_engine", tracked)
    yield
    for engine in engines:
        engine.dispose()


@pytest.fixture(autouse=True)
def owned_recorder_pools(cleanup_rejection_storage):
    pass


@pytest.fixture
def rejection_engine(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "rejection.db").as_posix())
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def recorder(engine):
    from backend.services.rejection_recorder import RejectionRecorder
    return RejectionRecorder(sessionmaker(bind=engine, autoflush=False),
        canonical_connect_args=getattr(engine, "_test_rejection_connect_args", {}))


def boundary(db, writer):
    from backend.services.application_audit import application_audit_boundary
    return application_audit_boundary(db, writer)


def rejection(case, kind="USER", tenant=False):
    from backend.services.permission_evaluator import evaluate_permission
    from backend.services.audit_event_builder import AuditEventBuilder, capture_authorization_receipt
    principal = case["principal"] if kind == "USER" else getattr(ExecutionPrincipal, "for_" + kind.lower())(
        "synthetic-" + kind.lower(), case["ids"]["org"], correlation_id="rejection-command")
    if tenant:
        return AuditEventBuilder.tenant_rejected(principal, action=P.LEAD_LIFECYCLE_CHANGE,
            requested_organization_id=case["ids"]["foreign_org"], occurred_at=datetime.now(timezone.utc))
    authority = (HumanAuthorizationContext(principal, "member", frozenset()) if kind == "USER"
                 else MachineAuthorizationContext(principal, frozenset()))
    decision = evaluate_permission(principal, authority, P.LEAD_LIFECYCLE_CHANGE, principal.organization_id)
    return AuditEventBuilder.permission_denied(principal, action=P.LEAD_LIFECYCLE_CHANGE,
        organization_id=principal.organization_id,
        authorization=(capture_authorization_receipt(principal, decision, authority),),
        occurred_at=datetime.now(timezone.utc))


def denied_error():
    from backend.core.exceptions import LeadForgeException
    return LeadForgeException("Action not permitted.", status_code=403, error_code="ACTION_PERMISSION_DENIED")


def provisional(db, case):
    db.add(Lead(organization_id=case["ids"]["org"], company="Private provisional company",
                email="provisional@example.com", source="test", notes="private request note"))
    db.flush()


def record_denied(engine, case, writer, draft=None, *, work=True):
    denial = denied_error()
    with Session(engine, autoflush=False) as db:
        with pytest.raises(type(denial)) as raised:
            with boundary(db, writer) as operation:
                with transaction(db):
                    if work: provisional(db, case)
                    operation.capture_rejection(draft or rejection(case))
                    raise denial
        assert raised.value is denial
    return operation


@pytest.mark.parametrize("kind", ["USER", "SYSTEM", "AGENT", "WORKFLOW", "INTEGRATION"])
def test_durable_rejection_after_business_rollback_exact_payload(rejection_engine, monkeypatch, kind):
    from backend.database.transaction_policy import current_root
    from backend.repositories.audit_repository import AuditRepository
    case = seed_case(rejection_engine)
    writer, seen, append = recorder(rejection_engine), {}, AuditRepository.append
    draft = rejection(case, kind)
    original = denied_error()
    with Session(rejection_engine, autoflush=False) as business:
        def business_begin(_db, tx, connection):
            if tx.parent is None: seen.update(business_session=business, business_tx=tx, business_connection=connection)
        event.listen(business, "after_begin", business_begin)
        def observe(repo, value):
            assert repo.db is not business and not business.in_transaction()
            assert readback(rejection_engine, case) == ([], [])
            root = current_root(repo.db)
            assert root is not None and root is not seen["business_root"]
            assert root.authority.nonce is not seen["business_authority"].nonce
            def audit_begin(_db, tx, connection):
                assert tx is not seen["business_tx"] and connection is not seen["business_connection"]
                seen.update(audit_session=repo.db, audit_tx=tx, audit_connection=connection)
            if root.authority.connection is not None:
                # PG timeout setup establishes the same audit root before append.
                audit_begin(repo.db, repo.db.get_transaction(), root.authority.connection)
            else:
                event.listen(repo.db, "after_begin", audit_begin, once=True)
            return append(repo, value)
        monkeypatch.setattr(AuditRepository, "append", observe)
        with pytest.raises(type(original)) as raised:
            with boundary(business, writer) as operation:
                with transaction(business):
                    provisional(business, case)
                    root = current_root(business)
                    seen.update(business_root=root, business_authority=root.authority)
                    assert operation.capture_rejection(draft)
                    assert readback(rejection_engine, case) == ([], [])
                    raise original
        assert raised.value is original
    leads, audits = readback(rejection_engine, case)
    assert leads == [] and len(audits) == 1
    audit = audits[0]
    assert operation.receipt.event_id == audit.event_id == draft.event_id
    assert audit.event_type == "permission.denied" and audit.outcome == "DENIED"
    assert audit.action == "lead.lifecycle.change" and audit.reason_code == "ACTION_PERMISSION_DENIED"
    assert audit.organization_id == case["ids"]["org"] and audit.principal_type == kind
    assert audit.actor_id == str(draft.principal.actor_id) and audit.correlation_id == draft.principal.correlation_id
    assert audit.target_id is None and audit.target_type == "lead" and audit.details == {}
    assert audit.authorization_evidence == [dict(permission="lead.lifecycle.change", decision="DENY",
                                                reason_code="DENIED_PERMISSION_NOT_GRANTED")]
    assert audit.authority_role == ("member" if kind == "USER" else None)
    assert audit.schema_version == 1 and audit.occurred_at.tzinfo is not None and audit.recorded_at >= audit.occurred_at
    for forbidden in ("Private provisional company", "provisional@example.com", "private request note"):
        assert forbidden not in json.dumps(audit.details)
    assert seen["audit_connection"].closed and seen["business_connection"].closed
    assert not seen["audit_session"].in_transaction() and current_root(seen["audit_session"]) is None


def test_no_sql_denial_can_record_only_after_scope_exit(rejection_engine):
    case = seed_case(rejection_engine)
    operation = record_denied(rejection_engine, case, recorder(rejection_engine), work=False)
    assert operation.receipt is not None
    assert len(readback(rejection_engine, case)[1]) == 1


def test_existing_read_autobegin_is_settled_before_recording(rejection_engine):
    case = seed_case(rejection_engine)
    with Session(rejection_engine, autoflush=False) as db:
        db.scalar(select(Lead.id))
        with pytest.raises(type(denied_error())):
            with boundary(db, recorder(rejection_engine)) as operation:
                with transaction(db):
                    operation.capture_rejection(rejection(case))
                    raise denied_error()
    assert operation.receipt is not None and len(readback(rejection_engine, case)[1]) == 1


@pytest.mark.parametrize("failure", ["append", "constraint", "commit", "close"])
def test_audit_failure_preserves_original_denial_and_business_rollback(rejection_engine, monkeypatch, failure):
    from backend.repositories.audit_repository import AuditRepository
    from backend.services import application_audit as module
    case = seed_case(rejection_engine)
    writer, observations, logs = recorder(rejection_engine), [], []
    append = AuditRepository.append
    def intercept(repo, draft):
        observations.append(repo.db)
        assert readback(rejection_engine, case) == ([], [])
        if failure == "append": raise RuntimeError("private database URI and credential must not be logged")
        if failure == "commit":
            def fail_commit(): raise RuntimeError("private commit detail")
            monkeypatch.setattr(repo.db, "commit", fail_commit)
        if failure == "close":
            close = repo.db.close
            def fail_close():
                close()
                raise RuntimeError("private cleanup detail")
            monkeypatch.setattr(repo.db, "close", fail_close)
        return append(repo, draft)
    def corrupt(_mapper, _connection, audit): audit.schema_version = 0
    monkeypatch.setattr(AuditRepository, "append", intercept)
    monkeypatch.setattr(module, "event", lambda name, **fields: logs.append((name, fields)))
    if failure == "constraint": event.listen(AuditEvent, "before_insert", corrupt)
    try:
        operation = record_denied(rejection_engine, case, writer)
    finally:
        if failure == "constraint": event.remove(AuditEvent, "before_insert", corrupt)
    leads, audits = readback(rejection_engine, case)
    assert leads == [] and len(audits) == (1 if failure == "close" else 0)
    # Known acknowledged commit remains RECORDED even if close then fails.
    assert (operation.receipt is not None) == (failure == "close")
    assert observations and not observations[0].in_transaction()
    assert logs[0][0] == "audit.rejection.persistence_failed"
    assert "private" not in str(logs) and "exc" not in logs[0][1]


def test_caught_nested_denial_records_once_after_rollback_only_root(rejection_engine):
    from backend.database.transactions import TransactionAborted
    case = seed_case(rejection_engine)
    first, later = rejection(case), rejection(case, tenant=True)
    with Session(rejection_engine, autoflush=False) as db:
        with pytest.raises(TransactionAborted):
            with boundary(db, recorder(rejection_engine)) as operation:
                with transaction(db):
                    provisional(db, case)
                    try:
                        with transaction(db):
                            assert operation.capture_rejection(first)
                            assert not operation.capture_rejection(later)
                            raise denied_error()
                    except type(denied_error()): pass
    leads, audits = readback(rejection_engine, case)
    assert leads == [] and len(audits) == 1 and audits[0].event_id == first.event_id


@pytest.mark.parametrize("mode", ["active_root", "external_begin", "different_database"])
def test_boundary_rejects_wrong_owner_before_writing(rejection_engine, tmp_path, mode):
    case = seed_case(rejection_engine)
    other = create_engine("sqlite:///" + (tmp_path / "other.db").as_posix()) if mode == "different_database" else None
    try:
        with Session(rejection_engine) as db:
            owner = transaction(db) if mode == "active_root" else db.begin()
            with owner:
                with pytest.raises(AuditValidationError):
                    with boundary(db, recorder(other or rejection_engine)): pytest.fail("Invalid boundary entered")
        assert readback(rejection_engine, case) == ([], [])
    finally:
        if other is not None: other.dispose()


@pytest.mark.parametrize("mode", ["unsettled", "committed", "second_root", "closed_capture"])
def test_ambiguous_or_wrong_order_never_records(rejection_engine, monkeypatch, mode):
    from backend.services import application_audit as module
    case = seed_case(rejection_engine)
    logs = []
    monkeypatch.setattr(module, "event", lambda name, **fields: logs.append(name))
    with Session(rejection_engine, autoflush=False) as db:
        if mode == "unsettled":
            with boundary(db, recorder(rejection_engine)) as operation:
                owner = transaction(db)
                owner.__enter__()
                provisional(db, case)
                operation.capture_rejection(rejection(case))
            assert operation.receipt is None and readback(rejection_engine, case) == ([], [])
            owner.__exit__(RuntimeError, RuntimeError("settle owner"), None)
        else:
            with boundary(db, recorder(rejection_engine)) as operation:
                if mode in {"second_root", "closed_capture"}:
                    with pytest.raises(type(denied_error())):
                        with transaction(db):
                            provisional(db, case)
                            operation.capture_rejection(rejection(case))
                            raise denied_error()
                    if mode == "second_root":
                        with transaction(db): db.scalar(select(Lead.id))
                else:
                    with transaction(db): operation.capture_rejection(rejection(case))
            if mode == "closed_capture":
                assert operation.receipt is not None
                with pytest.raises(AuditValidationError): operation.capture_rejection(rejection(case))
                return
        assert operation.receipt is None
    assert readback(rejection_engine, case) == ([], [])
    assert logs == ["audit.rejection.recording_deferred_unavailable"]


@pytest.mark.parametrize("mode", ["success", "dict", "tampered", "tenant"])
def test_only_canonical_private_safe_rejection_input_is_accepted(rejection_engine, mode):
    from tests.test_audit_construction import completed
    case = seed_case(rejection_engine)
    draft = rejection(case)
    if mode == "success": draft = completed(case["principal"])
    elif mode == "dict": draft = {"organization_id": case["ids"]["foreign_org"], "password": "private synthetic input"}
    elif mode == "tampered": draft = replace(draft, principal=ExecutionPrincipal.for_user(
        case["ids"]["user"], case["ids"]["foreign_org"]))
    if mode == "tenant":
        operation = record_denied(rejection_engine, case, recorder(rejection_engine), rejection(case, tenant=True))
        assert operation.receipt is not None
        audit = readback(rejection_engine, case)[1][0]
        assert audit.organization_id == case["ids"]["org"] and audit.target_id is None and audit.details == {}
        assert audit.authorization_evidence == [] and audit.reason_code == "EXECUTION_TENANT_MISMATCH"
    else:
        with Session(rejection_engine) as db:
            with pytest.raises(AuditValidationError):
                with boundary(db, recorder(rejection_engine)) as operation:
                    with transaction(db): operation.capture_rejection(draft)
        assert readback(rejection_engine, case) == ([], [])


def test_poisoned_business_session_is_not_touched_by_fresh_recorder(rejection_engine, monkeypatch):
    from backend.repositories.audit_repository import AuditRepository
    case = seed_case(rejection_engine)
    append = AuditRepository.append
    with Session(rejection_engine, autoflush=False) as db:
        def guarded(repo, draft):
            assert repo.db is not db
            monkeypatch.setattr(db, "commit", lambda: pytest.fail("Touched failed business Session"))
            monkeypatch.setattr(db, "rollback", lambda: pytest.fail("Touched failed business Session"))
            return append(repo, draft)
        monkeypatch.setattr(AuditRepository, "append", guarded)
        with pytest.raises(IntegrityError):
            with boundary(db, recorder(rejection_engine)) as operation:
                with transaction(db):
                    operation.capture_rejection(rejection(case))
                    db.add(Lead(organization_id=case["ids"]["org"], company=None, email="invalid@example.com", source="test"))
                    db.flush()
    assert operation.receipt is not None and len(readback(rejection_engine, case)[1]) == 1


def test_no_rejection_on_normal_success_and_no_factory_call(rejection_engine, monkeypatch):
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    monkeypatch.setattr(writer, "record_after_settlement", lambda *_: pytest.fail("Success invoked rejection recorder"))
    with Session(rejection_engine) as db:
        with boundary(db, writer) as operation:
            with transaction(db): provisional(db, case)
    leads, audits = readback(rejection_engine, case)
    assert len(leads) == 1 and audits == [] and operation.receipt is None


def test_unsealed_or_wrong_recorder_proof_does_not_open_session(rejection_engine, monkeypatch):
    from backend.services.application_audit import SettledRejection
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    monkeypatch.setattr(writer, "_persist", lambda *_: pytest.fail("Invalid proof opened audit Session"))
    record = SettledRejection(rejection(case), 1, 2, 3, id(rejection_engine), writer._recording_key, None)
    assert writer.record_after_settlement(record).status == "NOT_RECORDED"
    assert writer.record_after_settlement({"token": "private synthetic input"}).status == "NOT_RECORDED"
    assert readback(rejection_engine, case) == ([], [])


def test_frozen_settlement_replay_is_not_retried_or_duplicated(rejection_engine, monkeypatch):
    case = seed_case(rejection_engine)
    writer, records = recorder(rejection_engine), []
    original = writer.record_after_settlement
    def capture(record):
        records.append(record)
        with pytest.raises(FrozenInstanceError): record.business_session_id = 0
        assert not any(isinstance(value, Session) for value in vars(record).values())
        return original(record)
    monkeypatch.setattr(writer, "record_after_settlement", capture)
    record_denied(rejection_engine, case, writer)
    assert original(records[0]).status == "RECORDED"  # Acknowledged knowledge is absorbing.
    assert recorder(rejection_engine).record_after_settlement(records[0]).status == "NOT_RECORDED"
    assert len(readback(rejection_engine, case)[1]) == 1


@pytest.mark.parametrize("direction", ["ambient", "business_to_audit", "audit_to_business"])
def test_root_permits_cannot_cross_and_ambient_authority_is_discarded(rejection_engine, monkeypatch, direction):
    from backend.database import transaction_policy as policy
    from backend.repositories.audit_repository import AuditRepository
    case = seed_case(rejection_engine)
    writer, old, checks = recorder(rejection_engine), {}, []
    append = AuditRepository.append
    def inspect(repo, draft):
        current = policy.current_root(repo.db)
        assert policy._permit.get() is None and policy._flushing.get() is None
        assert current.authority.nonce is not old["root"].authority.nonce
        if direction == "ambient":
            checks.append(True)
        else:
            source, target = ((old["root"], current) if direction == "business_to_audit" else (current, old["root"]))
            token = policy._permit.set(policy._Permit(source.authority, policy.Operation.ROOT_COMMIT, ["foreign"]))
            try:
                with pytest.raises(policy.TransactionPolicyViolation):
                    target.consume("foreign", {policy.Operation.ROOT_COMMIT})
                checks.append(True)
            finally:
                policy._permit.reset(token)
            if direction == "business_to_audit":
                # The audit root was poisoned by the attempted foreign permit;
                # its later append/settlement must not succeed.
                assert current.failed and current.broken
        return append(repo, draft)
    monkeypatch.setattr(AuditRepository, "append", inspect)
    original_record = writer.record_after_settlement
    def ambient(record):
        token = policy._permit.set(policy._Permit(old["root"].authority, policy.Operation.ROOT_COMMIT, ["foreign"]))
        flushing = policy._flushing.set(object())
        try:
            result = original_record(record)
            assert policy._permit.get().authority is old["root"].authority
            return result
        finally:
            policy._flushing.reset(flushing)
            policy._permit.reset(token)
    monkeypatch.setattr(writer, "record_after_settlement", ambient)
    with Session(rejection_engine, autoflush=False) as db:
        with pytest.raises(type(denied_error())):
            with boundary(db, writer) as operation:
                with transaction(db):
                    provisional(db, case)
                    old["root"] = policy.current_root(db)
                    operation.capture_rejection(rejection(case))
                    raise denied_error()
    assert checks == [True]
    assert len(readback(rejection_engine, case)[1]) == (0 if direction == "business_to_audit" else 1)


def test_faulty_factory_cannot_reuse_or_close_business_session(rejection_engine, monkeypatch):
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    original = writer.record_after_settlement
    with Session(rejection_engine) as business:
        def reuse(record):
            monkeypatch.setattr(writer._session_factory, "class_", lambda **_kw: business)
            with monkeypatch.context() as patch:
                patch.setattr(business, "commit", lambda: pytest.fail("Settled business Session"))
                patch.setattr(business, "rollback", lambda: pytest.fail("Settled business Session"))
                patch.setattr(business, "close", lambda: pytest.fail("Closed business Session"))
                return original(record)
        monkeypatch.setattr(writer, "record_after_settlement", reuse)
        with pytest.raises(type(denied_error())):
            with boundary(business, writer) as operation:
                with transaction(business):
                    provisional(business, case)
                    operation.capture_rejection(rejection(case))
                    raise denied_error()
    assert operation.receipt is None and readback(rejection_engine, case) == ([], [])


def test_logging_failure_cannot_replace_original_denial(rejection_engine, monkeypatch):
    from backend.services import application_audit as module
    from backend.repositories.audit_repository import AuditRepository
    case = seed_case(rejection_engine)
    def fail(*_args, **_kw): raise RuntimeError("private failure")
    monkeypatch.setattr(AuditRepository, "append", fail)
    monkeypatch.setattr(module, "event", fail)
    assert record_denied(rejection_engine, case, recorder(rejection_engine)).receipt is None
    assert readback(rejection_engine, case) == ([], [])


def test_unconfirmed_rollback_skips_writer_and_preserves_original_error(rejection_engine, monkeypatch):
    from backend.services import application_audit as module
    case = seed_case(rejection_engine)
    writer, logs = recorder(rejection_engine), []
    monkeypatch.setattr(module, "event", lambda name, **fields: logs.append(name))
    monkeypatch.setattr(writer, "record_after_settlement", lambda *_: pytest.fail("Unconfirmed cleanup wrote an audit"))
    original = denied_error()
    with Session(rejection_engine, autoflush=False) as business:
        def failed_rollback(): raise RuntimeError("Synthetic rollback failure")
        monkeypatch.setattr(business, "rollback", failed_rollback)
        with pytest.raises(type(original)) as rejected:
            with boundary(business, writer) as operation:
                with transaction(business):
                    provisional(business, case)
                    operation.capture_rejection(rejection(case))
                    raise original
        assert rejected.value is original and operation.receipt is None
    assert readback(rejection_engine, case) == ([], [])
    assert logs == ["audit.rejection.recording_deferred_unavailable"]


@pytest.mark.parametrize("kind", ["connection", "callable", "two_phase"])
def test_noncanonical_factory_cannot_adopt_foreign_root(rejection_engine, kind):
    from backend.services.rejection_recorder import RejectionRecorder
    if kind == "connection":
        with rejection_engine.connect() as connection, connection.begin():
            with pytest.raises(ValueError): RejectionRecorder(sessionmaker(bind=connection))
    else:
        factory = (lambda: Session(rejection_engine)) if kind == "callable" else sessionmaker(bind=rejection_engine, twophase=True)
        with pytest.raises(ValueError): RejectionRecorder(factory)


def test_factory_rebinding_cannot_write_into_another_database(rejection_engine, tmp_path, monkeypatch):
    case = seed_case(rejection_engine)
    other = create_engine("sqlite:///" + (tmp_path / "foreign-audit.db").as_posix())
    Base.metadata.create_all(other)
    writer = recorder(rejection_engine)
    original = writer.record_after_settlement
    def rebind(record):
        writer._session_factory.configure(bind=other)
        return original(record)
    monkeypatch.setattr(writer, "record_after_settlement", rebind)
    try:
        assert record_denied(rejection_engine, case, writer).receipt is None
        assert readback(rejection_engine, case) == ([], [])
        with Session(other) as observer:
            assert list(observer.scalars(select(AuditEvent))) == []
    finally:
        other.dispose()


def test_recorder_environment_is_read_only(rejection_engine):
    writer = recorder(rejection_engine)
    with pytest.raises(AttributeError): writer.database_bind = None
    assert writer.database_bind is rejection_engine
