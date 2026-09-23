from sqlalchemy.orm import Session

from backend.models.lead import Lead


class LeadDeduplicationService:

    def __init__(self, db: Session):
        self.db = db

    def exists(
        self,
        organization_id: int,
        email: str,
    ) -> bool:

        return (
            self.db.query(Lead)
            .filter(
                Lead.organization_id == organization_id,
                Lead.email == email,
            )
            .first()
            is not None
        )