from pydantic import BaseModel, Field


class IntentIntelligence(BaseModel):
    intent: str = "unknown"
    urgency: str = "unknown"
    buying_signal: str = "unknown"
    pain_points: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)