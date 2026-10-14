"""E05-I2 closed construction, trust boundaries and semantic security tests."""

from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import ast
import json
from pathlib import Path
import traceback
import warnings
from uuid import UUID

import pytest

from backend.schemas.action_permission import (
    ActionPermission as P, HumanAuthorizationContext, MachineAuthorizationContext,
    PermissionDecision, PermissionReason as R, PermissionResult as D, ROLE_PERMISSIONS,
)
from backend.schemas.execution_principal import ActorReference, ExecutionPrincipal, PrincipalType
from backend.schemas.lead_contract import LeadLifecycle
from backend.schemas.audit_event import (
    AuditChangedField, AuditEvidenceItem, AuditEventDraft, AuditEventType as E, AuditOutcome,
    AuditReason, AuditLeadTarget, AuditValidationError, EmptyAuditDetails, ImportAuditDetails,
    LifecycleAuditDetails, audit_persistence_values, canonical_audit_json,
    validate_authorization_evidence, validate_details,
    APPROVED_DECISION_REASON_COMBINATIONS,
)
from backend.services.audit_event_builder import AuditEventBuilder as B, capture_authorization_receipt


NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


def user(org=1, actor=7, correlation="audit-test"):
    return ExecutionPrincipal.for_user(actor, org, correlation_id=correlation)


def receipt(principal, permission=P.LEAD_CREATE, result=D.PERMIT, reason=None, role="member"):
    human = principal.principal_type == PrincipalType.USER
    context = (HumanAuthorizationContext(principal, role, ROLE_PERMISSIONS.get(role, frozenset()))
               if human else MachineAuthorizationContext(principal, frozenset(P)))
    reason = reason or ((R.PERMITTED_BY_ROLE if human else R.PERMITTED_BY_CAPABILITY)
                        if result == D.PERMIT else R.DENIED_PERMISSION_NOT_GRANTED)
    decision = PermissionDecision(result, permission, principal.principal_type, reason)
    return capture_authorization_receipt(principal, decision, context)


def completed(principal=None):
    principal = principal or user()
    return B.create_completed(principal, target=AuditLeadTarget(principal.organization_id, 42),
                              authorization=receipt(principal), occurred_at=NOW)


def values(draft):
    return audit_persistence_values(draft, recorded_at=NOW + timedelta(seconds=1))


def evidence(permission=P.LEAD_CREATE, decision=D.PERMIT, reason=R.PERMITTED_BY_ROLE):
    return dict(permission=permission.value, decision=decision.value, reason_code=reason.value)


@pytest.mark.parametrize("permissions", [(), (P.LEAD_CREATE,), (P.LEAD_IMPORT, P.LEAD_CREATE), tuple(P)])
def test_evidence_container_zero_one_two_eight(permissions):
    result = validate_authorization_evidence([evidence(p) for p in permissions])
    assert len(result) == len(permissions)
    assert all(type(item) is AuditEvidenceItem for item in result)
    assert len(canonical_audit_json([item.as_json() for item in result]).encode("utf-8")) <= 2048


@pytest.mark.parametrize("field", ["permission", "decision", "reason_code"])
def test_evidence_missing_keys(field):
    item = evidence(); del item[field]
    with pytest.raises(AuditValidationError):
        validate_authorization_evidence([item])


@pytest.mark.parametrize("bad", [None, {}, "[]", (), [None], ["PERMIT"], [[evidence()]],
    [{**evidence(), "token": "synthetic-forbidden-value"}],
    [{**evidence(), "permission": "unknown"}], [{**evidence(), "decision": "unknown"}],
    [{**evidence(), "reason_code": "unknown"}], [{**evidence(), "permission": None}],
    [{**evidence(), "decision": 1}], [{**evidence(), "reason_code": False}],
    [evidence()] * 9, [evidence(), evidence()],
    [evidence(decision=D.DENY)], [evidence(reason=R.DENIED_PERMISSION_NOT_GRANTED)]])
def test_invalid_evidence_rejected(bad):
    with pytest.raises(AuditValidationError):
        validate_authorization_evidence(bad)


@pytest.mark.parametrize("reason", [R.DENIED_PERMISSION_NOT_GRANTED, R.DENIED_INVALID_CONTEXT,
    R.DENIED_TENANT_MISMATCH, R.DENIED_PRINCIPAL_MISMATCH,
    R.DENIED_UNKNOWN_ROLE, R.DENIED_UNKNOWN_PERMISSION])
def test_all_existing_e04_denial_reasons_are_recognized(reason):
    item = validate_authorization_evidence([evidence(decision=D.DENY, reason=reason)])[0]
    assert item.reason_code is reason


