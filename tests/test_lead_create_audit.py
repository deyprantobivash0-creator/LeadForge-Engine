"""I3A command atomicity and actual authorization evidence in disposable databases."""

from uuid import uuid4
import traceback
import warnings

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.base import Base
from backend.models import AuditEvent, Lead, Organization, OrganizationMembership, User
from backend.schemas.action_permission import ActionPermission as P, MachineAuthorizationContext
from backend.schemas.execution_principal import ActorReference, ExecutionPrincipal, PrincipalType


@pytest.fixture
def i3a_db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'create-audit.db').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, autoflush=False) as db:
            yield db
    finally:
        engine.dispose()


def identity(db, kind="USER"):
    suffix = uuid4().hex
    org = Organization(name="Disposable I3A", slug="i3a-" + suffix)
    account = User(email=suffix + "@example.invalid", password_hash="unused-synthetic-hash")
    db.add_all([org, account]); db.flush()
    membership = OrganizationMembership(organization_id=org.id, user_id=account.id, role="member")
    db.add(membership); db.commit()
    if kind == "USER":
        return ExecutionPrincipal.for_user(account.id, org.id, correlation_id="i3a-exact-correlation"), None
    parent = ActorReference(principal_type=PrincipalType.USER, actor_id=account.id)
    factory = getattr(ExecutionPrincipal, "for_" + kind.lower())
    extra = dict(workflow_run_id="parent-workflow", integration_id="parent-integration") if kind == "AGENT" else {}
    principal = factory("i3a-" + kind.lower(), org.id, delegated_by=parent,
                        correlation_id="i3a-exact-correlation", **extra)
    return principal, MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))


def service(db):
    # Keep settings imports behind the guarded PostgreSQL fixture configuration.
    from backend.services.lead_service import LeadService
    return LeadService(db)


def transaction(db):
    from backend.database.transactions import service_transaction
    return service_transaction(db)


def create(db, principal, context=None, **changes):
    kwargs = dict(company="Distinctive synthetic company", email="distinctive@example.invalid",
                  source="synthetic-source", organization_id=principal.organization_id,
                  machine_context=context)
    kwargs.update(changes)
    return service(db).create_lead(principal, **kwargs)


def rows(db, principal):
    with Session(db.get_bind()) as observer:
        leads = list(observer.scalars(select(Lead).where(Lead.organization_id == principal.organization_id)))
        audits = list(observer.scalars(select(AuditEvent).where(AuditEvent.organization_id == principal.organization_id)))
        return leads, audits


@pytest.mark.parametrize("kind", ["USER", "SYSTEM", "AGENT", "WORKFLOW", "INTEGRATION"])
def test_create_uses_actual_decision_and_same_context_once(i3a_db, monkeypatch, kind):
    import backend.services.action_permission_service as permission_module
    import backend.services.lead_service as lead_module
    principal, context = identity(i3a_db, kind)
    evaluated, captured = [], []
    evaluate = permission_module.evaluate_permission
    capture = lead_module.capture_authorization_receipt

    def observed_evaluation(p, authority, permission, org):
        result = evaluate(p, authority, permission, org)
        evaluated.append((result, authority))
        return result

    def observed_capture(p, result, authority):
        assert result is evaluated[0][0] and authority is evaluated[0][1]
        assert p is principal
        captured.append((result, authority))
        return capture(p, result, authority)

    monkeypatch.setattr(permission_module, "evaluate_permission", observed_evaluation)
    monkeypatch.setattr(lead_module, "capture_authorization_receipt", observed_capture)
    lead = create(i3a_db, principal, context)
    leads, audits = rows(i3a_db, principal)
    assert len(leads) == len(audits) == len(evaluated) == len(captured) == 1
    audit = audits[0]; decision, authority = evaluated[0]
    assert audit.event_type == "business.command.completed" and audit.action == "lead.create"
    assert audit.outcome == "SUCCEEDED" and audit.reason_code == "COMMAND_COMPLETED"
    assert audit.organization_id == principal.organization_id
    assert audit.principal_type == principal.principal_type.value and audit.actor_id == str(principal.actor_id)
    assert audit.correlation_id == principal.correlation_id
    assert audit.target_type == "lead" and audit.target_id == str(lead.id)
    assert audit.authorization_evidence == [dict(permission=decision.permission.value,
        decision=decision.result.value, reason_code=decision.reason_code.value)]
    assert audit.authority_role == (authority.role if kind == "USER" else None)
    assert audit.details == {} and audit.schema_version == 1
    assert audit.occurred_at.tzinfo is not None and audit.recorded_at >= audit.occurred_at
    for field in ("agent_id", "workflow_run_id", "integration_id"):
        assert getattr(audit, field) == getattr(principal, field)
    parent = principal.delegated_by
    assert audit.delegated_by_type == (parent.principal_type.value if parent else None)
    assert audit.delegated_by_actor_id == (str(parent.actor_id) if parent else None)
    assert lead.email not in str(audit.authorization_evidence) and lead.company not in str(audit.details)


