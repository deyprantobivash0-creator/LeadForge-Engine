"""Identity provenance and tenant seams; only disposable test databases."""

from dataclasses import replace
import json
import logging

import pytest
from pydantic import ValidationError

from backend.core.exceptions import LeadForgeException
from backend.core.logger import JsonFormatter
from backend.database.transactions import service_transaction
from backend.schemas.execution_principal import ActorReference, ExecutionPrincipal, PrincipalType
from backend.services.lead_lifecycle_service import LeadLifecycleService
from backend.services.lead_service import LeadService
from tests.test_service_transactions import command_db, persisted_leads


@pytest.mark.parametrize("factory,actor", [
    (ExecutionPrincipal.for_user, 7), (ExecutionPrincipal.for_system, "maintenance"),
    (ExecutionPrincipal.for_agent, "research"), (ExecutionPrincipal.for_workflow, "run-1"),
    (ExecutionPrincipal.for_integration, "connection-1"),
])
def test_valid_principals_round_trip_and_immutability(factory, actor):
    principal = factory(actor, 1, correlation_id="chain-1")
    assert principal.actor_id == actor and principal.organization_id == 1
    assert ExecutionPrincipal.from_json(principal.to_json()) == principal
    assert principal.to_json() == principal.to_json()
    assert json.loads(principal.to_json())["correlation_id"] == "chain-1"
    with pytest.raises(ValidationError):
        principal.organization_id = 2


@pytest.mark.parametrize("values", [
    {"principal_type": "USER", "organization_id": 1},
    {"principal_type": "USER", "actor_id": 1},
    {"principal_type": "USER", "actor_id": "1", "organization_id": 1},
    {"principal_type": "USER", "actor_id": True, "organization_id": 1},
    {"principal_type": "USER", "actor_id": 0, "organization_id": 1},
    {"principal_type": "USER", "actor_id": 1, "organization_id": True},
    {"principal_type": "USER", "actor_id": 1, "organization_id": "1"},
    {"principal_type": "SUPERUSER", "actor_id": 1, "organization_id": 1},
    {"principal_type": "SYSTEM", "actor_id": 1, "organization_id": 1},
    {"principal_type": "SYSTEM", "actor_id": "job"},
    {"principal_type": "SYSTEM", "actor_id": "job", "organization_id": 0},
    {"principal_type": "AGENT", "actor_id": "research", "organization_id": 1},
    {"principal_type": "WORKFLOW", "actor_id": "run", "organization_id": 1},
    {"principal_type": "INTEGRATION", "actor_id": "connection", "organization_id": 1},
    {"principal_type": "AGENT", "actor_id": "research", "agent_id": "other", "organization_id": 1},
    {"principal_type": "USER", "actor_id": 1, "organization_id": 1, "agent_id": "spoof"},
])
def test_invalid_identity_and_provenance_rejected(values):
    with pytest.raises(ValidationError):
        ExecutionPrincipal.model_validate(values)


@pytest.mark.parametrize("correlation", ["", "x" * 65, "line\nbreak", "trailing\n", "../unsafe", "email@example.com"])
def test_unsafe_correlation_rejected(correlation):
    with pytest.raises(ValidationError):
        ExecutionPrincipal.for_user(1, 1, correlation_id=correlation)


def test_generated_correlation_is_unique_and_preserved():
    one, two = ExecutionPrincipal.for_user(1, 1), ExecutionPrincipal.for_user(1, 1)
    assert one.correlation_id != two.correlation_id
    assert len(one.correlation_id) == 32
    child = ExecutionPrincipal.for_workflow("child-run", 1, correlation_id=one.correlation_id)
    assert child.correlation_id == one.correlation_id


def test_delegation_is_bounded_typed_provenance():
    authority = ActorReference(principal_type=PrincipalType.USER, actor_id=9)
    workflow = ExecutionPrincipal.for_workflow("run-1", 1, delegated_by=authority)
    agent = ExecutionPrincipal.for_agent(
        "research", 1, workflow_run_id=workflow.workflow_run_id,
        correlation_id=workflow.correlation_id,
        delegated_by=ActorReference(principal_type=workflow.principal_type, actor_id=workflow.actor_id),
    )
    assert agent.actor_id == "research" and agent.delegated_by.actor_id == "run-1"
    assert ExecutionPrincipal.from_json(agent.to_json()) == agent
    with pytest.raises(ValidationError):
        authority.actor_id = 10
    with pytest.raises(ValidationError):
        ActorReference.model_validate({"principal_type": "USER", "actor_id": 9,
                                       "delegated_by": {"principal_type": "USER", "actor_id": 10}})


@pytest.mark.parametrize("extra", ["password", "session_id", "session_token", "cookie", "api_key", "permissions"])
def test_serialization_rejects_transport_secrets_and_permission_claims(extra):
    values = json.loads(ExecutionPrincipal.for_user(1, 1).to_json())
    values[extra] = "synthetic-disallowed-field"
    with pytest.raises(ValidationError):
        ExecutionPrincipal.from_json(json.dumps(values))


