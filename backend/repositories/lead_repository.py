from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.lead import Lead


class LeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_lead(self, lead: Lead) -> Lead:
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def get_all_leads(
        self,
        organization_id: int,
        page: int = 1,
        page_size: int = 50,
    ):
        query = (
            self.db.query(Lead)
            .filter(Lead.organization_id == organization_id)
        )

        total = query.count()

        offset = (page - 1) * page_size

        items = (
            query
            .order_by(Lead.id.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return items, total

    def get_lead_by_id(
        self,
        lead_id: int,
        organization_id: int,
    ) -> Lead | None:
        return (
            self.db.query(Lead)
            .filter(
                Lead.id == lead_id,
                Lead.organization_id == organization_id,
            )
            .first()
        )

    def get_lead_by_email(
        self,
        email: str,
        organization_id: int,
    ) -> Lead | None:
        return (
            self.db.query(Lead)
            .filter(
                Lead.email == email,
                Lead.organization_id == organization_id,
            )
            .first()
        )

    def search_leads(
        self,
        organization_id: int,
        company: str | None = None,
        email: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ):
        query = (
            self.db.query(Lead)
            .filter(Lead.organization_id == organization_id)
        )

        if company:
            query = query.filter(
                Lead.company.ilike(f"%{company}%")
            )

        if email:
            query = query.filter(
                Lead.email.ilike(f"%{email}%")
            )

        total = query.count()

        offset = (page - 1) * page_size

        items = (
            query
            .order_by(Lead.id.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return items, total

    def update_status(
        self,
        lead_id: int,
        organization_id: int,
        status: str,
    ) -> Lead | None:
        lead = self.get_lead_by_id(
            lead_id=lead_id,
            organization_id=organization_id,
        )

        if not lead:
            return None

        lead.status = status

        self.db.commit()
        self.db.refresh(lead)

        return lead

    def update_lifecycle(
        self,
        lead_id: int,
        organization_id: int,
        status: str | None = None,
        notes: str | None = None,
        last_contacted: datetime | None = None,
        next_follow_up: datetime | None = None,
    ) -> Lead | None:

        lead = self.get_lead_by_id(
            lead_id=lead_id,
            organization_id=organization_id,
        )

        if not lead:
            return None

        if status is not None:
            lead.status = status

        if notes is not None:
            lead.notes = notes

        if last_contacted is not None:
            lead.last_contacted = last_contacted

        if next_follow_up is not None:
            lead.next_follow_up = next_follow_up

        self.db.commit()
        self.db.refresh(lead)

        return lead

    def get_follow_up_leads(
        self,
        organization_id: int,
        days: int = 7,
        page: int = 1,
        page_size: int = 50,
    ):
        now = datetime.utcnow()
        end_date = now + timedelta(days=days)

        query = (
            self.db.query(Lead)
            .filter(
                Lead.organization_id == organization_id,
                Lead.next_follow_up.is_not(None),
                Lead.next_follow_up >= now,
                Lead.next_follow_up <= end_date,
            )
        )

        total = query.count()

        offset = (page - 1) * page_size

        items = (
            query
            .order_by(Lead.next_follow_up.asc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return items, total