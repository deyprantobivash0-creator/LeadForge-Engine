"""Human-reported later evidence, never a replacement for a decision snapshot."""
from datetime import datetime
from enum import StrEnum
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, UUID4, field_validator


class OutcomeKind(StrEnum):
    CONTACTED = "Contacted"
    QUALIFIED = "Qualified"
    MEETING = "Meeting"
    WON = "Won"
    LOST = "Lost"


class OutcomeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")
    kind: OutcomeKind
    observed_at: AwareDatetime
    note: str | None = Field(default=None, max_length=1000, strict=True)

    @field_validator("note")
    @classmethod
    def safe_note(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("Invalid outcome note.")
        return value


class OutcomeRecord(OutcomeInput):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)
    id: UUID4
    organization_id: int
    lead_id: int
    decision_id: UUID4
    recorded_by_user_id: int
    recorded_at: AwareDatetime
    source: str = "manual_user_report"


class OutcomeHistory(BaseModel):
    items: list[OutcomeRecord]
    total: int
    limit: int
    offset: int
    effectiveness: str
