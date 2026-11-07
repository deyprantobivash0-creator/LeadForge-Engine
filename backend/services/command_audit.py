"""Structural-denial adoption for the three canonical E05 commands.

The explicit operation belongs to the outer application caller, never to a
request/global cache. This module observes no transaction and settles none.
Custom database owners inject a configured G0 recorder; the normal application
uses its existing canonical factory/options, without guessing Engine settings.
"""

from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone

from backend.database.transactions import in_service_transaction
from backend.schemas.action_permission import HumanAuthorizationContext, MachineAuthorizationContext
from backend.services.application_audit import application_audit_boundary, rejection_diagnostic
from backend.services.audit_event_builder import AuditEventBuilder, capture_authorization_receipt


def _application_recorder(db):
    from backend.database.dependencies import canonical_audit_connections
    from backend.database.session import SessionLocal, engine
    from backend.services.rejection_recorder import RejectionRecorder

    if db.get_bind() is not engine:
        return None  # An injected Engine's original connect_args cannot be guessed.
    return RejectionRecorder(SessionLocal, canonical_connections=canonical_audit_connections(db))


@contextmanager
def command_audit_boundary(db, recorder=None, operation=None):
    """Standalone owner or explicit composition; unsupported nesting defers.

    Boundary/setup/cleanup failures are evidence gaps, never business errors.
    Exceptions from the business body retain their original identity and E02
    behavior. The G0 boundary alone seals settlement and invokes persistence.
    """
    if operation is not None or in_service_transaction(db):
        yield operation
        return
    stack, owned = ExitStack(), False
    try:
        if recorder is None:
            recorder = _application_recorder(db)
            owned = recorder is not None
        captured = (stack.enter_context(application_audit_boundary(db, recorder))
                    if recorder is not None else None)
    except Exception:
        captured = None
    try:
        with stack:
            yield captured
    finally:
        if owned:
            try:
                recorder.close()
            except Exception:
                rejection_diagnostic("audit.rejection.persistence_failed")


def _capture(operation, build):
    try:
        draft = build()
        if operation is None:
            rejection_diagnostic("audit.rejection.recording_deferred_unavailable", draft)
        else:
            operation.capture_rejection(draft)
    except Exception:
        rejection_diagnostic("audit.rejection.persistence_failed")


def capture_permission_denial(operation, principal, action, organization_id,
                              decision, authority, authorization=()):
    # An invalid/mismatched authority is the reason for DENY, not a legitimate
    # role snapshot. Retain the actual decision, never serialize that input or
    # evaluate again to manufacture an authority context for the event.
    context = authority if type(authority) in {HumanAuthorizationContext, MachineAuthorizationContext} else None
    if context is not None:
        try:
            context.__post_init__()
            if context.principal != principal:
                context = None
        except (ValueError, TypeError):
            context = None
    _capture(operation, lambda: AuditEventBuilder.permission_denied(
        principal, action=action, organization_id=organization_id,
        authorization=authorization + (capture_authorization_receipt(principal, decision, context),),
        occurred_at=datetime.now(timezone.utc)))


def capture_tenant_denial(operation, principal, action, organization_id):
    _capture(operation, lambda: AuditEventBuilder.tenant_rejected(
        principal, action=action, requested_organization_id=organization_id,
        occurred_at=datetime.now(timezone.utc)))
