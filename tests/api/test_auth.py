"""Cookie authentication against the disposable Step 3A database."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from backend.core.config import settings
from backend.core.passwords import hash_password
from backend.core.rate_limit import limiter
from backend.database.session import SessionLocal, engine
from backend.main import app
from backend.models import AuthSession, OrganizationMembership, User
from backend.services.authentication_service import AuthenticationService, utc_now


EMAIL = "auth@example.com"
PASSWORD = "fixture password"


@pytest.fixture
def auth_client(client):
    limiter.reset()
    with TestClient(app, base_url="https://testserver") as test_client:
        with SessionLocal() as db:
            db.add(User(email=EMAIL, password_hash=hash_password(PASSWORD)))
            db.commit()
        yield test_client
    limiter.reset()


def login(auth_client, email=EMAIL, password=PASSWORD):
    return auth_client.post("/api/auth/login", json={"email": email, "password": password})


def session_rows():
    with SessionLocal() as db:
        return db.scalars(select(AuthSession)).all()


def test_login_success_and_cookie_contract(auth_client):
    response = login(auth_client, email=" AUTH@EXAMPLE.COM ")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == EMAIL
    assert set(response.json()["user"]) == {"id", "email", "is_active"}
    assert "password_hash" not in response.text
    assert PASSWORD not in response.text
    assert "organization" not in response.text
    raw_token = auth_client.cookies[settings.SESSION_COOKIE_NAME]
    csrf_token = auth_client.cookies[settings.CSRF_COOKIE_NAME]
    assert raw_token not in response.text
    rows = session_rows()
    assert len(rows) == 1
    assert rows[0].token_hash != raw_token
    assert rows[0].csrf_token_hash != csrf_token
    assert response.headers["cache-control"] == "no-store"
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(value for value in cookies if value.startswith(settings.SESSION_COOKIE_NAME + "="))
    csrf_cookie = next(value for value in cookies if value.startswith(settings.CSRF_COOKIE_NAME + "="))
    assert "httponly" in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()
    for value in (session_cookie, csrf_cookie):
        assert "secure" in value.lower()
        assert "samesite=lax" in value.lower()
        assert "path=/" in value.lower()
        assert "max-age=" in value.lower()


def test_login_failures_are_generic_and_create_no_session(auth_client):
    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == EMAIL)).is_active = False
        db.commit()
    inactive = login(auth_client)
    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == EMAIL)).is_active = True
        db.commit()
    unknown = login(auth_client, email="absent@example.com")
    wrong = login(auth_client, password="wrong password")
    assert inactive.status_code == unknown.status_code == wrong.status_code == 401
    assert inactive.json() == unknown.json() == wrong.json()
    assert len(session_rows()) == 0


def test_me_missing_invalid_and_valid_cookie(auth_client):
    assert auth_client.get("/api/auth/me").status_code == 401
    auth_client.cookies.set(settings.SESSION_COOKIE_NAME, "random-invalid")
    assert auth_client.get("/api/auth/me").status_code == 401
    auth_client.cookies.clear()
    assert login(auth_client).status_code == 200
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200
    assert set(response.json()) == {"id", "email", "is_active"}


@pytest.mark.parametrize("change", ["expire", "revoke", "disable"])
def test_me_rejects_session_state_changes(auth_client, change):
    assert login(auth_client).status_code == 200
    with SessionLocal() as db:
        row = db.scalar(select(AuthSession))
        if change == "expire":
            row.expires_at = utc_now() - timedelta(seconds=1)
        elif change == "revoke":
            row.revoked_at = utc_now()
        else:
            row.user.is_active = False
        db.commit()
    assert auth_client.get("/api/auth/me").status_code == 401


def test_logout_requires_session_bound_csrf_and_revokes(auth_client):
    assert login(auth_client).status_code == 200
    csrf = auth_client.cookies[settings.CSRF_COOKIE_NAME]
    assert auth_client.post("/api/auth/logout").status_code == 403
    assert auth_client.post("/api/auth/logout", headers={settings.CSRF_HEADER_NAME: "wrong"}).status_code == 403
    assert auth_client.get("/api/auth/me").status_code == 200
    response = auth_client.post("/api/auth/logout", headers={settings.CSRF_HEADER_NAME: csrf})
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert settings.SESSION_COOKIE_NAME not in auth_client.cookies
    assert settings.CSRF_COOKIE_NAME not in auth_client.cookies
    assert all("max-age=0" in value.lower() for value in response.headers.get_list("set-cookie"))
    assert session_rows()[0].revoked_at is not None
    assert auth_client.get("/api/auth/me").status_code == 401
    assert auth_client.post("/api/auth/logout", headers={settings.CSRF_HEADER_NAME: csrf}).status_code == 401


def test_csrf_cannot_be_reused_across_sessions(auth_client):
    assert login(auth_client).status_code == 200
    first_csrf = auth_client.cookies[settings.CSRF_COOKIE_NAME]
    with TestClient(app, base_url="https://testserver") as second_client:
        assert login(second_client).status_code == 200
        assert second_client.post("/api/auth/logout", headers={settings.CSRF_HEADER_NAME: first_csrf}).status_code == 403
        assert second_client.get("/api/auth/me").status_code == 200
        second_csrf = second_client.cookies[settings.CSRF_COOKIE_NAME]
        assert second_client.post("/api/auth/logout", headers={settings.CSRF_HEADER_NAME: second_csrf}).status_code == 200


def test_login_origin_and_rate_limit(auth_client):
    rejected = auth_client.post("/api/auth/login", headers={"Origin": "https://attacker.invalid"}, json={"email": EMAIL, "password": PASSWORD})
    assert rejected.status_code == 403
    assert len(session_rows()) == 0
    for _ in range(9):
        assert login(auth_client, password="wrong").status_code == 401
    assert login(auth_client, password="wrong").status_code == 429


def test_login_validation_never_echoes_password(auth_client):
    response = auth_client.post("/api/auth/login", json={"email": EMAIL, "password": ["private-value"]})
    assert response.status_code == 422
    assert "private-value" not in response.text


def test_credentialed_cors_preflight(auth_client):
    response = auth_client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-CSRF-Token,X-Organization-ID",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_application_sqlite_foreign_keys_and_auth_transaction(client):
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    with SessionLocal() as db:
        db.add(AuthSession(user_id=999999, token_hash="a" * 64, csrf_token_hash="b" * 64, expires_at=utc_now()))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 0
        ghost = User(id=999999, email="ghost@example.com", password_hash="unused", is_active=True)
        with pytest.raises(IntegrityError):
            AuthenticationService(db).create_session(ghost)
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_login_does_not_create_organization_context(auth_client):
    assert login(auth_client).status_code == 200
    assert "organization" not in auth_client.get("/api/auth/me").text
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OrganizationMembership)) == 0
