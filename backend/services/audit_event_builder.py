"""Trusted internal E05 factories; no IO, authorization evaluation or live adoption.

Future server callers must authenticate E03 producers, capture the actual E04
decision/context together, and supply an owned result reference. Typed values
do not authenticate client JSON. Private mint markers catch accidental forged
or replaced drafts, not hostile Python code or raw database access.
"""

from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from backend.schemas.action_permission import (
    ActionPermission, HumanAuthorizationContext, MachineAuthorizationContext,
    AuthorizationContext, PermissionDecision, PermissionResult, ROLE_PERMISSIONS,
)
from backend.schemas.execution_principal import ExecutionPrincipal, PrincipalType
from backend.schemas.audit_event import (
    AuditAuthorizationReceipt, AuditEventDraft, AuditEventType, AuditOutcome, AuditReason,
    AuditEvidenceItem, AuditLeadTarget, AuditValidationError, EmptyAuditDetails,
    ImportAuditDetails, LifecycleAuditDetails, aware_utc, positive_identifier,
    _principal, _receipt_fingerprint, _validate_receipt, _draft_values, _draft_fingerprint,
    _RECEIPT_MARKER, _DRAFT_MARKER,
)


def capture_authorization_receipt(principal: ExecutionPrincipal, decision: PermissionDecision,
                                  context: AuthorizationContext | None) -> AuditAuthorizationReceipt:
    """Capture an already evaluated E04 result, with its same-time server context.

    No role string or raw decision dictionary is accepted. Missing/invalid-role
    denial context yields NULL role; do not fetch a newer membership snapshot.
    This factory neither invokes E04 nor persists anything.
    """
    principal = _principal(principal)
    if (type(decision) is not PermissionDecision or type(decision.principal_type) is not PrincipalType
            or decision.principal_type != principal.principal_type):
        raise AuditValidationError("Matching typed E04 decision required.")
    evidence = AuditEvidenceItem(decision.permission, decision.result, decision.reason_code)
    role = None
    if context is not None:
        if type(context) not in {HumanAuthorizationContext, MachineAuthorizationContext}:
            raise AuditValidationError("Typed evaluated authority context required.")
        try:
            context.__post_init__()
            if _principal(context.principal) != principal:
                raise ValueError
        except (ValueError, TypeError):
            raise AuditValidationError("Audit authority identity mismatch.") from None
        if type(context) is HumanAuthorizationContext:
            role = context.role if context.role in ROLE_PERMISSIONS else None
    elif evidence.decision == PermissionResult.PERMIT:
        raise AuditValidationError("Permit requires evaluated authority context.")
    receipt = AuditAuthorizationReceipt(principal, evidence, role,
                (_RECEIPT_MARKER, _receipt_fingerprint(principal, evidence, role)))
    _validate_receipt(receipt)
    return receipt


def _build(principal, occurred_at, event_type, action, outcome, reason, receipts, target, details):
    principal = _principal(principal)
    if type(receipts) is not tuple:
        raise AuditValidationError("Typed audit receipt tuple required.")
    for receipt in receipts:
        _validate_receipt(receipt)
    role = receipts[0].authority_role if receipts else None
    draft = AuditEventDraft(str(uuid4()), principal, aware_utc(occurred_at), event_type, action,
                            outcome, reason, receipts, role, target, details, None)
    return replace(draft, _seal=(_DRAFT_MARKER, _draft_fingerprint(_draft_values(draft))))


class AuditEventBuilder:
    """Server-only factories; no caller-selected identity, event, outcome or JSON."""

    @staticmethod
    def create_completed(principal: ExecutionPrincipal, *, target: AuditLeadTarget,
                         authorization: AuditAuthorizationReceipt, occurred_at: datetime) -> AuditEventDraft:
        return _build(principal, occurred_at, AuditEventType.COMPLETED, ActionPermission.LEAD_CREATE,
                      AuditOutcome.SUCCEEDED, AuditReason.COMPLETED, (authorization,), target, EmptyAuditDetails())

    @staticmethod
    def lifecycle_completed(principal: ExecutionPrincipal, *, target: AuditLeadTarget,
                            authorization: AuditAuthorizationReceipt, details: LifecycleAuditDetails,
                            occurred_at: datetime) -> AuditEventDraft:
        return _build(principal, occurred_at, AuditEventType.COMPLETED,
                      ActionPermission.LEAD_LIFECYCLE_CHANGE, AuditOutcome.SUCCEEDED,
                      AuditReason.COMPLETED, (authorization,), target, details)

    @staticmethod
    def import_completed(principal: ExecutionPrincipal, *, authorization: tuple[AuditAuthorizationReceipt, ...],
                         details: ImportAuditDetails, occurred_at: datetime) -> AuditEventDraft:
        return _build(principal, occurred_at, AuditEventType.COMPLETED, ActionPermission.LEAD_IMPORT,
                      AuditOutcome.SUCCEEDED, AuditReason.COMPLETED, authorization, None, details)

    @staticmethod
    def permission_denied(principal: ExecutionPrincipal, *, action: ActionPermission,
                          authorization: tuple[AuditAuthorizationReceipt, ...], organization_id: int,
                          occurred_at: datetime) -> AuditEventDraft:
        principal = _principal(principal)
        if positive_identifier(organization_id) != principal.organization_id:
            raise AuditValidationError("Audit denial tenant mismatch.")
        return _build(principal, occurred_at, AuditEventType.PERMISSION_DENIED, action,
                      AuditOutcome.DENIED, AuditReason.PERMISSION_DENIED, authorization, None, EmptyAuditDetails())

    @staticmethod
    def tenant_rejected(principal: ExecutionPrincipal, *, action: ActionPermission,
                        requested_organization_id: int, occurred_at: datetime) -> AuditEventDraft:
        principal = _principal(principal)
        if positive_identifier(requested_organization_id) == principal.organization_id:
            raise AuditValidationError("Audit tenant rejection requires an actual mismatch.")
        return _build(principal, occurred_at, AuditEventType.SECURITY_REJECTED, action,
                      AuditOutcome.DENIED, AuditReason.TENANT_MISMATCH, (), None, EmptyAuditDetails())
