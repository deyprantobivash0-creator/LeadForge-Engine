"""Atomic tenant-scoped processing claims and attempt-guarded transitions."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from backend.models.lead import Lead


LEASE_MINUTES = 15


def utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LeadProcessingRepository:
    def claim(self, db: Session, organization_id: int, lead_id: int) -> str | None:
        now = utc_naive_now()
        attempt_id = str(uuid4())
        result = db.execute(
            update(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == organization_id,
                or_(
                    Lead.processing_status != "processing",
                    Lead.processing_started_at.is_(None),
                    Lead.processing_started_at < now - timedelta(minutes=LEASE_MINUTES),
                ),
            ).values(
                processing_status="processing",
                processing_started_at=now,
                processing_attempt_id=attempt_id,
            )
        )
        return attempt_id if result.rowcount == 1 else None

    def complete(
        self, db: Session, organization_id: int, lead_id: int,
        attempt_id: str, score: int, priority: str, reason: str, action: str,
    ) -> bool:
        result = db.execute(update(Lead).where(
            Lead.id == lead_id,
            Lead.organization_id == organization_id,
            Lead.processing_status == "processing",
            Lead.processing_attempt_id == attempt_id,
        ).values(
            processing_status="completed", processing_started_at=None,
            processing_attempt_id=None, lead_score=score, priority=priority,
            ai_reason=reason[:1000], next_action=action[:500],
        ))
        return result.rowcount == 1

    def fail(self, db: Session, organization_id: int, lead_id: int, attempt_id: str) -> bool:
        result = db.execute(update(Lead).where(
            Lead.id == lead_id,
            Lead.organization_id == organization_id,
            Lead.processing_status == "processing",
            Lead.processing_attempt_id == attempt_id,
        ).values(
            processing_status="failed", processing_started_at=None,
            processing_attempt_id=None,
        ))
        return result.rowcount == 1
