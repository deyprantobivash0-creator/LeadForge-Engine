"""Structural authority and service gates on disposable SQLite databases."""

from dataclasses import FrozenInstanceError
import json

import pytest
from sqlalchemy import select

from backend.core.exceptions import LeadForgeException
from backend.database.transactions import service_transaction
from backend.models import User, OrganizationMembership
from backend.schemas.action_permission import (
    ActionPermission as P, HumanAuthorizationContext, MachineAuthorizationContext,
    PermissionResult as R, PermissionReason as Reason, ROLE_PERMISSIONS, delegate_capabilities,
)
from backend.schemas.execution_principal import ActorReference, ExecutionPrincipal, PrincipalType
from backend.services.action_permission_service import ActionPermissionService
from backend.services.permission_evaluator import evaluate_permission
from backend.services.lead_service import LeadService
from backend.services.lead_lifecycle_service import LeadLifecycleService
from tests.test_service_transactions import command_db, persisted_leads, create


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
@pytest.mark.parametrize("permission", list(P))
def test_existing_roles_preserve_current_actions(role, permission):
    principal = ExecutionPrincipal.for_user(1, 1)
    context = HumanAuthorizationContext(principal, role, ROLE_PERMISSIONS[role])
    decision = evaluate_permission(principal, context, permission, 1)
    assert decision.result == R.PERMIT and decision.reason_code == Reason.PERMITTED_BY_ROLE
    assert json.loads(json.dumps(decision.to_dict())) == decision.to_dict()


def test_known_role_cannot_exceed_trusted_narrowed_scope_and_unknown_role_denies():
    principal = ExecutionPrincipal.for_user(1, 1)
    limited = HumanAuthorizationContext(principal, "member", frozenset({P.LEAD_READ}))
    assert evaluate_permission(principal, limited, P.LEAD_CREATE, 1).result == R.DENY
    unknown = HumanAuthorizationContext(principal, "superuser", frozenset({P.LEAD_CREATE}))
    assert evaluate_permission(principal, unknown, P.LEAD_CREATE, 1).reason_code == Reason.DENIED_UNKNOWN_ROLE


@pytest.mark.parametrize("factory,actor", [
    (ExecutionPrincipal.for_system, "maintenance"), (ExecutionPrincipal.for_agent, "research"),
    (ExecutionPrincipal.for_workflow, "run-1"), (ExecutionPrincipal.for_integration, "connection-1"),
])
def test_all_machine_types_need_explicit_capability(factory, actor):
    principal = factory(actor, 1)
    assert evaluate_permission(principal, None, P.LEAD_CREATE, 1).result == R.DENY
    empty = MachineAuthorizationContext(principal, frozenset())
    assert evaluate_permission(principal, empty, P.LEAD_CREATE, 1).reason_code == Reason.DENIED_PERMISSION_NOT_GRANTED
    granted = MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))
    assert evaluate_permission(principal, granted, P.LEAD_CREATE, 1).reason_code == Reason.PERMITTED_BY_CAPABILITY
    assert evaluate_permission(principal, granted, P.LEAD_LIFECYCLE_CHANGE, 1).result == R.DENY
    assert evaluate_permission(principal, granted, P.LEAD_CREATE, 2).reason_code == Reason.DENIED_TENANT_MISMATCH


def test_context_is_bound_to_full_principal_and_target_tenant():
    principal = ExecutionPrincipal.for_workflow("run-1", 1, correlation_id="one")
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))
    other_run = ExecutionPrincipal.for_workflow("run-1", 1, correlation_id="two")
    assert evaluate_permission(other_run, context, P.LEAD_CREATE, 1).reason_code == Reason.DENIED_PRINCIPAL_MISMATCH
    user = ExecutionPrincipal.for_user(1, 1)
    human = HumanAuthorizationContext(user, "owner", ROLE_PERMISSIONS["owner"])
    assert evaluate_permission(user, human, P.LEAD_CREATE, 2).result == R.DENY
    foreign_context = MachineAuthorizationContext(ExecutionPrincipal.for_workflow("run-1", 2),
                                                  frozenset({P.LEAD_CREATE}))
    assert evaluate_permission(principal, foreign_context, P.LEAD_CREATE, 1).result == R.DENY


@pytest.mark.parametrize("permission", [None, "lead.create", "execute_everything", "outreach.send"])
def test_untyped_or_unknown_permission_denies(permission):
    principal = ExecutionPrincipal.for_system("job", 1)
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))
    assert evaluate_permission(principal, context, permission, 1).reason_code == Reason.DENIED_UNKNOWN_PERMISSION


