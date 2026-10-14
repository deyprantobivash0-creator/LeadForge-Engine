"""Closed audit value types. Shape validation never authenticates a producer."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import json
from uuid import UUID

from backend.core.exceptions import ValidationException
from backend.schemas.action_permission import ActionPermission, PermissionReason, PermissionResult, ROLE_PERMISSIONS
from backend.schemas.execution_principal import ExecutionPrincipal, PrincipalType
from backend.schemas.lead_contract import LeadLifecycle


class AuditValidationError(ValidationException):
    """Static category messages only: never include a rejected value/payload."""

    error_code = "AUDIT_VALIDATION_ERROR"


class AuditEventType(StrEnum):
    COMPLETED = "business.command.completed"
    PERMISSION_DENIED = "permission.denied"
    SECURITY_REJECTED = "security.command.rejected"


class AuditOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"


class AuditReason(StrEnum):
    COMPLETED = "COMMAND_COMPLETED"
    PERMISSION_DENIED = "ACTION_PERMISSION_DENIED"
    TENANT_MISMATCH = "EXECUTION_TENANT_MISMATCH"


class AuditChangedField(StrEnum):
    STATUS = "status"
    NOTES = "notes"
    LAST_CONTACTED = "last_contacted"
    NEXT_FOLLOW_UP = "next_follow_up"


def positive_identifier(value):
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        raise AuditValidationError("Invalid audit identifier.")
    return value


def aware_utc(value):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise AuditValidationError("Audit timestamps require aware values.")
    return value.astimezone(timezone.utc)


def canonical_event_id(value):
    try:
        if type(value) is not str:
            raise ValueError
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise AuditValidationError("Invalid audit event identifier.") from None
    return value


def canonical_audit_json(value):
    """Audit JSON only: primitives, depth <=2, <=8 keys/items, <=2048 UTF-8 bytes.

    This is a size/representation validator, never an arbitrary-object serializer
    or secret scrubber. Closed evidence/details validators remain mandatory.
    """
    def check(item, depth):
        if type(item) in {dict, list}:
            if depth > 2 or len(item) > 8:
                raise AuditValidationError("Audit JSON structure exceeds bounds.")
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise AuditValidationError("Invalid audit JSON keys.")
                children = item.values()
            else:
                children = item
            for child in children:
                check(child, depth + 1)
        elif type(item) not in {str, int, bool, type(None)}:
            raise AuditValidationError("Invalid audit JSON value type.")

    check(value, 1)
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        size = len(encoded.encode("utf-8"))
    except (ValueError, TypeError, UnicodeError):
        raise AuditValidationError("Invalid audit JSON encoding.") from None
    if size > 2048:
        raise AuditValidationError("Audit JSON exceeds byte limit.")
    return encoded


# E04 enum membership is not E05 approval. Taxonomy changes require an explicit
# audit compatibility review; never derive DENY reasons by enum complement.
APPROVED_DECISION_REASON_COMBINATIONS = frozenset({
    (PermissionResult.PERMIT, PermissionReason.PERMITTED_BY_ROLE),
    (PermissionResult.PERMIT, PermissionReason.PERMITTED_BY_CAPABILITY),
    (PermissionResult.DENY, PermissionReason.DENIED_PERMISSION_NOT_GRANTED),
    (PermissionResult.DENY, PermissionReason.DENIED_INVALID_CONTEXT),
    (PermissionResult.DENY, PermissionReason.DENIED_TENANT_MISMATCH),
    (PermissionResult.DENY, PermissionReason.DENIED_PRINCIPAL_MISMATCH),
    (PermissionResult.DENY, PermissionReason.DENIED_UNKNOWN_ROLE),
    (PermissionResult.DENY, PermissionReason.DENIED_UNKNOWN_PERMISSION),
})


@dataclass(frozen=True)
class AuditEvidenceItem:
    permission: ActionPermission
    decision: PermissionResult
    reason_code: PermissionReason

    def __post_init__(self):
        if (type(self.permission) is not ActionPermission
                or type(self.decision) is not PermissionResult
                or type(self.reason_code) is not PermissionReason):
            raise AuditValidationError("Typed audit authorization evidence required.")
        if (self.decision, self.reason_code) not in APPROVED_DECISION_REASON_COMBINATIONS:
            raise AuditValidationError("Unapproved audit decision/reason combination.")

    def as_json(self):
        self.__post_init__()
        return dict(permission=self.permission.value, decision=self.decision.value,
                    reason_code=self.reason_code.value)


def validate_authorization_evidence(value):
    """Validate serialized storage shape; this does NOT make client JSON trusted."""
    if type(value) is not list or len(value) > 8:
        raise AuditValidationError("Invalid audit evidence container.")
    canonical_audit_json(value)
    items = []
    for item in value:
        if (type(item) is not dict or set(item) != {"permission", "decision", "reason_code"}
                or any(type(v) is not str for v in item.values())):
            raise AuditValidationError("Invalid audit evidence item schema.")
        try:
            items.append(AuditEvidenceItem(ActionPermission(item["permission"]),
                         PermissionResult(item["decision"]), PermissionReason(item["reason_code"])))
        except (ValueError, TypeError):
            raise AuditValidationError("Invalid audit evidence domain or consistency.") from None
    if len({item.permission for item in items}) != len(items):
        raise AuditValidationError("Duplicate audit authorization permission.")
    return tuple(items)


@dataclass(frozen=True)
class EmptyAuditDetails:
    def as_json(self):
        return {}


@dataclass(frozen=True)
class LifecycleAuditDetails:
    status_before: LeadLifecycle
    status_after: LeadLifecycle
    changed_fields: tuple[AuditChangedField, ...]

    def __post_init__(self):
        if (type(self.status_before) is not LeadLifecycle or type(self.status_after) is not LeadLifecycle
                or type(self.changed_fields) is not tuple or len(self.changed_fields) > 4
                or any(type(f) is not AuditChangedField for f in self.changed_fields)
                or len(set(self.changed_fields)) != len(self.changed_fields)):
            raise AuditValidationError("Invalid audit lifecycle details.")
        if ((self.status_before != self.status_after)
                != (AuditChangedField.STATUS in self.changed_fields)):
            raise AuditValidationError("Inconsistent audit lifecycle status change.")

    def as_json(self):
        self.__post_init__()
        return dict(status_before=self.status_before.value, status_after=self.status_after.value,
                    changed_fields=[f.value for f in self.changed_fields])


@dataclass(frozen=True)
class ImportAuditDetails:
    total: int
    imported: int
    duplicates: int
    invalid: int

    def __post_init__(self):
        values = (self.total, self.imported, self.duplicates, self.invalid)
        if any(type(v) is not int or not 0 <= v <= 1000 for v in values):
            raise AuditValidationError("Invalid audit import count.")
        if self.total != self.imported + self.duplicates + self.invalid:
            raise AuditValidationError("Inconsistent audit import counts.")

    def as_json(self):
        self.__post_init__()
        return dict(total=self.total, imported=self.imported, duplicates=self.duplicates, invalid=self.invalid)


def validate_details(value, event_type, action):
    """Closed serialized validation, not a trusted business construction API."""
    if type(event_type) is not AuditEventType or type(action) is not ActionPermission:
        raise AuditValidationError("Typed audit event and action required.")
    if action not in {ActionPermission.LEAD_CREATE, ActionPermission.LEAD_LIFECYCLE_CHANGE,
                      ActionPermission.LEAD_IMPORT}:
        raise AuditValidationError("Unsupported audit action.")
    if type(value) is not dict:
        raise AuditValidationError("Invalid audit details container.")
    canonical_audit_json(value)
    if event_type != AuditEventType.COMPLETED or action == ActionPermission.LEAD_CREATE:
        if value:
            raise AuditValidationError("Audit details must be empty.")
        return EmptyAuditDetails()
    try:
        if action == ActionPermission.LEAD_LIFECYCLE_CHANGE:
            if (set(value) != {"status_before", "status_after", "changed_fields"}
                    or type(value["status_before"]) is not str or type(value["status_after"]) is not str
                    or type(value["changed_fields"]) is not list
                    or any(type(f) is not str for f in value["changed_fields"])):
                raise ValueError
            return LifecycleAuditDetails(LeadLifecycle(value["status_before"]),
                       LeadLifecycle(value["status_after"]),
                       tuple(AuditChangedField(f) for f in value["changed_fields"]))
        if action == ActionPermission.LEAD_IMPORT:
            if set(value) != {"total", "imported", "duplicates", "invalid"}:
                raise ValueError
            return ImportAuditDetails(**value)
    except (ValueError, TypeError):
        raise AuditValidationError("Invalid audit details schema or values.") from None
    raise AuditValidationError("Unsupported audit action.")


@dataclass(frozen=True)
class AuditLeadTarget:
    """Trusted owned-result reference supplied by future server callers, not ingress."""
    organization_id: int
    lead_id: int

    def __post_init__(self):
        positive_identifier(self.organization_id)
        positive_identifier(self.lead_id)


@dataclass(frozen=True)
class AuditAuthorizationReceipt:
    """Captured E04 result/context. Only the server receipt factory mints this."""
    principal: ExecutionPrincipal
    evidence: AuditEvidenceItem
    authority_role: str | None
    _seal: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class AuditEventDraft:
    """Immutable builder result. No transport decoder or arbitrary payload API.

    Python internals/raw SQL remain outside the trusted application boundary.
    Persistence revalidates even builder-produced values before insertion.
    """
    event_id: str
    principal: ExecutionPrincipal
    occurred_at: datetime
    event_type: AuditEventType
    action: ActionPermission
    outcome: AuditOutcome
    reason_code: AuditReason
    receipts: tuple[AuditAuthorizationReceipt, ...]
    authority_role: str | None
    target: AuditLeadTarget | None
    details: EmptyAuditDetails | LifecycleAuditDetails | ImportAuditDetails
    _seal: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class AuditEventReceipt:
    """Immutable persistence receipt/read DTO; no tracked ORM or JSON payload."""
    event_id: str
    organization_id: int
    occurred_at: datetime
    recorded_at: datetime


_RECEIPT_MARKER = object()
_DRAFT_MARKER = object()
_ACTIONS = frozenset({ActionPermission.LEAD_CREATE, ActionPermission.LEAD_LIFECYCLE_CHANGE,
                      ActionPermission.LEAD_IMPORT})

def _principal(value):
    if type(value) is not ExecutionPrincipal:
        raise AuditValidationError("Trusted typed audit principal required.")
    # E03 revalidate_instances="always" validates copied/corrupted instances
    # directly and produces a fresh snapshot. Never serialize a candidate first.
    try:
        verified = ExecutionPrincipal.model_validate(value)
    except (ValueError, TypeError):
        verified = None
    if verified is None:
        # Raise outside the handler: even __context__ must not retain the raw
        # Pydantic error (which can contain rejected field values).
        raise AuditValidationError("Invalid audit execution identity.") from None
    return verified


def _receipt_fingerprint(principal, evidence, role):
    return (principal.to_json(), canonical_audit_json(evidence.as_json()), role)


def _validate_receipt(value):
    if type(value) is not AuditAuthorizationReceipt or type(value.evidence) is not AuditEvidenceItem:
        raise AuditValidationError("Trusted audit authorization receipt required.")
    principal = _principal(value.principal)
    value.evidence.__post_init__()
    if value.authority_role is not None and (
            type(value.authority_role) is not str or value.authority_role not in ROLE_PERMISSIONS):
        raise AuditValidationError("Invalid audit authority snapshot.")
    if principal.principal_type != PrincipalType.USER and value.authority_role is not None:
        raise AuditValidationError("Machine audit authority role must be absent.")
    if value.evidence.decision == PermissionResult.PERMIT:
        expected = (PermissionReason.PERMITTED_BY_ROLE if principal.principal_type == PrincipalType.USER
                    else PermissionReason.PERMITTED_BY_CAPABILITY)
        if value.evidence.reason_code != expected or (
                principal.principal_type == PrincipalType.USER and value.authority_role is None):
            raise AuditValidationError("Invalid audit permit authority snapshot.")
    if (type(value._seal) is not tuple or len(value._seal) != 2
            or value._seal[0] is not _RECEIPT_MARKER
            or value._seal[1] != _receipt_fingerprint(principal, value.evidence, value.authority_role)):
        raise AuditValidationError("Audit receipt was not constructed by the trusted factory.")
    return principal


def _draft_values(draft):
    if type(draft) is not AuditEventDraft:
        raise AuditValidationError("Trusted audit builder result required.")
    principal = _principal(draft.principal)
    occurred_at = aware_utc(draft.occurred_at)
    canonical_event_id(draft.event_id)
    if type(draft.action) is not ActionPermission or draft.action not in _ACTIONS:
        raise AuditValidationError("Unsupported audit action.")
    if (type(draft.event_type) is not AuditEventType or type(draft.outcome) is not AuditOutcome
            or type(draft.reason_code) is not AuditReason):
        raise AuditValidationError("Typed audit taxonomy required.")
    if type(draft.receipts) is not tuple or len(draft.receipts) > 8:
        raise AuditValidationError("Invalid audit receipt container.")
    for receipt in draft.receipts:
        if _validate_receipt(receipt) != principal:
            raise AuditValidationError("Audit receipt execution identity mismatch.")
    evidence_json = [receipt.evidence.as_json() for receipt in draft.receipts]
    evidence = validate_authorization_evidence(evidence_json)
    roles = {receipt.authority_role for receipt in draft.receipts}
    if (len(roles) > 1 or draft.authority_role != (next(iter(roles)) if roles else None)):
        raise AuditValidationError("Inconsistent evaluated audit authority role.")
    required = ({ActionPermission.LEAD_IMPORT, ActionPermission.LEAD_CREATE}
                if draft.action == ActionPermission.LEAD_IMPORT else {draft.action})
    if draft.action == ActionPermission.LEAD_IMPORT and principal.principal_type != PrincipalType.USER:
        raise AuditValidationError("Import audit requires the current USER command contract.")
    if draft.event_type == AuditEventType.COMPLETED:
        if (draft.outcome != AuditOutcome.SUCCEEDED or draft.reason_code != AuditReason.COMPLETED
                or {e.permission for e in evidence} != required or len(evidence) != len(required)
                or any(e.decision != PermissionResult.PERMIT for e in evidence)):
            raise AuditValidationError("Incomplete successful audit authorization evidence.")
        # Latest I2 instruction: success membership is order independent. Keep
        # the actual supplied evaluation order in storage, never sort the list.
        if draft.action == ActionPermission.LEAD_IMPORT:
            if draft.target is not None or type(draft.details) is not ImportAuditDetails:
                raise AuditValidationError("Invalid successful import audit target or details.")
            target_id = draft.event_id
        else:
            if type(draft.target) is not AuditLeadTarget:
                raise AuditValidationError("Trusted owned audit lead target required.")
            draft.target.__post_init__()
            if draft.target.organization_id != principal.organization_id:
                raise AuditValidationError("Audit target tenant mismatch.")
            target_id = str(draft.target.lead_id)
            detail_type = (EmptyAuditDetails if draft.action == ActionPermission.LEAD_CREATE
                           else LifecycleAuditDetails)
            if type(draft.details) is not detail_type:
                raise AuditValidationError("Typed event-specific audit details required.")
    elif draft.event_type == AuditEventType.PERMISSION_DENIED:
        pairs = [(e.permission, e.decision) for e in evidence]
        allowed = [[(draft.action, PermissionResult.DENY)]]
        if draft.action == ActionPermission.LEAD_IMPORT:
            allowed = [[(ActionPermission.LEAD_IMPORT, PermissionResult.DENY)],
                       [(ActionPermission.LEAD_IMPORT, PermissionResult.PERMIT),
                        (ActionPermission.LEAD_CREATE, PermissionResult.DENY)]]
        if (draft.outcome != AuditOutcome.DENIED or draft.reason_code != AuditReason.PERMISSION_DENIED
                or pairs not in allowed or draft.target is not None
                or type(draft.details) is not EmptyAuditDetails):
            raise AuditValidationError("Invalid first decisive audit denial evidence.")
        target_id = None
    else:
        if (draft.outcome != AuditOutcome.DENIED or draft.reason_code != AuditReason.TENANT_MISMATCH
                or evidence or draft.target is not None or type(draft.details) is not EmptyAuditDetails):
            raise AuditValidationError("Invalid trusted tenant rejection audit.")
        target_id = None
    details_json = draft.details.as_json()
    validate_details(details_json, draft.event_type, draft.action)
    delegator = principal.delegated_by
    return dict(event_id=draft.event_id, organization_id=principal.organization_id,
                occurred_at=occurred_at, event_type=draft.event_type.value, action=draft.action.value,
                outcome=draft.outcome.value, reason_code=draft.reason_code.value,
                principal_type=principal.principal_type.value, actor_id=str(principal.actor_id),
                delegated_by_type=delegator.principal_type.value if delegator else None,
                delegated_by_actor_id=str(delegator.actor_id) if delegator else None,
                correlation_id=principal.correlation_id, workflow_run_id=principal.workflow_run_id,
                agent_id=principal.agent_id, integration_id=principal.integration_id,
                target_type="lead_import" if draft.action == ActionPermission.LEAD_IMPORT else "lead",
                target_id=target_id, authorization_evidence=evidence_json,
                authority_role=draft.authority_role, details=details_json, schema_version=1)


def _draft_fingerprint(values):
    # Binding to minted values catches dataclass replacement/copy mistakes. It
    # is not a cryptographic signature or a defense against hostile Python.
    return tuple((key, canonical_audit_json(value) if type(value) in {dict, list} else value)
                 for key, value in values.items())


def audit_persistence_values(draft, *, recorded_at):
    """Repository conversion boundary; revalidate before any Session mutation."""
    values = _draft_values(draft)
    if (type(draft._seal) is not tuple or len(draft._seal) != 2
            or draft._seal[0] is not _DRAFT_MARKER
            or draft._seal[1] != _draft_fingerprint(values)):
        raise AuditValidationError("Audit draft was not constructed by the trusted factory.")
    return {**values, "recorded_at": aware_utc(recorded_at)}
