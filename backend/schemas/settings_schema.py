from typing import Literal

from pydantic import BaseModel


class SettingsAccount(BaseModel):
    email: str


class SettingsWorkspace(BaseModel):
    id: int
    name: str
    slug: str
    role: Literal["owner", "admin", "member"]


class AIStatus(BaseModel):
    provider: Literal["mock", "gemini", "ollama", "deepseek", "unsupported"]
    display_name: str
    configured: bool
    processing_available: bool
    status: Literal["development_only", "configuration_ready", "configuration_required", "not_available"]
    detail: str


class SettingsCapabilities(BaseModel):
    csv_import: bool
    historical_reports: bool
    report_csv_export: bool
    crm_sync: bool
    automation_integration: bool


class SettingsOverview(BaseModel):
    account: SettingsAccount
    workspace: SettingsWorkspace
    ai: AIStatus
    capabilities: SettingsCapabilities
