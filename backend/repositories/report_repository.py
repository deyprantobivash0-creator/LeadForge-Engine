from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.models.lead_analysis import LeadAnalysis


class ReportRepository:
    @staticmethod
    def _scope(organization_id: int, start: datetime, end: datetime):
        return (
            LeadAnalysis.organization_id == organization_id,
            LeadAnalysis.created_at >= start,
            LeadAnalysis.created_at < end,
        )

    def summary(self, db: Session, organization_id: int, start: datetime, end: datetime) -> dict:
        total, unique, average, hot, warm, cold = db.execute(select(
            func.count(LeadAnalysis.id),
            func.count(func.distinct(LeadAnalysis.lead_id)),
            func.avg(LeadAnalysis.lead_score),
            func.coalesce(func.sum(case((LeadAnalysis.priority == "Hot", 1), else_=0)), 0),
            func.coalesce(func.sum(case((LeadAnalysis.priority == "Warm", 1), else_=0)), 0),
            func.coalesce(func.sum(case((LeadAnalysis.priority == "Cold", 1), else_=0)), 0),
        ).where(*self._scope(organization_id, start, end))).one()
        return dict(analysis_events=total, unique_analyzed_leads=unique,
                    average_analysis_score=round(average, 2) if average is not None else None,
                    hot_events=hot, warm_events=warm, cold_events=cold,
                    other_priority_events=total - hot - warm - cold)

    def activity(self, db: Session, organization_id: int, start: datetime, end: datetime, hourly: bool):
        # strftime is SQLite-specific. Group by a half-open bucket boundary in
        # Python only after the SQL tenant/date aggregation has bounded rows.
        # PostgreSQL needs date_trunc; use portable SQL extraction instead.
        fields = [func.extract("year", LeadAnalysis.created_at),
                  func.extract("month", LeadAnalysis.created_at),
                  func.extract("day", LeadAnalysis.created_at)]
        if hourly:
            fields.append(func.extract("hour", LeadAnalysis.created_at))
        return db.execute(select(*fields, func.count(LeadAnalysis.id)).where(
            *self._scope(organization_id, start, end)
        ).group_by(*fields).order_by(*fields)).all()

    def top(self, db: Session, organization_id: int, start: datetime, end: datetime, limit: int = 5):
        scoped = self._scope(organization_id, start, end)
        ranked = select(
            LeadAnalysis.id.label("analysis_id"),
            func.row_number().over(
                partition_by=LeadAnalysis.lead_id,
                order_by=(LeadAnalysis.lead_score.desc(), LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc()),
            ).label("rank"),
        ).where(*scoped, LeadAnalysis.lead_id.is_not(None)).subquery()
        return db.scalars(select(LeadAnalysis).join(ranked, LeadAnalysis.id == ranked.c.analysis_id)
                          .where(ranked.c.rank == 1, LeadAnalysis.organization_id == organization_id)
                          .order_by(LeadAnalysis.lead_score.desc(), LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc())
                          .limit(limit)).all()

    def recent(self, db: Session, organization_id: int, start: datetime, end: datetime, limit: int = 10):
        return db.scalars(select(LeadAnalysis).where(*self._scope(organization_id, start, end))
                          .order_by(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc()).limit(limit)).all()

    def export_batches(self, db: Session, organization_id: int, start: datetime, end: datetime):
        # yield_per keeps memory bounded while exporting the entire selected period.
        statement = select(LeadAnalysis.id, LeadAnalysis.lead_id, LeadAnalysis.company,
                           LeadAnalysis.email, LeadAnalysis.lead_score, LeadAnalysis.priority,
                           LeadAnalysis.created_at).where(*self._scope(organization_id, start, end)).order_by(
                               LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc())
        yield from db.execute(statement.execution_options(yield_per=500))
