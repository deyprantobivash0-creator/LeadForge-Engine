from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from backend.schemas.lead_contract import LeadLifecycle, LeadPriority, ProcessingStatus


class AnalysisResponse(BaseModel):
    id: int
    lead_id: int | None
    priority: LeadPriority
    lead_score: int = Field(ge=0, le=100)
    result: dict
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LeadIntelligenceResponse(BaseModel):
    id: int
    company: str
    email: EmailStr
    source: str
    analysis: AnalysisResponse | None


class AnalysisHistoryResponse(BaseModel):
    items: list[AnalysisResponse]
    total: int
    limit: int
    offset: int


class LeadProcessingResponse(BaseModel):
    lead_id: int
    processing_status: ProcessingStatus
    analysis: AnalysisResponse | None
    error: str | None = None


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("company", "source")
    @classmethod
    def reject_nul(cls, value):
        if "\x00" in value:
            raise ValueError("Text must not contain NUL bytes")
        return value

    company: str = Field(
        min_length=1,
        max_length=200,
    )

    email: EmailStr = Field(max_length=200)

    source: str = Field(
        min_length=1,
        max_length=100,
    )


class LeadResponse(BaseModel):
    id: int
    company: str
    email: EmailStr
    source: str

    industry: str | None = None
    lead_score: int | None = Field(default=None, ge=0, le=100)
    priority: LeadPriority | None = None
    ai_reason: str | None = None
    next_action: str | None = None

    status: LeadLifecycle
    processing_status: ProcessingStatus
    notes: str | None = None

    last_contacted: datetime | None = None
    next_follow_up: datetime | None = None

    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class LeadAnalysisSummary(BaseModel):
    id: int
    lead_score: int = Field(ge=0, le=100)
    priority: LeadPriority


class LeadListItemResponse(LeadResponse):
    current_analysis: LeadAnalysisSummary | None = None


class LeadListResponse(BaseModel):
    items: list[LeadListItemResponse]
    page: int
    page_size: int
    total: int
    pages: int


class LeadDetailResponse(LeadResponse):
    current_analysis: AnalysisResponse | None = None
