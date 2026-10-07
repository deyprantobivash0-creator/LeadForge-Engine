from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.schemas.lead_contract import LeadLifecycle


LeadStatus = LeadLifecycle


class LeadLifecycleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("notes")
    @classmethod
    def reject_nul(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("Text must not contain NUL bytes")
        return value

    status: LeadStatus | None = None

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    last_contacted: datetime | None = None

    next_follow_up: datetime | None = None