def test_capability_context_is_immutable_typed_and_raw_json_is_not_trusted():
    principal = ExecutionPrincipal.for_workflow("run-1", 1)
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))
    with pytest.raises(FrozenInstanceError):
        context.capabilities = frozenset({P.LEAD_IMPORT})
    for malformed in ({P.LEAD_CREATE}, frozenset({"lead.create"}), frozenset({"*"})):
        with pytest.raises(ValueError):
            MachineAuthorizationContext(principal, malformed)
    assert evaluate_permission(principal, context.to_dict(), P.LEAD_CREATE, 1).result == R.DENY
    with pytest.raises(ValueError):
        ExecutionPrincipal.from_json(json.dumps({**principal.model_dump(mode="json"),
                                                "capabilities": ["lead.create"]}))


def test_delegation_narrows_without_escalation():
    user = ExecutionPrincipal.for_user(1, 1, correlation_id="chain")
    parent = HumanAuthorizationContext(user, "member", frozenset({P.LEAD_CREATE, P.LEAD_READ}))
    workflow = ExecutionPrincipal.for_workflow("run-1", 1, correlation_id="chain",
                   delegated_by=ActorReference(principal_type=PrincipalType.USER, actor_id=1))
    child = delegate_capabilities(parent, workflow, frozenset({P.LEAD_CREATE}))
    agent = ExecutionPrincipal.for_agent("research", 1, correlation_id="chain", workflow_run_id="run-1",
               delegated_by=ActorReference(principal_type=PrincipalType.WORKFLOW, actor_id="run-1"))
    narrowed = delegate_capabilities(child, agent, frozenset())
    assert not narrowed.capabilities
    with pytest.raises(ValueError):
        delegate_capabilities(parent, workflow, frozenset({P.LEAD_IMPORT}))
    with pytest.raises(ValueError):
        delegate_capabilities(child, agent, frozenset({P.LEAD_READ}))
    with pytest.raises(ValueError):
        delegate_capabilities(parent, workflow.model_copy(update={"organization_id": 2}), frozenset())
    with pytest.raises(ValueError):
        delegate_capabilities(parent, workflow.model_copy(update={"delegated_by": None}), frozenset())


def test_evaluator_is_deterministic_and_context_only():
    principal = ExecutionPrincipal.for_agent("research", 1)
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))
    results = [evaluate_permission(principal, context, P.LEAD_CREATE, 1).to_dict() for _ in range(10)]
    assert all(value == results[0] for value in results)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_service_user_authority_is_from_live_membership(command_db, role):
    db = command_db
    db.add(User(id=1, email="human@example.com", password_hash="unused-test-hash"))
    db.flush()
    membership = OrganizationMembership(user_id=1, organization_id=1, role=role)
    db.add(membership)
    db.commit()
    principal = ExecutionPrincipal.for_user(1, 1)
    lead = LeadService(db).create_lead(principal, company="Synthetic",
                        email="one@example.com", source="test", organization_id=1)
    assert LeadLifecycleService(db).update_lifecycle(
        principal, lead_id=lead.id, organization_id=1, status="Contacted").status == "Contacted"
    membership.is_active = False
    db.commit()
    with pytest.raises(LeadForgeException) as caught:
        LeadService(db).create_lead(principal, company="Synthetic",
                        email="two@example.com", source="test", organization_id=1)
    assert caught.value.error_code == "ACTION_PERMISSION_DENIED"
    assert persisted_leads(db) == [("one@example.com", "Contacted")]


@pytest.mark.parametrize("actor_type", ["system", "agent", "workflow", "integration"])
def test_machine_service_enforcement_without_http(command_db, actor_type):
    principal = getattr(ExecutionPrincipal, "for_" + actor_type)("actor-1", 1)
    service = LeadService(command_db)
    with pytest.raises(LeadForgeException):
        service.create_lead(principal, company="Synthetic", email="denied@example.com",
                                          source="test", organization_id=1)
    assert persisted_leads(command_db) == []
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))
    lead = service.create_lead(principal, company="Synthetic", email="allowed@example.com",
                                          source="test", organization_id=1, machine_context=context)
    with pytest.raises(LeadForgeException):
        LeadLifecycleService(command_db).update_lifecycle(
            principal, lead_id=lead.id, organization_id=1, status="Contacted", machine_context=context)
    assert persisted_leads(command_db) == [("allowed@example.com", "New")]