# Explicit reviewed expectation, independent of runtime enum completeness.
REVIEWED_DECISION_REASON_PAIRS = frozenset({
    (D.PERMIT, R.PERMITTED_BY_ROLE),
    (D.PERMIT, R.PERMITTED_BY_CAPABILITY),
    (D.DENY, R.DENIED_PERMISSION_NOT_GRANTED),
    (D.DENY, R.DENIED_INVALID_CONTEXT),
    (D.DENY, R.DENIED_TENANT_MISMATCH),
    (D.DENY, R.DENIED_PRINCIPAL_MISMATCH),
    (D.DENY, R.DENIED_UNKNOWN_ROLE),
    (D.DENY, R.DENIED_UNKNOWN_PERMISSION),
})


def test_closed_reason_matrix_exactly_matches_reviewed_pairs():
    assert APPROVED_DECISION_REASON_COMBINATIONS == REVIEWED_DECISION_REASON_PAIRS


def test_e04_reason_and_decision_taxonomy_drift_requires_audit_review():
    assert set(R) == {reason for _, reason in REVIEWED_DECISION_REASON_PAIRS}
    assert set(D) == {D.PERMIT, D.DENY}


@pytest.mark.parametrize("permission", list(P))
@pytest.mark.parametrize("decision", list(D))
@pytest.mark.parametrize("reason", list(R))
def test_current_decision_reason_matrix_for_every_permission(permission, decision, reason):
    # Iteration exercises all current candidates; approval is ONLY the explicit
    # reviewed set. Future enum additions cannot silently become expected-valid.
    if (decision, reason) in REVIEWED_DECISION_REASON_PAIRS:
        item = AuditEvidenceItem(permission, decision, reason)
        assert validate_authorization_evidence([item.as_json()]) == (item,)
    else:
        with pytest.raises(AuditValidationError, match="Unapproved"):
            AuditEvidenceItem(permission, decision, reason)
        with pytest.raises(AuditValidationError, match="Unapproved"):
            validate_authorization_evidence([evidence(permission, decision, reason)])


@pytest.mark.parametrize("decision,reason", sorted(REVIEWED_DECISION_REASON_PAIRS))
def test_matrix_pairs_are_actually_emitted_by_current_e04(decision, reason):
    from backend.services.permission_evaluator import evaluate_permission
    p = user(); context = HumanAuthorizationContext(p, "member", frozenset(P))
    permission = P.LEAD_CREATE; target = 1
    if reason == R.PERMITTED_BY_CAPABILITY:
        p = ExecutionPrincipal.for_system("matrix-system", 1)
        context = MachineAuthorizationContext(p, frozenset(P))
    elif reason == R.DENIED_PERMISSION_NOT_GRANTED:
        context = HumanAuthorizationContext(p, "member", frozenset())
    elif reason == R.DENIED_INVALID_CONTEXT:
        context = None
    elif reason == R.DENIED_TENANT_MISMATCH:
        target = 2
    elif reason == R.DENIED_PRINCIPAL_MISMATCH:
        context = HumanAuthorizationContext(user(actor=8), "member", frozenset(P))
    elif reason == R.DENIED_UNKNOWN_ROLE:
        context = HumanAuthorizationContext(p, "unmapped", frozenset(P))
    elif reason == R.DENIED_UNKNOWN_PERMISSION:
        permission = "unknown"
    actual = evaluate_permission(p, context, permission, target)
    assert (actual.result, actual.reason_code) == (decision, reason)
    # The generic pair is approved; the existing typed permission/principal
    # requirements still exclude unknown-permission/invalid-identity receipts.
    assert AuditEvidenceItem(P.LEAD_CREATE, actual.result, actual.reason_code)


@pytest.mark.parametrize("decision", [D.PERMIT, D.DENY])
def test_future_typed_reason_rejected_by_unchanged_validator_in_isolation(decision):
    from backend.schemas import audit_event as module
    extended = StrEnum("ExtendedPermissionReason", {reason.name: reason.value for reason in R}
                       | {"FUTURE_REASON": "FUTURE_REASON"})
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if
             (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
              and t.id == "APPROVED_DECISION_REASON_COMBINATIONS" for t in node.targets))
             or (isinstance(node, ast.ClassDef) and node.name == "AuditEvidenceItem")]
    namespace = dict(dataclass=dataclass, ActionPermission=P, PermissionResult=D,
                     PermissionReason=extended, AuditValidationError=AuditValidationError)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<isolated audit validator>", "exec"), namespace)
    item_type = namespace["AuditEvidenceItem"]
    # Prove the isolated exact production validator accepts the genuine typed
    # extended enum for reviewed pairs. Future rejection cannot be a type error.
    for result, reason in REVIEWED_DECISION_REASON_PAIRS:
        assert item_type(P.LEAD_CREATE, result, extended[reason.name])
    assert type(extended.FUTURE_REASON) is namespace["PermissionReason"]
    with pytest.raises(AuditValidationError, match="Unapproved") as error:
        item_type(P.LEAD_CREATE, decision, extended.FUTURE_REASON)
    assert "FUTURE_REASON" not in str(error.value) and "FUTURE_REASON" not in repr(error.value)
    assert R is module.PermissionReason and "FUTURE_REASON" not in R.__members__


