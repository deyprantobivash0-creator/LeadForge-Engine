from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.lead_analysis import LeadAnalysis


class LeadAnalysisRepository:

    def create(
        self,
        db: Session,
        company: str,
        email: str,
        priority: str,
        lead_score: int,
        result: dict,
        organization_id: int,
    ) -> LeadAnalysis:

        analysis = LeadAnalysis(
            company=company,
            email=email,
            priority=priority,
            lead_score=lead_score,
            result=result,
            organization_id=organization_id,
        )

        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        return analysis

    def get_by_lead_email(
        self,
        db: Session,
        email: str,
        organization_id: int,
       ) -> LeadAnalysis | None:

     return (
        db.query(LeadAnalysis)
        .filter(
            LeadAnalysis.email == email,
            LeadAnalysis.organization_id == organization_id,
        )
        .first()
    )

    def get_all(
        self,
        db: Session,
    ) -> list[LeadAnalysis]:

        return (
            db.query(LeadAnalysis)
            .order_by(LeadAnalysis.created_at.desc())
            .all()
        )

    def count(
        self,
        db: Session,
    ) -> int:

        return (
            db.query(LeadAnalysis)
            .count()
        )

    def count_by_priority(
        self,
        db: Session,
        priority: str,
    ) -> int:

        return (
            db.query(LeadAnalysis)
            .filter(
                LeadAnalysis.priority == priority
            )
            .count()
        )

    def average_lead_score(
        self,
        db: Session,
    ) -> float:

        result = (
            db.query(
                func.avg(LeadAnalysis.lead_score)
            )
            .scalar()
        )

        return round(result or 0, 2)

    def get_between_dates(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime,
    ) -> list[LeadAnalysis]:

        return (
            db.query(LeadAnalysis)
            .filter(
                LeadAnalysis.created_at >= start_date,
                LeadAnalysis.created_at < end_date,
            )
            .order_by(
                LeadAnalysis.created_at.desc()
            )
            .all()
        )