def test_denied_nested_command_cannot_commit_early_write(command_db):
    principal = ExecutionPrincipal.for_workflow("run-1", 1)
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_CREATE}))
    with pytest.raises(LeadForgeException):
        with service_transaction(command_db):
            lead = LeadService(command_db).create_lead(principal, company="Synthetic",
                          email="rolled-back@example.com", source="test", organization_id=1, machine_context=context)
            LeadLifecycleService(command_db).update_lifecycle(
                principal, lead_id=lead.id, organization_id=1, status="Contacted", machine_context=context)
    assert persisted_leads(command_db) == []


def test_capability_does_not_bypass_repository_foreign_resource_filter(command_db):
    lead = create(command_db, "foreign@example.com", organization_id=2)
    principal = ExecutionPrincipal.for_system("job", 1)
    context = MachineAuthorizationContext(principal, frozenset({P.LEAD_LIFECYCLE_CHANGE}))
    assert LeadLifecycleService(command_db).update_lifecycle(
        principal, lead_id=lead.id, organization_id=1, status="Contacted", machine_context=context) is None
    assert persisted_leads(command_db) == [("foreign@example.com", "New")]


def test_stale_orm_membership_role_is_not_service_authority(tenant_workspace):
    from backend.database.session import SessionLocal
    ids = tenant_workspace["ids"]
    principal = ExecutionPrincipal.for_user(ids["users"]["a"], ids["organizations"]["a"])
    with SessionLocal() as reader, SessionLocal() as writer:
        cached = reader.scalar(select(OrganizationMembership).where(
            OrganizationMembership.user_id == principal.actor_id,
            OrganizationMembership.organization_id == principal.organization_id))
        assert cached.is_active
        current = writer.get(OrganizationMembership, cached.id)
        current.is_active = False
        writer.commit()
        assert cached.is_active  # deliberately stale identity map
        with pytest.raises(LeadForgeException):
            LeadService(reader).create_lead(principal, company="Synthetic",
                        email="stale@example.com", source="test", organization_id=principal.organization_id)


def test_user_cannot_supply_a_forged_authority_context(tenant_workspace):
    from backend.database.session import SessionLocal
    ids = tenant_workspace["ids"]
    principal = ExecutionPrincipal.for_user(ids["users"]["a"], ids["organizations"]["b"])
    forged = HumanAuthorizationContext(principal, "owner", ROLE_PERMISSIONS["owner"])
    with SessionLocal() as db:
        with pytest.raises(LeadForgeException):
            LeadService(db).create_lead(principal, company="Synthetic",
                       email="forged@example.com", source="test", organization_id=principal.organization_id,
                       machine_context=forged)


def test_http_role_capability_injection_and_import_permission_gate(tenant_workspace, monkeypatch):
    from backend.services.lead_import_service import LeadImportService
    from backend.repositories.permission_repository import PermissionRepository
    from tests.api.test_tenant_leads import headers
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    h = {**headers(workspace, "a", csrf=True), "X-Role": "owner", "X-Capabilities": "*"}
    csv = b"company,email,source\nOne,import-permission@example.com,test\n"
    preview = client.post("/api/imports/leads/preview", headers={**h, "Content-Type": "text/csv"},
                          content=csv).json()
    # Simulate unmapped authoritative role without altering membership schema.
    monkeypatch.setattr(PermissionRepository, "active_role", lambda *args: "unmapped")
    assert client.post("/api/leads/", headers=h,
                       json={"company": "Synthetic", "email": "denied@example.com", "source": "test"}).status_code == 403
    lead_id = workspace["ids"]["leads"]["a"]
    assert client.patch(f"/api/leads/{lead_id}/lifecycle", headers=h,
                        json={"status": "Contacted"}).status_code == 403
    invoked = []
    monkeypatch.setattr(LeadImportService, "_confirm", lambda *args: invoked.append(True))
    result = client.post("/api/imports/leads/confirm", content=csv,
                        headers={**h, "Content-Type": "text/csv", "X-Import-Preview-Token": preview["token"]})
    assert result.status_code == 403 and not invoked
    assert client.post("/api/leads/", headers=h,
                      json={"company": "Synthetic", "email": "injected@example.com", "source": "test",
                            "capabilities": ["lead.create"]}).status_code == 422


