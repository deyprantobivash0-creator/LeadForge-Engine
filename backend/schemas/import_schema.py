from typing import Literal

from pydantic import BaseModel


class ImportRow(BaseModel):
    row_number: int
    company: str
    email: str
    source: str
    status: Literal["ready", "duplicate", "invalid"]
    errors: list[str]


class ImportSummary(BaseModel):
    total: int
    ready: int
    duplicates: int
    invalid: int


class ImportPreview(BaseModel):
    token: str
    summary: ImportSummary
    rows: list[ImportRow]
    preview_limit: int
    ignored_headers: list[str]


class ImportResult(BaseModel):
    total: int
    imported: int
    duplicates: int
    invalid: int
