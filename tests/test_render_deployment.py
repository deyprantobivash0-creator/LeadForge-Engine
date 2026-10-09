"""Render boundary regressions use only synthetic configuration and isolated test DBs."""
import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url
from backend.core.config import Settings, settings
from deploy.render.runtime import database_url


RENDER_HOST = "leadforge-staging-backend-test.onrender.com"


def test_platform_hostname_is_loaded_without_the_render_adapter(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", RENDER_HOST)
    config = Settings(ENVIRONMENT="development", TRUSTED_HOSTS="manual.example.com")
    assert config.TRUSTED_HOSTS == f"manual.example.com,{RENDER_HOST}"
    assert config.allowed_origins == settings.allowed_origins


@pytest.mark.parametrize("host", ["*", "*.onrender.com", "https://backend.onrender.com",
    "backend.onrender.com/path", "user@backend.onrender.com", "backend.onrender.com:443",
    " backend.onrender.com", "backend.onrender.com ", "bad\nhost", "backend.onrender.com?x=1",
    "backend.onrender.com#fragment", "backend..onrender.com", "backend.example.com"])
def test_platform_hostname_rejects_malformed_configuration(host):
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="development", RENDER_EXTERNAL_HOSTNAME=host)


def test_originless_render_probe_reaches_readiness_and_unknown_hosts_do_not(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.repositories.runtime_readiness_repository import RuntimeReadinessRepository
    from backend.services.runtime_readiness_service import expected_heads
    config = Settings(ENVIRONMENT="development", RENDER_EXTERNAL_HOSTNAME=RENDER_HOST,
                      TRUSTED_HOSTS="manual.example.com")
    monkeypatch.setattr(settings, "TRUSTED_HOSTS", config.TRUSTED_HOSTS)
    calls = []
    def ready(_repository):
        calls.append(True)
        return expected_heads()
    monkeypatch.setattr(RuntimeReadinessRepository, "migration_heads", ready)
    app.middleware_stack = None
    try:
        with TestClient(app) as client:
            for host in (RENDER_HOST, "manual.example.com"):
                response = client.get("/ready", headers={"Host": host})
                assert response.status_code == 200
                assert response.json() == {"success": True, "status": "ready", "database": "ok"}
            assert len(calls) == 2
            for host in ("unknown.example.com", "something-else.onrender.com"):
                response = client.get("/ready", headers={"Host": host, "X-Forwarded-Host": RENDER_HOST})
                assert response.status_code == 400
                assert response.json() == {"detail": "Invalid host."}
            assert len(calls) == 2
    finally:
        app.middleware_stack = None


@pytest.mark.parametrize("port,expected", [(None, "8000"), ("10000", "10000"), ("8123", "8123")])
def test_server_launch_consumes_port_without_binding(monkeypatch, port, expected):
    from deploy.render.runtime import server_command
    monkeypatch.delenv("PORT", raising=False)
    if port is not None:
        monkeypatch.setenv("PORT", port)
    command = server_command()
    assert command[command.index("--host") + 1] == "0.0.0.0"
    assert command[command.index("--port") + 1] == expected
    assert "--no-proxy-headers" in command


@pytest.mark.parametrize("port", ["", "abc", "10000/path", " 10000", "80", "65536", "-1"])
def test_server_port_rejects_invalid_values(monkeypatch, port):
    from deploy.render.runtime import server_command
    monkeypatch.setenv("PORT", port)
    with pytest.raises(ValueError, match="unprivileged TCP port"):
        server_command()


@pytest.mark.parametrize("render", [False, True])
def test_default_container_launch_selects_strict_render_configuration(monkeypatch, render):
    from deploy.render import runtime
    calls = []
    monkeypatch.setattr(runtime.sys, "argv", ["runtime.py", "container"])
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    monkeypatch.setenv("RENDER", "true" if render else "false")
    monkeypatch.setenv("PORT", "10000" if render else "8000")
    monkeypatch.setattr(runtime, "configure", lambda: calls.append("configure"))
    monkeypatch.setattr(runtime.os, "execv", lambda executable, command: calls.append(command))
    runtime.main()
    assert ("configure" in calls) is render
    assert calls[-1] == runtime.server_command()


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
