from sqlalchemy.orm import Session

from backend.repositories.lead_analysis_repository import (
    LeadAnalysisRepository,
)


class AnalysisService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = LeadAnalysisRepository()

    def save_analysis(
        self, *, organization_id: int, lead_id: int, company: str,
        email: str, result: dict,
    ):
        if not isinstance(result, dict):
            raise ValueError("Analysis result must be an object")
        decision = result.get("final_decision")
        if not isinstance(decision, dict):
            raise ValueError("Analysis final_decision is required")
        priority = decision.get("priority")
        score = decision.get("lead_score")
        if priority not in {"Hot", "Warm", "Cold"} or type(score) is not int or not 0 <= score <= 100:
            raise ValueError("Analysis decision is invalid")
        return self.repository.create(
            db=self.db, company=company, email=email,
            priority=priority, lead_score=score, result=result,
            organization_id=organization_id, lead_id=lead_id,
        )
