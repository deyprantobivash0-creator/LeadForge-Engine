from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ReportPeriod(BaseModel):
    preset: Literal["today", "7d", "30d", "custom"]
    start: datetime
    end: datetime
    timezone: Literal["UTC"] = "UTC"


class ReportSummary(BaseModel):
    analysis_events: int
    unique_analyzed_leads: int
    average_analysis_score: float | None
    hot_events: int
    warm_events: int
    cold_events: int
    other_priority_events: int


class ActivityBucket(BaseModel):
    bucket: datetime
    analysis_events: int


class ReportEvent(BaseModel):
    analysis_id: int
    lead_id: int | None
    company: str
    email: str
    score: int
    priority: str
    created_at: datetime


class ReportV2Response(BaseModel):
    period: ReportPeriod
    summary: ReportSummary
    activity: list[ActivityBucket]
    priority_distribution: dict[str, int]
    top_opportunities: list[ReportEvent]
    recent_analysis_events: list[ReportEvent]
