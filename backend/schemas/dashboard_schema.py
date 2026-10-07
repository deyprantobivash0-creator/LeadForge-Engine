"""Executive Dashboard contract: current Lead snapshot plus analysis events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.schemas.lead_contract import LeadLifecycle, LeadPriority, ProcessingStatus


class PipelineSnapshot(BaseModel):
    total_leads: int = Field(ge=0)
    analyzed_leads: int = Field(ge=0)
    unanalyzed_leads: int = Field(ge=0)
    average_current_score: float | None = Field(default=None, ge=0, le=100)


class PriorityDistribution(BaseModel):
    Hot: int = Field(ge=0)
    Warm: int = Field(ge=0)
    Cold: int = Field(ge=0)
    Unanalyzed: int = Field(ge=0)


class LifecycleDistribution(BaseModel):
    New: int = Field(ge=0)
    Qualified: int = Field(ge=0)
    Contacted: int = Field(ge=0)
    Meeting: int = Field(ge=0)
    Won: int = Field(ge=0)
    Lost: int = Field(ge=0)


class ProcessingDistribution(BaseModel):
    pending: int = Field(ge=0)
    processing: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)


class CurrentOpportunity(BaseModel):
    lead_id: int
    company: str
    status: LeadLifecycle
    processing_status: ProcessingStatus
    lead_score: int = Field(ge=0, le=100)
    priority: LeadPriority


class AnalysisActivity(BaseModel):
    analysis_id: int
    lead_id: int | None
    company: str
    lead_score: int = Field(ge=0, le=100)
    # Historical, unlinked records predate the canonical Hot/Warm/Cold policy.
    # Preserve their exact stored label without treating it as current priority.
    priority: LeadPriority | Literal["High", "Unknown"]
    created_at: datetime


class DashboardOverviewResponse(BaseModel):
    pipeline: PipelineSnapshot
    priority_distribution: PriorityDistribution
    lifecycle_distribution: LifecycleDistribution
    processing_distribution: ProcessingDistribution
    top_opportunities: list[CurrentOpportunity]
    recent_analysis_activity: list[AnalysisActivity]


class LegacyDashboardLead(BaseModel):
    id: int
    company: str
    email: str
    priority: LeadPriority
    lead_score: int = Field(ge=0, le=100)


class LegacyDashboardRecentLead(LegacyDashboardLead):
    created_at: datetime


class LegacyDashboardOverviewResponse(BaseModel):
    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    average_lead_score: float
    top_opportunities: list[LegacyDashboardLead]
    recent_analyses: list[LegacyDashboardRecentLead]
