from sqlalchemy.orm import Session

from backend.repositories.lead_analysis_repository import (
    LeadAnalysisRepository,
)


class AnalysisService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadAnalysisRepository()

    def save_analysis(
        self,
        company: str,
        email: str,
        result: dict,
    ):

        final_decision = result.get(
            "final_decision",
            {},
        )

        priority = final_decision.get(
            "priority",
            "Unknown",
        )

        lead_score = final_decision.get(
            "lead_score",
            0,
        )

        return self.repository.create(
            db=self.db,
            company=company,
            email=email,
            priority=priority,
            lead_score=lead_score,
            result=result,
        )