from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.core.config import settings
from backend.database.session import SessionLocal
from backend.main import app
from backend.models import OrganizationMembership


def headers(workspace, tenant):
    return {"X-Organization-ID": str(workspace["ids"]["organizations"][tenant])}


def test_settings_auth_role_and_tenant_scope(tenant_workspace):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    with TestClient(app, base_url="https://testserver") as anonymous:
        assert anonymous.get("/api/settings/overview", headers=headers(workspace, "a")).status_code == 401
    assert client.get("/api/settings/overview").status_code == 400
    assert client.get("/api/settings/overview", headers=headers(workspace, "b")).status_code == 403
    response = client.get("/api/settings/overview", headers=headers(workspace, "a"))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["account"] == {"email": "user-a@example.com"}
    assert body["workspace"] == {"id": workspace["ids"]["organizations"]["a"],
                                 "name": "Tenant A", "slug": "tenant-a", "role": "owner"}
    assert body["capabilities"]["csv_import"] is True
    assert body["capabilities"]["crm_sync"] is False
    assert "Tenant B" not in response.text
    admin = workspace["clients"]["admin"].get("/api/settings/overview", headers=headers(workspace, "a"))
    assert admin.json()["workspace"]["role"] == "admin"
    with SessionLocal() as db:
        membership = db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.user_id == workspace["ids"]["users"]["a"],
            OrganizationMembership.organization_id == workspace["ids"]["organizations"]["a"],
        ))
        membership.is_active = False
        db.commit()
    assert client.get("/api/settings/overview", headers=headers(workspace, "a")).status_code == 403


def test_settings_provider_status_and_secret_leakage(tenant_workspace, monkeypatch):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    marker = "TEST-SECRET-MUST-NOT-LEAK"
    monkeypatch.setattr(settings, "GEMINI_API_KEY", marker)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", marker)
    monkeypatch.setattr(settings, "HUBSPOT_ACCESS_TOKEN", marker)
    monkeypatch.setattr(settings, "OLLAMA_HOST", marker)
    monkeypatch.setattr(settings, "GEMINI_MODEL", marker)
    for provider, configured, expected_status in [
        ("mock", True, "development_only"),
        ("gemini", True, "configuration_ready"),
        ("ollama", True, "configuration_ready"),
        ("deepseek", False, "not_available"),
        ("unsupported", False, "not_available"),
    ]:
        monkeypatch.setattr(settings, "AI_PROVIDER", provider)
        response = client.get("/api/settings/overview", headers=headers(workspace, "a"))
        assert response.status_code == 200
        assert response.json()["ai"]["configured"] is configured
        assert response.json()["ai"]["status"] == expected_status
        assert marker not in response.text
        for forbidden in ("GEMINI_API_KEY", "password_hash", "raw_token", "csrf_verifier", "session_token"):
            assert forbidden not in response.text
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    response = client.get("/api/settings/overview", headers=headers(workspace, "a"))
    assert response.json()["ai"]["status"] == "configuration_required"
    assert response.json()["ai"]["processing_available"] is False
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "OLLAMA_HOST", "")
    assert client.get("/api/settings/overview", headers=headers(workspace, "a")).json()["ai"]["status"] == "configuration_required"
