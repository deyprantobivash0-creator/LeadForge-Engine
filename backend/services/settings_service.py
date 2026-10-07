"""Safe customer-facing configuration summary; no provider construction or I/O."""

from backend.core.config import settings
from backend.services.organization_authorization_service import AuthorizedOrganizationContext


class SettingsService:
    @staticmethod
    def ai_status() -> dict:
        provider = settings.AI_PROVIDER.lower().strip()
        if provider == "mock":
            available = settings.ENVIRONMENT.lower() in {"development", "test"} or settings.LEADFORGE_STAGING
            return {
                "provider": "mock", "display_name": "Staging Mock" if settings.LEADFORGE_STAGING else "Development Mock",
                "configured": available, "processing_available": available,
                "status": "configuration_ready" if settings.LEADFORGE_STAGING else ("development_only" if available else "not_available"),
                "detail": "Synthetic staging assessments only." if settings.LEADFORGE_STAGING else ("Local development assessments only." if available else "Development provider is disabled here."),
            }
        if provider == "gemini":
            configured = bool(settings.GEMINI_API_KEY and settings.GEMINI_MODEL)
            return {
                "provider": "gemini", "display_name": "Gemini",
                "configured": configured, "processing_available": configured,
                "status": "configuration_ready" if configured else "configuration_required",
                "detail": "Server configuration is present; connectivity is unverified." if configured else "Server configuration is required.",
            }
        if provider == "ollama":
            configured = bool(settings.OLLAMA_HOST and settings.OLLAMA_MODEL)
            return {
                "provider": "ollama", "display_name": "Ollama",
                "configured": configured, "processing_available": configured,
                "status": "configuration_ready" if configured else "configuration_required",
                "detail": "Local configuration is present; model availability is unverified." if configured else "Local configuration is required.",
            }
        if provider == "deepseek":
            return {
                "provider": "deepseek", "display_name": "DeepSeek",
                "configured": False, "processing_available": False,
                "status": "not_available", "detail": "Not available in this release.",
            }
        return {
            "provider": "unsupported", "display_name": "Unrecognized provider",
            "configured": False, "processing_available": False,
            "status": "not_available", "detail": "Not available in this release.",
        }

    @classmethod
    def overview(cls, context: AuthorizedOrganizationContext) -> dict:
        return {
            "account": {"email": context.user.email},
            "workspace": {"id": context.organization.id, "name": context.organization.name,
                          "slug": context.organization.slug, "role": context.membership.role},
            "ai": cls.ai_status(),
            "capabilities": {
                "csv_import": True, "historical_reports": True, "report_csv_export": True,
                "crm_sync": False, "automation_integration": False,
            },
        }
