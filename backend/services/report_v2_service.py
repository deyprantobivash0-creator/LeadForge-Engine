from backend.core.logger import operation
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from backend.repositories.report_repository import ReportRepository


class ReportV2Service:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ReportRepository()

    @staticmethod
    def window(preset: str, start: date | None = None, end: date | None = None, now: datetime | None = None):
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        if preset == "custom":
            if start is None or end is None or start > end or (end - start).days >= 365:
                raise ValueError("Custom range requires start <= end and at most 365 calendar days")
            return datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)
        if start is not None or end is not None:
            raise ValueError("Date boundaries are only valid for a custom range")
        if preset == "today":
            return datetime.combine(now.date(), time.min), now
        if preset == "7d":
            return now - timedelta(days=7), now
        if preset == "30d":
            return now - timedelta(days=30), now
        raise ValueError("Invalid report preset")

    @staticmethod
    def event(row):
        return dict(analysis_id=row.id, lead_id=row.lead_id, company=row.company,
                    email=row.email, score=row.lead_score, priority=row.priority,
                    created_at=row.created_at)

    @operation("report.generate")
    def overview(self, organization_id: int, preset: str, start: date | None = None, end: date | None = None):
        first, last = self.window(preset, start, end)
        summary = self.repository.summary(self.db, organization_id, first, last)
        hourly = preset == "today" and first.date() == last.date()
        counts = {}
        for row in self.repository.activity(self.db, organization_id, first, last, hourly):
            parts = [int(value) for value in row[:-1]]
            bucket = datetime(*parts, *([0] if hourly else []))
            counts[bucket] = row[-1]
        cursor = first.replace(minute=0, second=0, microsecond=0) if hourly else datetime.combine(first.date(), time.min)
        step = timedelta(hours=1) if hourly else timedelta(days=1)
        activity = []
        while cursor < last:
            activity.append({"bucket": cursor, "analysis_events": counts.get(cursor, 0)})
            cursor += step
        return {
            "period": {"preset": preset, "start": first, "end": last, "timezone": "UTC"},
            "summary": summary,
            "activity": activity,
            "priority_distribution": {"Hot": summary["hot_events"], "Warm": summary["warm_events"],
                                      "Cold": summary["cold_events"], "Other": summary["other_priority_events"]},
            "top_opportunities": [self.event(row) for row in self.repository.top(self.db, organization_id, first, last)],
            "recent_analysis_events": [self.event(row) for row in self.repository.recent(self.db, organization_id, first, last)],
        }
