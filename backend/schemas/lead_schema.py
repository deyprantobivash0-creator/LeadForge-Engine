from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    company: str = Field(
        min_length=1,
        max_length=200,
    )

    email: EmailStr

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
    lead_score: int | None = None
    priority: str | None = None
    ai_reason: str | None = None
    next_action: str | None = None

    status: str
    notes: str | None = None

    last_contacted: datetime | None = None
    next_follow_up: datetime | None = None

    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    page: int
    page_size: int
    total: int
    pages: int