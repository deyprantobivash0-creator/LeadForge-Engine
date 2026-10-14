"""Append-only internal persistence; no authorization, settlement or live wiring."""

from datetime import datetime, timezone

from sqlalchemy import select

from backend.database.transactions import in_service_transaction
from backend.models.audit_event import AuditEvent
from backend.schemas.audit_event import (
    AuditEventReceipt, AuditValidationError, canonical_event_id, positive_identifier, audit_persistence_values,
)


class AuditRepository:
    def __init__(self, db):
        self.db = db

    def append(self, draft) -> AuditEventReceipt:
        """Join the caller's E02 scope, add/flush only. Receipt is provisional.

        No dict or caller-created ORM input is accepted. No mutable ORM object
        is returned. Caller/root transaction alone determines durability.
        """
        values = audit_persistence_values(draft, recorded_at=datetime.now(timezone.utc))
        if not in_service_transaction(self.db):
            raise AuditValidationError("Caller-owned service transaction required for audit append.")
        item = AuditEvent(**values)
        self.db.add(item)
        self.db.flush()
        return AuditEventReceipt(item.event_id, item.organization_id, item.occurred_at, item.recorded_at)

    def get_event(self, organization_id, event_id) -> AuditEventReceipt | None:
        """One scoped row, no membership inference, live joins or payload exposure.

        Scalar projection avoids returning a tracked, mutable AuditEvent.
        No list/unbounded history/cursor/API is needed in this slice.
        """
        positive_identifier(organization_id)
        canonical_event_id(event_id)
        row = self.db.execute(select(AuditEvent.event_id, AuditEvent.organization_id,
                              AuditEvent.occurred_at, AuditEvent.recorded_at).where(
                              AuditEvent.organization_id == organization_id,
                              AuditEvent.event_id == event_id).limit(1)).one_or_none()
        return AuditEventReceipt(*row) if row is not None else None
