from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.models.lead_analysis import LeadAnalysis
from backend.models.lead import Lead


class LeadAnalysisRepository:

    @staticmethod
    def current_ranked_subquery(organization_id: int):
        """One rank per linked Lead; tie-break matches current-detail selection."""
        return (
            select(
                LeadAnalysis.organization_id.label("organization_id"),
                LeadAnalysis.lead_id.label("lead_id"),
                LeadAnalysis.id.label("analysis_id"),
                LeadAnalysis.lead_score.label("analysis_score"),
                LeadAnalysis.priority.label("analysis_priority"),
                LeadAnalysis.created_at.label("analysis_created_at"),
                func.row_number().over(
                    partition_by=(LeadAnalysis.organization_id, LeadAnalysis.lead_id),
                    order_by=(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc()),
                ).label("rank"),
            )
            .where(
                LeadAnalysis.organization_id == organization_id,
                LeadAnalysis.lead_id.is_not(None),
            )
            .subquery()
        )

    def create(
        self,
        db: Session,
        company: str,
        email: str,
        priority: str,
        lead_score: int,
        result: dict,
        organization_id: int,
        lead_id: int,
    ) -> LeadAnalysis:
        if not 0 <= lead_score <= 100:
            raise ValueError("Lead score must be between 0 and 100")
        if priority not in {"Hot", "Warm", "Cold"}:
            raise ValueError("Invalid priority")
        owner = db.scalar(select(Lead.id).where(
            Lead.id == lead_id, Lead.organization_id == organization_id,
        ))
        if owner is None:
            raise ValueError("Lead not found in organization")
        analysis = LeadAnalysis(
            company=company,
            email=email,
            priority=priority,
            lead_score=lead_score,
            result=result,
            organization_id=organization_id,
            lead_id=lead_id,
        )

        db.add(analysis)
        db.flush()

        return analysis

    def get_current_for_lead(
        self,
        db: Session,
        lead_id: int,
        organization_id: int,
    ) -> LeadAnalysis | None:
        return db.scalar(
            select(LeadAnalysis).where(
                LeadAnalysis.lead_id == lead_id,
                LeadAnalysis.organization_id == organization_id,
            ).order_by(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc()).limit(1)
        )

    def get_history_for_lead(
        self, db: Session, lead_id: int, organization_id: int,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[LeadAnalysis], int]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid history pagination")
        condition = (LeadAnalysis.organization_id == organization_id, LeadAnalysis.lead_id == lead_id)
        total = db.scalar(select(func.count(LeadAnalysis.id)).where(*condition)) or 0
        items = list(db.scalars(select(LeadAnalysis).where(*condition).order_by(
            LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc(),
        ).limit(limit).offset(offset)))
        return items, total

    def get_all(self, db: Session, organization_id: int) -> list[LeadAnalysis]:
        return list(db.scalars(
            select(LeadAnalysis)
            .where(LeadAnalysis.organization_id == organization_id)
            .order_by(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc())
        ))

    def count(self, db: Session, organization_id: int) -> int:
        return db.scalar(
            select(func.count(LeadAnalysis.id))
            .where(LeadAnalysis.organization_id == organization_id)
        )

    def count_by_priority(self, db: Session, organization_id: int, priority: str) -> int:
        return db.scalar(
            select(func.count(LeadAnalysis.id))
            .where(
                LeadAnalysis.organization_id == organization_id,
                LeadAnalysis.priority == priority,
            )
        )

    def average_lead_score(self, db: Session, organization_id: int) -> float:
        result = db.scalar(
            select(func.avg(LeadAnalysis.lead_score))
            .where(LeadAnalysis.organization_id == organization_id)
        )
        return round(result or 0, 2)

    @staticmethod
    def _date_predicates(start_date: datetime | None, end_date: datetime | None):
        if (start_date is None) != (end_date is None):
            raise ValueError("Both date boundaries are required")
        if start_date is None:
            return ()
        if start_date.tzinfo is not None or end_date.tzinfo is not None:
            raise ValueError("Date boundaries must use stored naïve UTC")
        if start_date >= end_date:
            raise ValueError("End date must be after start date")
        return (
            LeadAnalysis.created_at >= start_date,
            LeadAnalysis.created_at < end_date,
        )

    def summary(
        self,
        db: Session,
        organization_id: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        predicates = self._date_predicates(start_date, end_date)
        total, hot, warm, cold, average = db.execute(
            select(
                func.count(LeadAnalysis.id),
                func.coalesce(func.sum(case((LeadAnalysis.priority == "Hot", 1), else_=0)), 0),
                func.coalesce(func.sum(case((LeadAnalysis.priority == "Warm", 1), else_=0)), 0),
                func.coalesce(func.sum(case((LeadAnalysis.priority == "Cold", 1), else_=0)), 0),
                func.avg(LeadAnalysis.lead_score),
            ).where(LeadAnalysis.organization_id == organization_id, *predicates)
        ).one()
        return {
            "total_leads": total,
            "hot_leads": hot,
            "warm_leads": warm,
            "cold_leads": cold,
            "average_lead_score": round(average or 0, 2),
        }

    def top_by_score(
        self,
        db: Session,
        organization_id: int,
        limit: int,
        priority: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[LeadAnalysis]:
        if limit < 1:
            raise ValueError("Limit must be positive")
        predicates = self._date_predicates(start_date, end_date)
        if priority is not None:
            predicates += (LeadAnalysis.priority == priority,)
        return list(db.scalars(
            select(LeadAnalysis)
            .where(LeadAnalysis.organization_id == organization_id, *predicates)
            .order_by(LeadAnalysis.lead_score.desc(), LeadAnalysis.id.desc())
            .limit(limit)
        ))

    def recent(
        self,
        db: Session,
        organization_id: int,
        limit: int,
        priority: str | None = None,
    ) -> list[LeadAnalysis]:
        if limit < 1:
            raise ValueError("Limit must be positive")
        predicates = (LeadAnalysis.priority == priority,) if priority is not None else ()
        return list(db.scalars(
            select(LeadAnalysis)
            .where(LeadAnalysis.organization_id == organization_id, *predicates)
            .order_by(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc())
            .limit(limit)
        ))

    def get_between_dates(
        self,
        db: Session,
        organization_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> list[LeadAnalysis]:
        predicates = self._date_predicates(start_date, end_date)
        return list(db.scalars(
            select(LeadAnalysis)
            .where(LeadAnalysis.organization_id == organization_id, *predicates)
            .order_by(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc())
        ))