@pytest.mark.parametrize("command", ["create", "lifecycle", "import"])
@pytest.mark.parametrize("authority", ["missing", "none", "machine_without_scope"])
def test_canonical_direct_commands_fail_closed(command_db, command, authority):
    from backend.services.lead_import_service import LeadImportService
    from tests.test_service_transactions import CSV, import_command
    db = command_db
    principal = ExecutionPrincipal.for_system("unscoped", 1)
    args = {} if authority == "missing" else {"principal": None if authority == "none" else principal}
    expected = TypeError if authority == "missing" else LeadForgeException
    if command == "create":
        call = lambda: LeadService(db).create_lead(**args, company="Synthetic",
                     email="direct-denied@example.com", source="test", organization_id=1)
        before = []
    elif command == "lifecycle":
        lead_id = create(db).id
        before = persisted_leads(db)
        call = lambda: LeadLifecycleService(db).update_lifecycle(**args, lead_id=lead_id,
                      organization_id=1, status="Contacted")
    else:
        service, token, key = import_command(db)
        before = []
        call = lambda: service.confirm(**args, content=CSV, token=token,
                                       organization_id=1, user_id=1, session_key=key)
        if authority == "machine_without_scope":
            from backend.services.lead_import_service import ImportValidationError
            expected = ImportValidationError  # Browser confirmation never accepts machines.
    with pytest.raises(expected):
        call()
    assert persisted_leads(db) == before


@pytest.mark.parametrize("service_class,obsolete", [
    (LeadService, "create_lead_for_principal"),
    (LeadLifecycleService, "update_lifecycle_for_principal"),
    (LeadLifecycleService, "update_status"),
])
def test_obsolete_public_mutation_aliases_are_unavailable(command_db, service_class, obsolete):
    with pytest.raises(AttributeError):
        getattr(service_class(command_db), obsolete)
    assert persisted_leads(command_db) == []


def test_old_integer_only_command_signatures_cannot_mutate(command_db):
    from backend.services.lead_import_service import LeadImportService
    with pytest.raises(TypeError):
        LeadService(command_db).create_lead("Synthetic", "old@example.com", "test", 1)
    lead_id = create(command_db).id
    with pytest.raises(TypeError):
        LeadLifecycleService(command_db).update_lifecycle(lead_id, 1, status="Contacted")
    with pytest.raises(TypeError):
        LeadImportService(command_db).confirm(b"csv", "token", 1, 1, "synthetic")
    with pytest.raises(AttributeError):
        getattr(LeadImportService(command_db), "confirm_for_principal")
    assert persisted_leads(command_db) == [("new@example.com", "New")]


@pytest.mark.parametrize("grants", [frozenset({P.LEAD_IMPORT}), frozenset({P.LEAD_CREATE}),
                                   frozenset({P.LEAD_IMPORT, P.LEAD_CREATE})])
def test_direct_import_requires_both_permissions_before_any_row(command_db, monkeypatch, grants):
    import backend.services.action_permission_service as authority_service
    import backend.services.permission_evaluator as evaluator
    from tests.test_service_transactions import CSV, import_command, commit_spy
    service, token, key = import_command(command_db)
    # Narrow trusted server policy, never a caller-supplied human grant.
    policy = {"member": grants}
    monkeypatch.setattr(authority_service, "ROLE_PERMISSIONS", policy)
    monkeypatch.setattr(evaluator, "ROLE_PERMISSIONS", policy)
    calls = commit_spy(command_db, monkeypatch)
    principal = ExecutionPrincipal.for_user(1, 1)
    if len(grants) == 2:
        assert service.confirm(principal, CSV, token, 1, 1, key).imported == 2
        assert len(persisted_leads(command_db)) == 2 and calls == ["commit"]
    else:
        monkeypatch.setattr(service.repository, "add", lambda *args: pytest.fail("Denied import wrote a row"))
        with pytest.raises(LeadForgeException) as caught:
            service.confirm(principal, CSV, token, 1, 1, key)
        assert caught.value.error_code == "ACTION_PERMISSION_DENIED"
        assert persisted_leads(command_db) == [] and calls == []


def test_private_mutation_helpers_join_the_owning_transaction(command_db, monkeypatch):
    from tests.test_service_transactions import commit_spy
    calls = commit_spy(command_db, monkeypatch)
    # Trusted implementation details, deliberately tested within an owning scope.
    with service_transaction(command_db):
        lead = LeadService(command_db)._create_lead_internal("Synthetic", "helper@example.com", "test", 1)
        LeadLifecycleService(command_db)._apply_lifecycle_change(lead.id, 1, status="Contacted")
        assert calls == []
    assert calls == ["commit"]
    assert persisted_leads(command_db) == [("helper@example.com", "Contacted")]
