import pytest
from starlette.requests import Request
from backend.core.rate_limit import LoginLimiter
from backend.core.request_security import MAX_REQUEST_BYTES


@pytest.mark.parametrize("path", ["/api/auth/me", "/api/leads/", "/api/settings/overview", "/health", "/missing"])
def test_security_headers_include_rejections(client, path):
    response = client.get(path)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert "strict-transport-security" not in response.headers
    if path.startswith("/api/"):
        assert response.headers["cache-control"] == "no-store"


def test_host_and_forwarded_headers_fail_closed(client):
    assert client.get("/health", headers={"Host": "attacker.invalid", "X-Forwarded-Host": "localhost"}).status_code == 400
    assert client.get("/health", headers={"Forwarded": "host=attacker.invalid", "X-Forwarded-Host": "attacker.invalid"}).status_code == 200
    assert client.request("TRACE", "/api/auth/login").status_code == 405


@pytest.mark.parametrize("streamed", [False, True])
def test_direct_backend_size_limit(client, streamed):
    body = b"x" * (MAX_REQUEST_BYTES + 1)
    content = iter([body[:100], body[100:]]) if streamed else body
    result = client.post("/api/auth/login", content=content, headers={"Content-Type": "application/json"})
    assert result.status_code == 413
    assert result.headers["cache-control"] == "no-store"


def test_login_limiter_bounds_spoofing_and_recovery():
    now = [100.0]
    limiter = LoginLimiter(slots=8, clock=lambda: now[0])
    def request(peer, forwarded):
        return Request({"type": "http", "client": (peer, 123), "headers": [(b"x-forwarded-for", forwarded.encode())]})
    for i in range(10):
        limiter.check(request("192.0.2.1", f"198.51.100.{i}"))
    with pytest.raises(Exception) as error:
        limiter.check(request("192.0.2.1", "new-spoofed-peer"))
    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "60"
    now[0] += 60
    limiter.check(request("192.0.2.1", "another"))
    for i in range(10000):
        try:
            limiter.check(request(str(i), str(i)))
        except Exception as exc:
            assert exc.status_code == 429
    assert len(limiter._buckets) == 8


def test_login_overposting_and_password_bound(client):
    for payload in [
        {"email": "a@example.com", "password": "x" * 1025},
        {"email": "a@example.com", "password": "synthetic-secret", "is_active": True},
    ]:
        result = client.post("/api/auth/login", json=payload)
        assert result.status_code == 422
        assert "synthetic-secret" not in result.text


def test_production_docs_are_disabled():
    import os
    import subprocess
    import sys
    environment = {**os.environ, "ENVIRONMENT": "production", "AI_PROVIDER": "mock",
                   "DATABASE_URL": "postgresql+psycopg://runtime:synthetic-configuration-only@database.example/leadforge",
                   "CORS_ORIGINS": "https://app.example.com", "SESSION_COOKIE_SECURE": "true"}
    environment.pop("LEADFORGE_ENV_FILE", None)
    code = "from backend.main import app; assert app.docs_url is None and app.redoc_url is None and app.openapi_url is None"
    result = subprocess.run([sys.executable, "-c", code], env=environment, capture_output=True)
    assert result.returncode == 0, "Production docs policy process failed"