def test_unknown_raw_reason_is_rejected_separately_from_future_typed_reason():
    with pytest.raises(AuditValidationError):
        validate_authorization_evidence([{**evidence(), "reason_code": "FUTURE_REASON"}])
    with pytest.raises(AuditValidationError, match="Typed"):
        AuditEvidenceItem(P.LEAD_CREATE, D.DENY, "FUTURE_REASON")


def test_invalid_decision_reason_cannot_reach_repository_persistence():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.database.transactions import service_transaction
    from backend.repositories.audit_repository import AuditRepository
    # Simulate an incorrectly constructed internal value. Revalidation must
    # reject the pair before ORM insertion, regardless of a stale copied seal.
    bad = object.__new__(AuditEvidenceItem)
    for field, value in (("permission", P.LEAD_CREATE), ("decision", D.DENY), ("reason_code", R.PERMITTED_BY_ROLE)):
        object.__setattr__(bad, field, value)
    draft = completed()
    draft = replace(draft, receipts=(replace(draft.receipts[0], evidence=bad),))
    engine = create_engine("sqlite:///:memory:")
    try:
        with Session(engine) as db:
            with service_transaction(db):
                with pytest.raises(AuditValidationError, match="Unapproved"):
                    AuditRepository(db).append(draft)
                assert not db.new and not db.in_transaction()
    finally:
        engine.dispose()


@pytest.mark.parametrize("value", ["x" * 2046, "é" * 1023, "界" * 682])
def test_canonical_exact_utf8_byte_boundary(value):
    result = canonical_audit_json(value)
    assert len(result.encode("utf-8")) == 2048  # JSON quote bytes included
    assert json.loads(result) == value
    assert len(canonical_audit_json(value[:-1]).encode("utf-8")) < 2048
    with pytest.raises(AuditValidationError):
        canonical_audit_json(value + "x")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1.0, {"x": {"y": {}}},
    {i: "x" for i in range(2)}, {str(i): i for i in range(9)}, object(), (1,), "\ud800"])
def test_canonical_rejects_non_json_or_unsafe_structure(value):
    with pytest.raises(AuditValidationError):
        canonical_audit_json(value)


def test_canonical_is_stable_and_preserves_evidence_order():
    assert canonical_audit_json({"z": "é", "a": 1}) == '{"a":1,"z":"é"}'
    assert canonical_audit_json({"a": 1, "z": "é"}) == canonical_audit_json({"z": "é", "a": 1})
    items = [evidence(P.LEAD_IMPORT), evidence(P.LEAD_CREATE)]
    assert [item["permission"] for item in json.loads(canonical_audit_json(items))] == ["lead.import", "lead.create"]


