from pydantic import BaseModel, Field


class CompanyIntelligence(BaseModel):
    company_name: str
    industry: str | None = None
    company_size: str | None = None
    business_model: str | None = None
    likely_needs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
