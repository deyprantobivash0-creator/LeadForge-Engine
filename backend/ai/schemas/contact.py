from pydantic import BaseModel, Field


class ContactIntelligence(BaseModel):
    contact_name: str | None = None
    role: str | None = None
    seniority: str | None = None
    likely_decision_maker: bool = False
    likely_responsibilities: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)