@pytest.mark.parametrize("array", [False, True])
@pytest.mark.parametrize("multibyte", [False, True])
def test_object_and_array_byte_budgets_exact_below_above_without_truncation(array, multibyte):
    # Closed enum/details vocabularies cannot reach 2048 valid bytes. Probe the
    # shared byte-budget primitive separately without weakening those schemas.
    wrap = lambda s: [{"x": s}] if array else {"x": s}
    overhead = len(canonical_audit_json(wrap("")).encode("utf-8"))
    remaining = 2048 - overhead
    content = ("é" * (remaining // 2) + "x" * (remaining % 2)) if multibyte else "x" * remaining
    payload = wrap(content)
    serialized = canonical_audit_json(payload)
    assert len(serialized.encode("utf-8")) == 2048 and json.loads(serialized) == payload
    assert len(canonical_audit_json(wrap(content[:-1])).encode("utf-8")) < 2048
    with pytest.raises(AuditValidationError, match="byte limit"):
        canonical_audit_json(wrap(content + "x"))


@pytest.mark.parametrize("validator", [validate_authorization_evidence,
    lambda value: validate_details(value, E.COMPLETED, P.LEAD_CREATE)])
def test_oversized_malformed_payloads_fail_byte_budget_without_relaxing_domains(validator):
    payload = [{**evidence(), "reason_code": "é" * 1100}] if validator is validate_authorization_evidence else {"token": "é" * 1100}
    with pytest.raises(AuditValidationError, match="byte limit"):
        validator(payload)


def test_create_success_has_exact_evidence_target_and_no_content():
    v = values(completed())
    assert v["authorization_evidence"] == [evidence()]
    assert v["details"] == {} and v["target_id"] == "42" and v["target_type"] == "lead"
    assert v["event_type"] == E.COMPLETED.value and v["outcome"] == "SUCCEEDED"
    assert v["authority_role"] == "member" and v["schema_version"] == 1
    assert UUID(v["event_id"]).version == 4


@pytest.mark.parametrize("bad", [None, {}, [], PermissionDecision(D.PERMIT, P.LEAD_CREATE, PrincipalType.USER, R.PERMITTED_BY_ROLE)])
def test_create_rejects_untrusted_or_missing_receipt(bad):
    with pytest.raises(AuditValidationError):
        B.create_completed(user(), target=AuditLeadTarget(1, 42), authorization=bad, occurred_at=NOW)


@pytest.mark.parametrize("permission,result", [(P.LEAD_CREATE, D.DENY), (P.LEAD_IMPORT, D.PERMIT)])
def test_create_rejects_wrong_or_denied_permission(permission, result):
    p = user()
    with pytest.raises(AuditValidationError):
        B.create_completed(p, target=AuditLeadTarget(1, 42), authorization=receipt(p, permission, result), occurred_at=NOW)


def test_eight_structurally_valid_checks_cannot_become_create_success():
    p = user()
    with pytest.raises(AuditValidationError):
        values(replace(completed(p), receipts=tuple(receipt(p, permission) for permission in P)))


def lifecycle_details():
    return LifecycleAuditDetails(LeadLifecycle.NEW, LeadLifecycle.QUALIFIED, (AuditChangedField.STATUS,))


def test_lifecycle_and_noop_details():
    p = user(); r = receipt(p, P.LEAD_LIFECYCLE_CHANGE)
    d = B.lifecycle_completed(p, target=AuditLeadTarget(1, 42), authorization=r, details=lifecycle_details(), occurred_at=NOW)
    assert values(d)["details"] == {"status_before": "New", "status_after": "Qualified", "changed_fields": ["status"]}
    noop = LifecycleAuditDetails(LeadLifecycle.NEW, LeadLifecycle.NEW, ())
    assert values(B.lifecycle_completed(p, target=AuditLeadTarget(1, 42), authorization=r, details=noop, occurred_at=NOW))["details"]["changed_fields"] == []


@pytest.mark.parametrize("authorization", [None, P.LEAD_CREATE, D.DENY])
def test_lifecycle_requires_its_permit(authorization):
    p = user()
    r = None if authorization is None else receipt(p, authorization if type(authorization) is P else P.LEAD_LIFECYCLE_CHANGE,
                                                  authorization if type(authorization) is D else D.PERMIT)
    with pytest.raises(AuditValidationError):
        B.lifecycle_completed(p, target=AuditLeadTarget(1, 42), authorization=r, details=lifecycle_details(), occurred_at=NOW)


@pytest.mark.parametrize("reverse", [False, True])
def test_import_success_requires_both_permits_without_order_dependency(reverse):
    p = user(); rs = (receipt(p, P.LEAD_IMPORT), receipt(p, P.LEAD_CREATE))
    if reverse: rs = rs[::-1]
    draft = B.import_completed(p, authorization=rs, details=ImportAuditDetails(10, 7, 2, 1), occurred_at=NOW)
    v = values(draft)
    assert v["target_id"] == v["event_id"] and v["target_type"] == "lead_import"
    assert [e["permission"] for e in v["authorization_evidence"]] == [r.evidence.permission.value for r in rs]
    assert v["details"] == {"total": 10, "imported": 7, "duplicates": 2, "invalid": 1}


@pytest.mark.parametrize("permissions,results", [([], []), ([P.LEAD_IMPORT], [D.PERMIT]),
    ([P.LEAD_CREATE], [D.PERMIT]), ([P.LEAD_IMPORT, P.LEAD_IMPORT], [D.PERMIT, D.PERMIT]),
    ([P.LEAD_IMPORT, P.LEAD_CREATE], [D.PERMIT, D.DENY]),
    ([P.LEAD_CREATE, P.LEAD_IMPORT], [D.DENY, D.PERMIT]), (list(P), [D.PERMIT] * 8)])
def test_import_rejects_missing_duplicate_denied_extra_evidence(permissions, results):
    p = user(); rs = tuple(receipt(p, permission, result) for permission, result in zip(permissions, results))
    with pytest.raises(AuditValidationError):
        B.import_completed(p, authorization=rs, details=ImportAuditDetails(0, 0, 0, 0), occurred_at=NOW)


@pytest.mark.parametrize("action", [P.LEAD_CREATE, P.LEAD_LIFECYCLE_CHANGE, P.LEAD_IMPORT])
def test_first_check_denial(action):
    p = user(); r = receipt(p, action, D.DENY)
    v = values(B.permission_denied(p, action=action, authorization=(r,), organization_id=1, occurred_at=NOW))
    assert v["outcome"] == "DENIED" and v["reason_code"] == "ACTION_PERMISSION_DENIED"
    assert v["target_id"] is None and v["details"] == {}
    assert v["authorization_evidence"] == [r.evidence.as_json()]


def test_import_second_decisive_denial():
    p = user(); rs = (receipt(p, P.LEAD_IMPORT), receipt(p, P.LEAD_CREATE, D.DENY))
    v = values(B.permission_denied(p, action=P.LEAD_IMPORT, authorization=rs, organization_id=1, occurred_at=NOW))
    assert [e["decision"] for e in v["authorization_evidence"]] == ["PERMIT", "DENY"]


@pytest.mark.parametrize("checks", [[], [(P.LEAD_CREATE, D.DENY)], [(P.LEAD_IMPORT, D.PERMIT)],
    [(P.LEAD_CREATE, D.DENY), (P.LEAD_IMPORT, D.PERMIT)],
    [(P.LEAD_IMPORT, D.DENY), (P.LEAD_CREATE, D.PERMIT)],
    [(P.LEAD_IMPORT, D.PERMIT), (P.LEAD_CREATE, D.PERMIT)]])
def test_import_denial_rejects_unevaluated_or_out_of_order_checks(checks):
    p = user()
    with pytest.raises(AuditValidationError):
        B.permission_denied(p, action=P.LEAD_IMPORT, authorization=tuple(receipt(p, a, d) for a, d in checks),
                            organization_id=1, occurred_at=NOW)


def test_security_tenant_rejection_under_trusted_org_only():
    v = values(B.tenant_rejected(user(), action=P.LEAD_CREATE, requested_organization_id=999, occurred_at=NOW))
    assert v["organization_id"] == 1 and v["authorization_evidence"] == [] and v["authority_role"] is None
    assert v["event_type"] == "security.command.rejected" and v["outcome"] == "DENIED"
    assert v["target_id"] is None and v["details"] == {}
    assert "999" not in json.dumps({k: v[k] for k in ("details", "authorization_evidence", "target_id")})


@pytest.mark.parametrize("organization_id", [None, 0, -1, True, "2", 1])
def test_security_rejection_requires_actual_valid_mismatched_tenant(organization_id):
    with pytest.raises(AuditValidationError):
        B.tenant_rejected(user(), action=P.LEAD_CREATE, requested_organization_id=organization_id, occurred_at=NOW)


@pytest.mark.parametrize("action", [P.LEAD_READ, "lead.create", "anything", None])
def test_rejection_factories_cannot_expand_actions(action):
    with pytest.raises(AuditValidationError):
        B.tenant_rejected(user(), action=action, requested_organization_id=2, occurred_at=NOW)
    with pytest.raises(AuditValidationError):
        B.permission_denied(user(), action=action, authorization=(receipt(user(), P.LEAD_CREATE, D.DENY),), organization_id=1, occurred_at=NOW)


@pytest.mark.parametrize("event,action,valid", [
    (E.COMPLETED, P.LEAD_CREATE, {}),
    (E.COMPLETED, P.LEAD_LIFECYCLE_CHANGE, {"status_before": "New", "status_after": "Qualified", "changed_fields": ["status"]}),
    (E.COMPLETED, P.LEAD_IMPORT, {"total": 0, "imported": 0, "duplicates": 0, "invalid": 0}),
    (E.PERMISSION_DENIED, P.LEAD_CREATE, {}), (E.SECURITY_REJECTED, P.LEAD_CREATE, {})])
def test_details_closed_schema_for_every_pair(event, action, valid):
    assert validate_details(valid, event, action).as_json() == valid
    for key in ("email", "phone", "name", "notes", "prompt", "provider_response", "request_body",
                "password", "cookie", "session_token", "api_key", "authorization", "database_url", "csv_rows"):
        with pytest.raises(AuditValidationError):
            validate_details({**valid, key: "synthetic-forbidden-content"}, event, action)
    with pytest.raises(AuditValidationError):
        validate_details({"lead": {"customer": {"email": "synthetic@example.invalid"}}}, event, action)


@pytest.mark.parametrize("bad", [None, [], "{}", {"status_before": "unknown", "status_after": "New", "changed_fields": []},
    {"status_before": "New", "status_after": "Qualified", "changed_fields": []},
    {"status_before": "New", "status_after": "New", "changed_fields": ["status"]},
    {"status_before": "New", "status_after": "New", "changed_fields": ["notes", "notes"]},
    {"status_before": "New", "status_after": "New", "changed_fields": ["email"]},
    {"status_before": "New", "status_after": "New", "changed_fields": {"notes": "content"}}])
def test_lifecycle_details_reject_malformed_or_customer_values(bad):
    with pytest.raises(AuditValidationError):
        validate_details(bad, E.COMPLETED, P.LEAD_LIFECYCLE_CHANGE)


@pytest.mark.parametrize("bad", [dict(total=1, imported=0, duplicates=0, invalid=0),
    dict(total=1001, imported=1001, duplicates=0, invalid=0), dict(total=-1, imported=-1, duplicates=0, invalid=0),
    dict(total=True, imported=True, duplicates=0, invalid=0), dict(total=1.0, imported=1, duplicates=0, invalid=0),
    dict(total="1", imported=1, duplicates=0, invalid=0), dict(total=0),
    dict(total=0, imported=0, duplicates=0, invalid=0, operation_reference="secret")])
def test_import_counts_are_strict_bounded_and_arithmetic(bad):
    with pytest.raises(AuditValidationError):
        validate_details(bad, E.COMPLETED, P.LEAD_IMPORT)


@pytest.mark.parametrize("principal", [user(), ExecutionPrincipal.for_system("system-1", 1, correlation_id="audit-test"),
    ExecutionPrincipal.for_agent("agent-1", 1, correlation_id="audit-test"),
    ExecutionPrincipal.for_workflow("workflow-1", 1, correlation_id="audit-test"),
    ExecutionPrincipal.for_integration("integration-1", 1, correlation_id="audit-test")])
def test_every_principal_snapshot(principal):
    v = values(completed(principal))
    assert v["principal_type"] == principal.principal_type.value and v["actor_id"] == str(principal.actor_id)
    assert v["organization_id"] == principal.organization_id and v["correlation_id"] == principal.correlation_id
    for field in ("agent_id", "workflow_run_id", "integration_id"):
        assert v[field] == getattr(principal, field)
    assert v["authority_role"] == ("member" if principal.principal_type == PrincipalType.USER else None)
    assert v["delegated_by_type"] is None and v["delegated_by_actor_id"] is None


def test_immediate_delegation_and_optional_provenance_preserved():
    parent = ActorReference(principal_type=PrincipalType.USER, actor_id=7)
    p = ExecutionPrincipal.for_agent("agent-1", 1, delegated_by=parent, workflow_run_id="run-1",
                                    integration_id="integration-1", correlation_id="exact-correlation")
    v = values(completed(p))
    assert v["delegated_by_type"] == "USER" and v["delegated_by_actor_id"] == "7"
    assert v["correlation_id"] == "exact-correlation" and v["workflow_run_id"] == "run-1"
    assert v["integration_id"] == "integration-1"


@pytest.mark.parametrize("principal", [None, {}, {"principal_type": "USER", "actor_id": 7, "organization_id": 1},
    user().model_copy(update={"organization_id": 0}), user().model_copy(update={"actor_id": "email@example.invalid"}),
    user().model_copy(update={"correlation_id": "not a valid correlation"})])
def test_invalid_or_client_principal_cannot_build(principal):
    with pytest.raises(AuditValidationError):
        B.tenant_rejected(principal, action=P.LEAD_CREATE, requested_organization_id=2, occurred_at=NOW)


@pytest.mark.parametrize("other", [user(org=2), user(actor=8), user(correlation="other")])
def test_receipt_cannot_override_execution_identity(other):
    with pytest.raises(AuditValidationError):
        B.create_completed(user(), target=AuditLeadTarget(1, 42), authorization=receipt(other), occurred_at=NOW)


def test_target_and_denial_context_cannot_override_tenant():
    p = user()
    with pytest.raises(AuditValidationError):
        B.create_completed(p, target=AuditLeadTarget(2, 42), authorization=receipt(p), occurred_at=NOW)
    with pytest.raises(AuditValidationError):
        B.permission_denied(p, action=P.LEAD_CREATE, authorization=(receipt(p, result=D.DENY),), organization_id=2, occurred_at=NOW)


@pytest.mark.parametrize("key", ["actor_id", "principal_type", "organization_id", "correlation_id",
    "authority_role", "target_type", "event_type", "outcome", "details", "action"])
def test_factory_has_no_client_override_keywords(key):
    with pytest.raises(TypeError):
        B.create_completed(user(), target=AuditLeadTarget(1, 42), authorization=receipt(user()), occurred_at=NOW,
                           **{key: "synthetic-forbidden-value"})


def test_context_role_must_be_typed_same_time_context_not_client_string():
    p = user(); decision = PermissionDecision(D.PERMIT, P.LEAD_CREATE, PrincipalType.USER, R.PERMITTED_BY_ROLE)
    for raw in ("owner", {"role": "owner"}, None):
        with pytest.raises(AuditValidationError):
            capture_authorization_receipt(p, decision, raw)
    with pytest.raises(AuditValidationError):
        capture_authorization_receipt(p, decision, HumanAuthorizationContext(user(org=2), "owner", frozenset(P)))
    r = receipt(p, role="admin")
    assert values(B.create_completed(p, target=AuditLeadTarget(1, 42), authorization=r, occurred_at=NOW))["authority_role"] == "admin"
    with pytest.raises(AuditValidationError):
        B.create_completed(p, target=AuditLeadTarget(1, 42), authorization=replace(r, authority_role="owner"), occurred_at=NOW)


def test_role_snapshot_is_preserved_without_reconsulting_context():
    p = user(); context = HumanAuthorizationContext(p, "member", frozenset(P))
    decision = PermissionDecision(D.PERMIT, P.LEAD_CREATE, PrincipalType.USER, R.PERMITTED_BY_ROLE)
    r = capture_authorization_receipt(p, decision, context)
    newer = replace(context, role="owner")
    assert newer.role == "owner"
    assert values(B.create_completed(p, target=AuditLeadTarget(1, 42), authorization=r, occurred_at=NOW))["authority_role"] == "member"


@pytest.mark.parametrize("decision", [None, {},
    PermissionDecision("PERMIT", P.LEAD_CREATE, PrincipalType.USER, R.PERMITTED_BY_ROLE),
    PermissionDecision(D.PERMIT, "lead.create", PrincipalType.USER, R.PERMITTED_BY_ROLE),
    PermissionDecision(D.PERMIT, P.LEAD_CREATE, PrincipalType.USER, "PERMITTED_BY_ROLE"),
    PermissionDecision(D.PERMIT, P.LEAD_CREATE, PrincipalType.SYSTEM, R.PERMITTED_BY_ROLE),
    PermissionDecision(D.PERMIT, P.LEAD_CREATE, PrincipalType.USER, R.PERMITTED_BY_CAPABILITY),
    PermissionDecision(D.DENY, None, PrincipalType.USER, R.DENIED_UNKNOWN_PERMISSION)])
def test_untyped_or_mismatched_decision_receipts_rejected(decision):
    p = user()
    with pytest.raises(AuditValidationError):
        capture_authorization_receipt(p, decision, HumanAuthorizationContext(p, "member", frozenset(P)))


def test_current_import_contract_does_not_expand_to_machines():
    p = ExecutionPrincipal.for_system("importer", 1)
    with pytest.raises(AuditValidationError):
        B.import_completed(p, authorization=(receipt(p, P.LEAD_IMPORT), receipt(p, P.LEAD_CREATE)),
                           details=ImportAuditDetails(0, 0, 0, 0), occurred_at=NOW)


def test_missing_unknown_human_role_denial_is_null_without_lookup():
    p = user(); d = PermissionDecision(D.DENY, P.LEAD_CREATE, PrincipalType.USER, R.DENIED_INVALID_CONTEXT)
    r = capture_authorization_receipt(p, d, None)
    assert values(B.permission_denied(p, action=P.LEAD_CREATE, authorization=(r,), organization_id=1, occurred_at=NOW))["authority_role"] is None
    assert receipt(p, result=D.DENY, reason=R.DENIED_UNKNOWN_ROLE, role="unmapped").authority_role is None


@pytest.mark.parametrize("change", [dict(event_type="arbitrary"), dict(action="arbitrary"), dict(outcome="FAILED"),
    dict(reason_code="arbitrary"), dict(outcome=AuditOutcome.DENIED), dict(event_type=E.PERMISSION_DENIED),
    dict(event_id="not-uuid"), dict(target={"lead_id": 42, "organization_id": 1}), dict(details={"token": "secret"}),
    dict(principal=user(org=2)), dict(principal=user(actor=8)), dict(principal=user(correlation="other")),
    dict(authority_role="owner"), dict(receipts=()), dict(_seal=None)])
def test_modified_or_unminted_draft_rejected(change):
    with pytest.raises(AuditValidationError):
        values(replace(completed(), **change))


def test_denial_and_security_outcome_or_details_tampering_rejected():
    p = user()
    drafts = [B.permission_denied(p, action=P.LEAD_CREATE, authorization=(receipt(p, result=D.DENY),), organization_id=1, occurred_at=NOW),
              B.tenant_rejected(p, action=P.LEAD_CREATE, requested_organization_id=2, occurred_at=NOW)]
    for draft in drafts:
        for change in (dict(outcome=AuditOutcome.SUCCEEDED), dict(details={"security_metadata": "secret"}), dict(principal=user(org=2))):
            with pytest.raises(AuditValidationError):
                values(replace(draft, **change))


def test_aware_time_normalization_and_naive_rejection():
    offset = timezone(timedelta(hours=6)); p = user()
    draft = B.create_completed(p, target=AuditLeadTarget(1, 42), authorization=receipt(p), occurred_at=NOW.astimezone(offset))
    assert draft.occurred_at == NOW and draft.occurred_at.tzinfo is timezone.utc
    with pytest.raises(AuditValidationError):
        B.create_completed(p, target=AuditLeadTarget(1, 42), authorization=receipt(p), occurred_at=NOW.replace(tzinfo=None))
    with pytest.raises(AuditValidationError):
        audit_persistence_values(draft, recorded_at=NOW.replace(tzinfo=None))


def test_builder_never_evaluates_permissions_or_logs_payload(monkeypatch, caplog):
    from backend.services import permission_evaluator
    monkeypatch.setattr(permission_evaluator, "evaluate_permission", lambda *a, **k: pytest.fail("Builder invoked evaluator"))
    values(completed())
    secret = "synthetic-sensitive-candidate-DO-NOT-ECHO"
    with pytest.raises(AuditValidationError) as exc:
        validate_details({"password": secret}, E.COMPLETED, P.LEAD_CREATE)
    assert secret not in str(exc.value) and secret not in caplog.text
    assert caplog.text == ""


def test_immutable_draft_and_no_mutable_json_aliasing():
    draft = completed()
    with pytest.raises(FrozenInstanceError):
        draft.action = P.LEAD_IMPORT
    first = values(draft); first["authorization_evidence"][0]["permission"] = "unknown"
    first["details"]["password"] = "synthetic"
    assert values(draft)["authorization_evidence"] == [evidence()] and values(draft)["details"] == {}


@pytest.mark.parametrize("field", ["actor_id", "organization_id", "correlation_id", "principal_type",
    "delegated_by", "nested_delegator_actor", "nested_delegator_type",
    "workflow_run_id", "agent_id", "integration_id"])
@pytest.mark.parametrize("category", ["completed", "denied", "tenant_rejected"])
def test_r2_corrupted_principals_rejected_without_diagnostic_disclosure(field, category, capsys, caplog):
    marker = "Probe42!"  # Synthetic fixture only; never print captured diagnostics.
    secret_value = {"password": marker}
    parent = ActorReference(principal_type=PrincipalType.USER, actor_id=7)
    valid = ExecutionPrincipal.for_agent("agent-r2", 1, delegated_by=parent, correlation_id="r2-correlation")
    if field.startswith("nested_delegator_"):
        key = "actor_id" if field.endswith("actor") else "principal_type"
        corrupted = valid.model_copy(update={"delegated_by": parent.model_copy(update={key: secret_value})})
    else:
        corrupted = valid.model_copy(update={field: secret_value})
    permit = receipt(valid); denial = receipt(valid, result=D.DENY)
    capsys.readouterr(); caplog.clear()
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(AuditValidationError) as rejected:
            if category == "completed":
                B.create_completed(corrupted, target=AuditLeadTarget(1, 42), authorization=permit, occurred_at=NOW)
            elif category == "denied":
                B.permission_denied(corrupted, action=P.LEAD_CREATE, authorization=(denial,), organization_id=1, occurred_at=NOW)
            else:
                B.tenant_rejected(corrupted, action=P.LEAD_CREATE, requested_organization_id=2, occurred_at=NOW)
    error = rejected.value
    assert emitted == []
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "" and caplog.text == ""
    assert marker not in str(error) and marker not in repr(error)
    assert error.__cause__ is None and error.__context__ is None
    assert marker not in "".join(traceback.format_exception(error))


def test_r2_original_user_actor_tenant_rejection_warning_leak_is_closed(capsys, caplog):
    marker = "Probe42!"
    corrupted = user().model_copy(update={"actor_id": {"password": marker}})
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(AuditValidationError) as rejected:
            B.tenant_rejected(corrupted, action=P.LEAD_CREATE, requested_organization_id=2, occurred_at=NOW)
    assert emitted == []
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "" and caplog.text == ""
    assert marker not in str(rejected.value) and marker not in repr(rejected.value)
    assert rejected.value.__cause__ is None and rejected.value.__context__ is None
    assert marker not in "".join(traceback.format_exception(rejected.value))


@pytest.mark.parametrize("factory,actor", [
    (ExecutionPrincipal.for_user, 7), (ExecutionPrincipal.for_system, "system-r2"),
    (ExecutionPrincipal.for_agent, "agent-r2"), (ExecutionPrincipal.for_workflow, "workflow-r2"),
    (ExecutionPrincipal.for_integration, "integration-r2")])
def test_r2_valid_principals_snapshot_without_candidate_serialization(factory, actor, monkeypatch):
    from backend.schemas.audit_event import _principal
    p = factory(actor, 1, correlation_id="r2-exact-correlation")
    expected = p.model_dump()  # Known valid fixture; not the production path.
    with monkeypatch.context() as patch:
        patch.setattr(ExecutionPrincipal, "model_dump", lambda *a, **k: pytest.fail("Serialized candidate before validation"))
        snapshot = _principal(p)
    assert snapshot is not p and snapshot.model_dump() == expected
    assert values(completed(p))["correlation_id"] == "r2-exact-correlation"


def test_r2_direct_e03_instance_validation_revalidates_copied_state():
    from pydantic import ValidationError
    valid = user()
    corrupted = valid.model_copy(update={"actor_id": {"password": "Probe42!"}})
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(ValidationError):
            ExecutionPrincipal.model_validate(corrupted)
    assert emitted == []
    assert ExecutionPrincipal.model_config["revalidate_instances"] == "always"
    assert ExecutionPrincipal.model_validate(valid) is not valid


def test_r2_revalidation_rejects_corrupted_receipt_principal_before_persistence(capsys, caplog):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.database.transactions import service_transaction
    from backend.repositories.audit_repository import AuditRepository
    draft = completed()
    corrupted = draft.receipts[0].principal.model_copy(update={"actor_id": {"password": "Probe42!"}})
    draft = replace(draft, receipts=(replace(draft.receipts[0], principal=corrupted),))
    engine = create_engine("sqlite:///:memory:")
    try:
        with Session(engine) as db:
            with service_transaction(db), warnings.catch_warnings(record=True) as emitted:
                warnings.simplefilter("always")
                with pytest.raises(AuditValidationError) as rejected:
                    AuditRepository(db).append(draft)
                assert not db.new and not db.in_transaction()  # No INSERT or DB access.
                assert emitted == []
                assert rejected.value.__cause__ is None and rejected.value.__context__ is None
                assert "Probe42!" not in "".join(traceback.format_exception(rejected.value))
        captured = capsys.readouterr()
        assert captured.out == "" and captured.err == "" and caplog.text == ""
    finally:
        engine.dispose()
