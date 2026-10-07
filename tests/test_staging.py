"""Staging deployment-sensitive policy checks; no remote resources or real provider."""
import pytest
from pydantic import ValidationError
from backend.core.config import Settings
from backend.ai.providers.base import ProviderNotConfigured
from backend.ai.providers.router import AIRouter
from scripts.staging import hostname, render_proxy, source_paths


def config(**values):
    defaults = dict(ENVIRONMENT="production", AI_PROVIDER="mock", LEADFORGE_STAGING=True,
        DATABASE_URL="postgresql+psycopg://runtime:synthetic-staging-test-password@postgres/stage",
        CORS_ORIGINS="https://staging.example.com")
    return Settings(_env_file=None, **(defaults | values))


def test_staging_opt_in_enables_mock_only(monkeypatch):
    import backend.ai.providers.router as router
    monkeypatch.setattr(router, "settings", config())
    assert type(AIRouter().get_provider()).__name__ == "MockProvider"
    monkeypatch.setattr(router, "settings", config(LEADFORGE_STAGING=False))
    with pytest.raises(ProviderNotConfigured):
        AIRouter().get_provider()


def test_settings_reports_staging_mock_truthfully(monkeypatch):
    import backend.services.settings_service as service
    monkeypatch.setattr(service, "settings", config())
    summary = service.SettingsService.ai_status()
    assert summary["processing_available"] and summary["display_name"] == "Staging Mock"
    assert "Synthetic staging" in summary["detail"]


@pytest.mark.parametrize("values", [{"ENVIRONMENT": "development"}, {"ENVIRONMENT": "test"},
    {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "synthetic-key"},
    {"SESSION_COOKIE_SECURE": False}, {"RATE_LIMIT_ENABLED": False},
    {"LOG_LEVEL": "DEBUG"}, {"CORS_ORIGINS": "http://staging.example.com"},
    {"DATABASE_URL": "sqlite:///:memory:"}])
def test_staging_does_not_bypass_strict_configuration(values):
    with pytest.raises(ValidationError):
        config(**values)


@pytest.mark.parametrize("value", ["https://stage.example.com", "*.example.com", "stage.example.com:443", "stage.example.com;", "localhost", "Stage.example.com", "stage.example.com/", "stage.example.com\n"])
def test_proxy_hostname_cannot_inject_configuration(value):
    with pytest.raises(ValueError):
        hostname(value)


def test_tls_render_reuses_security_policy_and_strips_untrusted_headers():
    proxy, headers = render_proxy("staging.example.com")
    assert "listen 8443 ssl" in proxy and "TLSv1.2 TLSv1.3" in proxy
    assert 'if ($host != "staging.example.com") { return 400; }' in proxy
    assert "return 308 https://staging.example.com$request_uri" in proxy
    assert 'proxy_set_header X-Forwarded-For $remote_addr' in proxy
    assert 'proxy_set_header X-Forwarded-Proto $scheme' in proxy
    assert 'proxy_set_header Forwarded ""' in proxy
    assert "noindex, nofollow, noarchive" in headers
    assert "max-age=86400" in headers and "includeSubDomains" not in headers and "preload" not in headers
    assert "Content-Security-Policy" in headers


def test_snapshot_paths_exclude_private_and_generated_files():
    paths = list(source_paths())
    assert paths
    for path in paths:
        assert not any(part.startswith(".env") or part in {"secrets", "backups", "node_modules", "dist"} for part in path.parts)
        assert path.suffix not in {".db", ".dump", ".pem", ".key", ".pyc"}
