"""Render boundary regressions use only synthetic configuration and isolated test DBs."""
import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url
from backend.core.config import Settings, settings
from deploy.render.runtime import database_url


def test_render_database_driver_and_internal_tls_preserve_encoded_identity():
    url = make_url(database_url("postgresql://fixture:p%40ssword%25synthetic@dpg-fixture/leadforge_stage?application_name=fixture", "internal"))
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ssword%synthetic"
    assert dict(url.query) == {"application_name": "fixture", "sslmode": "require"}


@pytest.mark.parametrize("raw,mode", [("sqlite:///private.db", "internal"), ("not-a-url", "internal"),
    ("postgresql://u:synthetic@host/db?sslmode=disable", "internal"),
    ("postgresql://u:synthetic@host/db?sslmode=prefer", "external"),
    ("postgresql://u:synthetic@host/db", "unknown")])
def test_render_database_rejects_unsafe_transport_without_leaking(raw, mode):
    with pytest.raises(ValueError) as error:
        database_url(raw, mode)
    assert str(error.value) == "Render DATABASE_URL/TLS configuration rejected"
    assert raw not in str(error.value)


def test_external_transport_requires_a_real_trust_file(tmp_path):
    raw = "postgres://u:synthetic@external.example/db"
    with pytest.raises(ValueError):
        database_url(raw, "external", str(tmp_path / "missing"))
    ca = tmp_path / "synthetic-ca.crt"; ca.write_text("synthetic test file")
    url = make_url(database_url(raw, "external", str(ca)))
    assert url.query["sslmode"] == "verify-full"
    assert url.query["sslrootcert"] == str(ca.resolve())


@pytest.mark.parametrize("host", ["*", "*.onrender.com", "https://backend.onrender.com", "backend.onrender.com:443", "bad\nhost", "user@host"])
def test_trusted_hosts_are_exact_dns_names(host):
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="development", TRUSTED_HOSTS=host)


def test_backend_host_is_independent_of_browser_cors():
    config = Settings(ENVIRONMENT="development", TRUSTED_HOSTS="BACKEND.onrender.com,backend.onrender.com")
    assert config.TRUSTED_HOSTS == "backend.onrender.com"
    assert "https://backend.onrender.com" not in config.allowed_origins


def test_direct_render_host_retains_auth_tenant_csrf_and_session_checks(tenant_workspace, monkeypatch):
    from backend.core.request_security import RequestSecurityMiddleware
    from backend.main import app
    monkeypatch.setattr(settings, "TRUSTED_HOSTS", "backend.onrender.com")
    app.middleware_stack = None
    clients = tenant_workspace["clients"]
    a = clients["a"]
    ids = tenant_workspace["ids"]
    headers = {"Host": "backend.onrender.com", "X-Organization-ID": str(ids["organizations"]["a"])}
    assert a.get("/health", headers=headers).status_code == 200
    assert a.get("/api/leads/", headers=headers).status_code == 200
    assert a.get(f'/api/leads/{ids["leads"]["b"]}', headers=headers).status_code == 404
    assert a.get("/api/leads/", headers={**headers, "X-Organization-ID": str(ids["organizations"]["b"])}).status_code == 403
    assert a.post("/api/leads/", headers=headers, json={"company":"Synthetic","email":"synthetic@example.com","source":"test"}).status_code == 403
    assert a.get("/health", headers={"Host":"unknown.onrender.com", "X-Forwarded-Host":"backend.onrender.com"}).status_code == 400
    cookies = dict(a.cookies); a.cookies.clear()
    assert a.get("/api/leads/", headers=headers).status_code == 401
    a.cookies.update(cookies)
    assert RequestSecurityMiddleware(app).hosts >= {"backend.onrender.com"}
    app.middleware_stack = None
