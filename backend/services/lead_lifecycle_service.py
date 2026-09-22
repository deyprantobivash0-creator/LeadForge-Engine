from datetime import datetime

from sqlalchemy.orm import Session

from backend.repositories.lead_repository import LeadRepository


class LeadLifecycleService:

    ALLOWED_STATUSES = {
        "New",
        "Qualified",
        "Contacted",
        "Meeting",
        "Won",
        "Lost",
    }

    def __init__(self, db: Session):
        self.repository = LeadRepository(db)

    def update_status(
        self,
        lead_id: int,
        organization_id: int,
        status: str,
    ):

        if status not in self.ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status: {status}"
            )

        return self.repository.update_status(
            lead_id=lead_id,
            organization_id=organization_id,
            status=status,
        )

    def update_lifecycle(
        self,
        lead_id: int,
        organization_id: int,
        status: str | None = None,
        notes: str | None = None,
        last_contacted: datetime | None = None,
        next_follow_up: datetime | None = None,
    ):

        if status is not None and status not in self.ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status: {status}"
            )

        return self.repository.update_lifecycle(
            lead_id=lead_id,
            organization_id=organization_id,
            status=status,
            notes=notes,
            last_contacted=last_contacted,
            next_follow_up=next_follow_up,
        )

    def get_follow_ups(
        self,
        organization_id: int,
        days: int = 7,
        page: int = 1,
        page_size: int = 50,
    ):
        return self.repository.get_follow_up_leads(
            organization_id=organization_id,
            days=days,
            page=page,
            page_size=page_size,
        )