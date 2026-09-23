from pydantic import BaseModel, Field


class IngestionResult(BaseModel):
    success: bool
    ingestion_id: int

    total_rows: int
    successful_rows: int
    duplicate_rows: int
    failed_rows: int

    errors: list[str] = Field(default_factory=list)


class LeadImportItem(BaseModel):
    company: str
    email: str
    source: str = "api"

    industry: str | None = None
    status: str | None = None
    notes: str | None = None

class LeadImportRequest(BaseModel):
    leads: list[LeadImportItem]