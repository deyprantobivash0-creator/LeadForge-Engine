"""Explicit rejection capture outside E02; no business settlement or global queue.

This is an internal server API, not authentication for client-supplied drafts.
Only the outer application owner may establish this boundary. Compositions pass
its operation explicitly; an already governed caller must defer to that owner.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from threading import get_ident

from sqlalchemy import event as session_event

from backend.core.logger import event
from backend.database.transactions import in_service_transaction, service_transaction
from backend.database.rejection_storage import active_attempt
from backend.schemas.audit_event import (
    AuditEventDraft, AuditEventType, AuditOutcome, AuditValidationError,
    audit_persistence_values,
)


_SETTLED = object()


def validate_rejection(draft):
    values = audit_persistence_values(draft, recorded_at=datetime.now(timezone.utc))
    if (draft.outcome is not AuditOutcome.DENIED or draft.event_type not in {
            AuditEventType.PERMISSION_DENIED, AuditEventType.SECURITY_REJECTED}):
        raise AuditValidationError("Canonical rejection draft required.")
    return values


def rejection_diagnostic(name, draft=None):
    # No exception argument, traceback, request or database message is logged.
    fields = {}
    if draft is not None:
        fields = dict(organization_id=draft.principal.organization_id,
                      principal_type=draft.principal.principal_type.value,
                      actor_id=draft.principal.actor_id,
                      correlation_id=draft.principal.correlation_id,
                      reason=draft.reason_code.value)
    try:
        event(name, level=logging.WARNING, **fields)
    except Exception:
        # Broken diagnostics must not replace the authoritative business denial.
        pass


@dataclass(frozen=True)
class SettledRejection:
    """Boundary-minted, immutable value; contains no Session/Connection/ORM data.

    Private knowledge capability carries observations, not mutable draft data.
    The private seal catches accidental construction/replacement, not hostile
    Python. There is intentionally no JSON decoder or public mint function.
    """
    draft: AuditEventDraft
    business_session_id: int
    business_connection_id: int
    business_transaction_id: int
    database_bind_id: int
    _owner: object = field(repr=False, compare=False)
    _seal: object = field(repr=False, compare=False)
    _knowledge: object = field(default=None, repr=False, compare=False)


def _fingerprint(draft, session_id, connection_id, transaction_id, bind_id, owner, knowledge):
    return (_SETTLED, owner, draft._seal, session_id, connection_id, transaction_id, bind_id, knowledge)


def validate_settlement(record, owner):
    if type(record) is not SettledRejection or record._owner is not owner:
        raise AuditValidationError("Boundary-confirmed settlement required.")
    validate_rejection(record.draft)
    if record._seal != _fingerprint(record.draft, record.business_session_id,
                                    record.business_connection_id, record.business_transaction_id,
                                    record.database_bind_id, owner, record._knowledge):
        raise AuditValidationError("Invalid settlement provenance.")


class AuditOperation:
    """First decisive rejection only; explicit context, never an authority grant."""
    def __init__(self, capture_guard):
        self._capture_guard = capture_guard
        self._draft = None
        self.receipt = None
        self.result = None

    def capture_rejection(self, draft):
        if self._capture_guard is None or not self._capture_guard():
            raise AuditValidationError("Capture requires the boundary's active business E02 scope.")
        if self._draft is not None:
            return False
        validate_rejection(draft)
        self._draft = draft
        return True


@contextmanager
def application_audit_boundary(business_db, recorder):
    """Observe the outer business operation, then attempt its first rejection.

    Wrap the *outermost* service_transaction. This boundary never commits,
    rolls back, closes or repairs business_db. Existing read AUTOBEGIN is safe
    to observe; an external Session.begin or an already governed root is not.
    Failed/ambiguous cleanup skips recording. Original exceptions propagate.
    """
    existing = business_db.get_transaction()
    database_bind = business_db.get_bind()
    recording_key = recorder._recording_key
    if (in_service_transaction(business_db) or not business_db.is_active
            or (existing is not None and existing.origin.name != "AUTOBEGIN")
            or database_bind is not recorder.database_bind):
        raise AuditValidationError("An outer same-database audit boundary is required.")
    roots = [existing] if existing is not None else []
    rolled_back = set()
    connection_id = 0
    owner_thread = get_ident()

    def created(_db, transaction):
        if transaction.parent is None:
            roots.append(transaction)

    def begun(_db, transaction, connection):
        nonlocal connection_id
        if transaction.parent is None:
            connection_id = id(connection)

    def rollback_complete(_db, transaction):
        if transaction.parent is None and in_service_transaction(business_db):
            rolled_back.add(transaction)

    def can_capture():
        return get_ident() == owner_thread and in_service_transaction(business_db)

    operation = AuditOperation(can_capture)
    listeners = (("after_transaction_create", created), ("after_begin", begun),
                 ("after_soft_rollback", rollback_complete))
    for name, callback in listeners:
        session_event.listen(business_db, name, callback)
    escaped = False
    try:
        yield operation
    except BaseException:
        escaped = True
        raise
    finally:
        operation._capture_guard = None  # Release the live business reference.
        cleanup_ok = True
        for name, callback in reversed(listeners):
            try:
                session_event.remove(business_db, name, callback)
            except Exception:
                cleanup_ok = False
        draft = operation._draft
        if draft is not None:
            # No-SQL rejection has no SQLAlchemy transaction to roll back. It
            # still requires capture inside E02, an escaping rejection, and a
            # fully exited, clean scope. Otherwise require observed root rollback.
            settled = (cleanup_ok and not in_service_transaction(business_db)
                       and not business_db.in_transaction() and business_db.is_active
                       and ((len(roots) == 1 and roots[0] in rolled_back)
                            or (not roots and escaped)))
            if settled:
                session_id = id(business_db)
                transaction_id = id(roots[0]) if roots else 0
                bind_id = id(database_bind)
                try:
                    knowledge = recorder._new_event_knowledge(draft)
                    record = SettledRejection(draft, session_id, connection_id, transaction_id, bind_id,
                        recording_key, _fingerprint(draft, session_id, connection_id,
                            transaction_id, bind_id, recording_key, knowledge), knowledge)
                    operation.result = recorder.record_after_settlement(record)
                    operation.receipt = operation.result.receipt
                except Exception:
                    rejection_diagnostic("audit.rejection.persistence_failed", draft)
            else:
                rejection_diagnostic("audit.rejection.recording_deferred_unavailable", draft)


@contextmanager
def _application_audit_transaction(session_factory, record, storage):
    """Own one fresh audit-only Session/E02 root; never expose it to business code."""
    validate_settlement(record, record._owner if type(record) is SettledRejection else None)
    state = active_attempt()
    if (id(session_factory.kw.get("bind")) != record.database_bind_id
            or storage.business_bind is not session_factory.kw.get("bind")
            or storage.factory.kw.get("bind") is not storage.audit_bind):
        raise AuditValidationError("Audit database must match the settled business database.")
    audit_db = storage.factory()
    # Reject a faulty injected factory before closing or settling foreign state.
    if (id(audit_db) == record.business_session_id or audit_db.in_transaction()
            or not audit_db.is_active or audit_db.new or audit_db.dirty or audit_db.deleted
            or audit_db.get_bind() is not storage.audit_bind):
        raise AuditValidationError("Fresh same-database audit Session required.")

    def independent(_db, transaction, connection):
        if (id(transaction) == record.business_transaction_id
                or id(connection) == record.business_connection_id):
            raise AuditValidationError("Audit transaction must be independent.")

    session_event.listen(audit_db, "after_begin", independent)
    try:
        with service_transaction(audit_db):
            storage.configure(audit_db)
            yield audit_db
    finally:
        state.cleaning = True
        session_event.remove(audit_db, "after_begin", independent)
        audit_db.close()