@pytest.mark.parametrize("failure", ["construction", "append", "flush"])
def test_required_audit_failure_after_lead_flush_rolls_back(i3a_db, monkeypatch, failure):
    from backend.schemas.audit_event import AuditValidationError
    from backend.services.audit_event_builder import AuditEventBuilder
    from backend.repositories.audit_repository import AuditRepository
    principal, context = identity(i3a_db)
    seen = []

    def observe_flushed_lead():
        lead = i3a_db.scalar(select(Lead).where(Lead.organization_id == principal.organization_id))
        assert lead is not None and lead.id is not None
        seen.append(lead.id)

    def fail_construction(*args, **kwargs):
        observe_flushed_lead()
        raise AuditValidationError("Synthetic audit construction failure.")

    def fail_append(repo, draft):
        assert repo.db is i3a_db
        observe_flushed_lead()
        raise RuntimeError("Synthetic audit append failure")

    def fail_constraint(_mapper, _connection, item):
        observe_flushed_lead()
        item.schema_version = 0  # Actual database CHECK failure, not a fake flush exception.

    expected = {"construction": AuditValidationError, "append": RuntimeError, "flush": IntegrityError}[failure]
    if failure == "construction": monkeypatch.setattr(AuditEventBuilder, "create_completed", fail_construction)
    elif failure == "append": monkeypatch.setattr(AuditRepository, "append", fail_append)
    else: event.listen(AuditEvent, "before_insert", fail_constraint)
    try:
        with pytest.raises(expected): create(i3a_db, principal, context)
    finally:
        if failure == "flush": event.remove(AuditEvent, "before_insert", fail_constraint)
    assert len(seen) == 1 and rows(i3a_db, principal) == ([], [])
    assert i3a_db.is_active and not i3a_db.in_transaction()


@pytest.mark.parametrize("failure", ["duplicate", "not_null", "repository"])
def test_lead_failure_does_not_append_success(i3a_db, monkeypatch, failure):
    from backend.repositories.audit_repository import AuditRepository
    from backend.repositories.lead_repository import LeadRepository
    principal, context = identity(i3a_db)
    if failure == "duplicate": create(i3a_db, principal, context)
    before = tuple(len(items) for items in rows(i3a_db, principal))
    monkeypatch.setattr(AuditRepository, "append", lambda *args: pytest.fail("Failed lead reached audit append"))
    if failure == "repository":
        def fail(*args): raise RuntimeError("Synthetic lead persistence failure")
        monkeypatch.setattr(LeadRepository, "create_lead", fail)
    expected = {"duplicate": ValueError, "not_null": IntegrityError, "repository": RuntimeError}[failure]
    with pytest.raises(expected):
        create(i3a_db, principal, context, **({"company": None} if failure == "not_null" else {}))
    assert tuple(len(items) for items in rows(i3a_db, principal)) == before


@pytest.mark.parametrize("denial", ["inactive_membership", "unknown_role", "caller_context", "machine_scope"])
def test_denial_creates_neither_lead_nor_audit(i3a_db, monkeypatch, denial):
    from backend.core.exceptions import LeadForgeException
    from backend.repositories.permission_repository import PermissionRepository
    from backend.schemas.action_permission import HumanAuthorizationContext, ROLE_PERMISSIONS
    principal, context = identity(i3a_db, "SYSTEM" if denial == "machine_scope" else "USER")
    if denial == "inactive_membership":
        membership = i3a_db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == principal.actor_id))
        membership.is_active = False; i3a_db.commit()
    elif denial == "unknown_role": monkeypatch.setattr(PermissionRepository, "active_role", lambda *args: "unmapped")
    elif denial == "caller_context": context = HumanAuthorizationContext(principal, "owner", ROLE_PERMISSIONS["owner"])
    else: context = MachineAuthorizationContext(principal, frozenset())
    with pytest.raises(LeadForgeException) as rejected: create(i3a_db, principal, context)
    assert rejected.value.error_code == "ACTION_PERMISSION_DENIED"
    assert rows(i3a_db, principal) == ([], [])


