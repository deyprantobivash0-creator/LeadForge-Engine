from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.lead import Lead


class LeadImportRepository:
    def __init__(self, db: Session):
        self.db = db

    def existing_emails(self, organization_id: int, emails: set[str]) -> set[str]:
        if not emails:
            return set()
        return set(self.db.scalars(select(Lead.email).where(
            Lead.organization_id == organization_id, Lead.email.in_(emails),
        )).all())

    def add(self, organization_id: int, company: str, email: str, source: str) -> None:
        self.db.add(Lead(
            organization_id=organization_id,
            company=company,
            email=email,
            source=source,
        ))
        self.db.flush()