def test_worker_calls_services_without_http_and_nested_identity_is_preserved(command_db, caplog):
    principal = ExecutionPrincipal.for_workflow("run-1", 1, correlation_id="worker-chain")
    with caplog.at_level(logging.INFO):
        with service_transaction(command_db):
            lead = LeadService(command_db).create_lead_for_principal(
                principal, organization_id=1, company="Synthetic", email="worker@example.com", source="test")
            LeadLifecycleService(command_db).update_lifecycle_for_principal(
                principal, organization_id=1, lead_id=lead.id, status="Contacted")
    assert persisted_leads(command_db) == [("worker@example.com", "Contacted")]
    records = [r for r in caplog.records if getattr(r, "event", "").startswith("execution.lead.")]
    assert len(records) == 2
    for record in records:
        value = json.loads(JsonFormatter().format(record))
        assert value["principal_type"] == "WORKFLOW"
        assert value["actor_id"] == "run-1" and value["organization_id"] == 1
        assert value["correlation_id"] == "worker-chain"
        assert "worker@example.com" not in JsonFormatter().format(record)


@pytest.mark.parametrize("factory,actor", [(ExecutionPrincipal.for_user, 1),
                                         (ExecutionPrincipal.for_system, "maintenance")])
def test_principal_domain_tenant_mismatch_rolls_back_outer_command(command_db, factory, actor):
    principal = factory(actor, 1)
    with pytest.raises(LeadForgeException) as caught:
        with service_transaction(command_db):
            lead = LeadService(command_db).create_lead_for_principal(
                principal, organization_id=1, company="Synthetic", email="one@example.com", source="test")
            LeadLifecycleService(command_db).update_lifecycle_for_principal(
                principal, organization_id=2, lead_id=lead.id, status="Contacted")
    assert caught.value.error_code == "EXECUTION_TENANT_MISMATCH"
    assert persisted_leads(command_db) == []


def test_system_is_not_a_cross_tenant_bypass(command_db):
    foreign = LeadService(command_db).create_lead("Foreign", "foreign@example.com", "test", 2)
    principal = ExecutionPrincipal.for_system("maintenance", 1)
    assert LeadLifecycleService(command_db).update_lifecycle_for_principal(
        principal, organization_id=1, lead_id=foreign.id, status="Contacted") is None
    assert persisted_leads(command_db) == [("foreign@example.com", "New")]


def test_service_rejects_raw_serialized_context_and_invalid_model_copy(command_db):
    service = LeadService(command_db)
    valid = ExecutionPrincipal.for_user(1, 1)
    for invalid in (json.loads(valid.to_json()), valid.model_copy(update={"organization_id": None})):
        with pytest.raises(LeadForgeException):
            service.create_lead_for_principal(invalid, organization_id=1, company="Synthetic",
                                               email="invalid@example.com", source="test")
    assert persisted_leads(command_db) == []


def test_http_adapter_binds_authenticated_user_membership_and_request_id(tenant_workspace, monkeypatch):
    from tests.api.test_tenant_leads import headers
    seen = []
    original = LeadService.create_lead_for_principal

    def capture(self, principal, **kwargs):
        seen.append(principal)
        return original(self, principal, **kwargs)

    monkeypatch.setattr(LeadService, "create_lead_for_principal", capture)
    request_headers = {**headers(tenant_workspace, "a", csrf=True), "X-Request-ID": "http-chain",
                       "X-Principal-Type": "SYSTEM", "X-Actor-ID": "spoof"}
    client = tenant_workspace["clients"]["a"]
    response = client.post("/api/leads/", headers=request_headers,
                           json={"company": "Synthetic", "email": "http@example.com", "source": "test"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == seen[0].correlation_id == "http-chain"
    assert seen[0].principal_type == PrincipalType.USER
    assert seen[0].actor_id == tenant_workspace["ids"]["users"]["a"]
    assert seen[0].organization_id == tenant_workspace["ids"]["organizations"]["a"]
    # A raw principal body is not an identity ingress.
    response = client.post("/api/leads/", headers=request_headers,
                           json={"company": "Synthetic", "email": "spoof@example.com", "source": "test",
                                 "principal": json.loads(seen[0].to_json())})
    assert response.status_code == 422 and len(seen) == 1
    assert client.post("/api/leads/", headers=headers(tenant_workspace, "b", client_key="a", csrf=True),
                       json={"company": "Synthetic", "email": "denied@example.com", "source": "test"}).status_code == 403
    assert len(seen) == 1


def test_adapter_rejects_forged_context_and_live_membership_revocation(tenant_workspace):
    from backend.api.dependencies.execution_principal import principal_from_authorized_context
    from backend.database.session import SessionLocal
    from backend.models import User
    from backend.services.organization_authorization_service import (
        OrganizationAuthorizationService, OrganizationAccessDenied,
    )

    ids = tenant_workspace["ids"]
    with SessionLocal() as db:
        a, b = db.get(User, ids["users"]["a"]), db.get(User, ids["users"]["b"])
        service = OrganizationAuthorizationService(db)
        ca = service.authorize(a, ids["organizations"]["a"])
        cb = service.authorize(b, ids["organizations"]["b"])
        for context in (cb, replace(ca, organization=cb.organization), replace(ca, user=b)):
            with pytest.raises(OrganizationAccessDenied):
                principal_from_authorized_context(context, authenticated_user=a, db=db, correlation_id="safe")
        ca.membership.is_active = False
        db.commit()
        with pytest.raises(OrganizationAccessDenied):
            principal_from_authorized_context(ca, authenticated_user=a, db=db, correlation_id="safe")