def test_tenant_mismatch_has_no_success_or_denial_audit(i3a_db):
    from backend.core.exceptions import LeadForgeException
    principal, context = identity(i3a_db)
    with pytest.raises(LeadForgeException) as rejected:
        create(i3a_db, principal, context, organization_id=principal.organization_id + 1)
    assert rejected.value.error_code == "EXECUTION_TENANT_MISMATCH"
    assert rows(i3a_db, principal) == ([], [])


@pytest.mark.parametrize("settlement", ["commit", "outer_failure", "caught_nested_failure"])
def test_nested_create_shares_session_and_one_root_settlement(i3a_db, monkeypatch, settlement):
    from backend.database.transactions import TransactionAborted
    from backend.repositories.audit_repository import AuditRepository
    principal, context = identity(i3a_db)
    commits, appends = [], []
    original_commit, original_append = i3a_db.commit, AuditRepository.append

    def counted_commit(): commits.append(True); original_commit()
    def observed_append(repo, draft):
        assert repo.db is i3a_db and commits == []
        appends.append(draft.event_id)
        return original_append(repo, draft)

    monkeypatch.setattr(i3a_db, "commit", counted_commit)
    monkeypatch.setattr(AuditRepository, "append", observed_append)

    def operation():
        with transaction(i3a_db):
            create(i3a_db, principal, context)
            assert len(appends) == 1 and not commits
            assert rows(i3a_db, principal) == ([], [])  # Independent observer sees neither provisional write.
            if settlement == "outer_failure": raise RuntimeError("Synthetic later failure")
            if settlement == "caught_nested_failure":
                try:
                    with transaction(i3a_db): raise ValueError("Synthetic nested failure")
                except ValueError: pass

    if settlement == "commit":
        operation(); assert len(commits) == 1
        assert tuple(len(items) for items in rows(i3a_db, principal)) == (1, 1)
    else:
        with pytest.raises(RuntimeError if settlement == "outer_failure" else TransactionAborted): operation()
        assert not commits and rows(i3a_db, principal) == ([], [])


def test_commit_failure_rolls_back_both(i3a_db, monkeypatch):
    principal, context = identity(i3a_db)
    def fail():
        assert len(list(i3a_db.scalars(select(AuditEvent)))) == 1
        raise RuntimeError("Synthetic commit failure")
    monkeypatch.setattr(i3a_db, "commit", fail)
    with pytest.raises(RuntimeError): create(i3a_db, principal, context)
    assert rows(i3a_db, principal) == ([], [])


def test_role_snapshot_is_not_looked_up_after_mutation(i3a_db, monkeypatch):
    from backend.repositories.permission_repository import PermissionRepository
    from backend.services.lead_service import LeadService
    principal, context = identity(i3a_db)
    lookups = []; lookup = PermissionRepository.active_role; mutate = LeadService._create_lead_internal
    def observed_lookup(*args): lookups.append(True); return lookup(*args)
    def changed_role(self, *args):
        lead = mutate(self, *args)
        membership = self.db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == principal.actor_id))
        membership.role = "admin"
        return lead
    monkeypatch.setattr(PermissionRepository, "active_role", observed_lookup)
    monkeypatch.setattr(LeadService, "_create_lead_internal", changed_role)
    create(i3a_db, principal, context)
    assert lookups == [True] and rows(i3a_db, principal)[1][0].authority_role == "member"


def test_existing_require_contract_returns_actual_decision(i3a_db, monkeypatch):
    import backend.services.action_permission_service as module
    principal, context = identity(i3a_db)
    results = []; evaluate = module.evaluate_permission
    def observed(*args):
        result = evaluate(*args); results.append(result); return result
    monkeypatch.setattr(module, "evaluate_permission", observed)
    result = module.ActionPermissionService(i3a_db).require(principal, P.LEAD_CREATE, principal.organization_id)
    assert len(results) == 1 and result is results[0]


