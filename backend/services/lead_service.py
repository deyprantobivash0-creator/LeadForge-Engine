from sqlalchemy.orm import Session

from backend.models.lead import Lead
from backend.repositories.lead_repository import LeadRepository


class LeadService:
    def __init__(self, db: Session):
        self.repository = LeadRepository(db)

    def create_lead(
        self,
        company: str,
        email: str,
        source: str,
        organization_id: int,
    ) -> Lead:

        existing = self.repository.get_lead_by_email(
            email=email,
            organization_id=organization_id,
        )

        if existing:
            raise ValueError(
                "A lead with this email already exists "
                "in this organization."
            )

        lead = Lead(
            company=company,
            email=email,
            source=source,
            organization_id=organization_id,
        )

        return self.repository.create_lead(lead)

    def get_leads(
        self,
        organization_id: int,
        page: int = 1,
        page_size: int = 50,
    ):
        return self.repository.get_all_leads(
            organization_id=organization_id,
            page=page,
            page_size=page_size,
        )

    def get_lead(
        self,
        lead_id: int,
        organization_id: int,
    ):
        return self.repository.get_lead_by_id(
            lead_id=lead_id,
            organization_id=organization_id,
        )

    def search_leads(
        self,
        organization_id: int,
        company: str | None = None,
        email: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ):
        return self.repository.search_leads(
            organization_id=organization_id,
            company=company,
            email=email,
            page=page,
            page_size=page_size,
        )

    def get_follow_up_leads(
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