@pytest.mark.parametrize("audit_failure", [False, True])
def test_http_create_uses_canonical_atomic_command(tenant_workspace, monkeypatch, audit_failure):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database.session import SessionLocal
    from backend.repositories.audit_repository import AuditRepository
    from tests.api.test_tenant_leads import headers
    workspace = tenant_workspace
    if audit_failure:
        def fail(*args): raise RuntimeError("Synthetic route audit failure")
        monkeypatch.setattr(AuditRepository, "append", fail)
    client = workspace["clients"]["a"]
    h = {**headers(workspace, "a", csrf=True), "X-Request-ID": "i3a-http-correlation", "X-Role": "admin"}
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as request_client:
        request_client.cookies.update(client.cookies)
        response = request_client.post("/api/leads/", headers=h,
            json={"company": "Synthetic HTTP", "email": "i3a-http@example.com", "source": "test"})
    assert response.status_code == (500 if audit_failure else 200)
    org = workspace["ids"]["organizations"]["a"]
    with SessionLocal() as db:
        lead = db.scalar(select(Lead).where(Lead.organization_id == org, Lead.email == "i3a-http@example.com"))
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.organization_id == org,
                                                        AuditEvent.correlation_id == "i3a-http-correlation")))
        if audit_failure: assert lead is None and audits == []
        else:
            assert lead.id == response.json()["id"] and len(audits) == 1
            assert audits[0].actor_id == str(workspace["ids"]["users"]["a"])
            assert audits[0].authority_role == "owner" and audits[0].target_id == str(lead.id)
            assert audits[0].details == {}


def test_mutation_helper_and_lifecycle_do_not_duplicate_create_audit(i3a_db):
    from backend.services.lead_lifecycle_service import LeadLifecycleService
    principal, context = identity(i3a_db, "SYSTEM")
    with transaction(i3a_db):
        lead = create(i3a_db, principal, context)
        lifecycle_context = MachineAuthorizationContext(principal, frozenset({P.LEAD_LIFECYCLE_CHANGE}))
        LeadLifecycleService(i3a_db).update_lifecycle(principal, organization_id=principal.organization_id,
            lead_id=lead.id, status="Contacted", machine_context=lifecycle_context)
        service(i3a_db)._create_lead_internal("Synthetic helper", "helper@example.invalid", "test", principal.organization_id)
    leads, audits = rows(i3a_db, principal)
    assert len(leads) == 2 and len(audits) == 1 and audits[0].action == "lead.create"


def test_e03_r1_canonical_rejection_is_safe_before_authority_or_persistence(i3a_db, monkeypatch, capsys, caplog):
    from backend.core.exceptions import LeadForgeException
    from backend.repositories.permission_repository import PermissionRepository
    from backend.repositories.lead_repository import LeadRepository
    from backend.repositories.audit_repository import AuditRepository
    principal, _context = identity(i3a_db)
    marker = "ProbeR1!"
    candidate = principal.model_copy(update={"actor_id": {"password": marker}})
    def forbidden(*args, **kwargs):
        pytest.fail("Rejected identity reached authority or persistence")
    monkeypatch.setattr(PermissionRepository, "active_role", forbidden)
    monkeypatch.setattr(LeadRepository, "create_lead", forbidden)
    monkeypatch.setattr(AuditRepository, "append", forbidden)
    statements = []
    def observed_statement(*args): statements.append(True)
    engine = i3a_db.get_bind()
    event.listen(engine, "before_cursor_execute", observed_statement)
    capsys.readouterr(); caplog.clear()
    try:
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            with pytest.raises(LeadForgeException) as rejected:
                create(i3a_db, candidate)
    finally:
        event.remove(engine, "before_cursor_execute", observed_statement)
    error = rejected.value
    assert error.error_code == "EXECUTION_IDENTITY_INVALID" and error.status_code == 400
    assert error.__cause__ is None and error.__context__ is None and emitted == []
    output = capsys.readouterr()
    assert marker not in output.out + output.err + caplog.text
    assert marker not in str(error) + repr(error) + "".join(traceback.format_exception(error))
    assert statements == [] and not i3a_db.new and not i3a_db.dirty
    assert rows(i3a_db, principal) == ([], [])
