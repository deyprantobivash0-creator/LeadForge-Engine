"""Account-only credential changes against the disposable auth database."""
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.core.config import settings
from backend.core.passwords import verify_password
from backend.core.rate_limit import limiter, password_change_limiter
from backend.database.session import SessionLocal
from backend.main import app
from backend.models import AuthSession, User
from backend.repositories.auth_repository import AuthRepository
from backend.services.authentication_service import AuthenticationService

OLD = "tenant fixture password"
NEW = "a different secure password"
PATH = "/api/auth/change-password"


@pytest.fixture(autouse=True)
def reset_budget():
    password_change_limiter.reset()
    yield
    password_change_limiter.reset()


def change(client, **payload):
    return client.post(PATH, headers={settings.CSRF_HEADER_NAME: client.cookies[settings.CSRF_COOKIE_NAME]},
                       json={"current_password": OLD, "new_password": NEW, **payload})


def hashes(workspace):
    with SessionLocal() as db:
        return {key: db.get(User, user_id).password_hash for key, user_id in workspace["ids"]["users"].items()}


def test_success_sessions_login_logout_and_isolation(tenant_workspace, caplog):
    workspace = tenant_workspace
    client = workspace["clients"]["a"]
    before = hashes(workspace)
    cookies = dict(client.cookies)
    with TestClient(app, base_url="https://testserver") as other:
        assert other.post("/api/auth/login", json={"email": "user-a@example.com", "password": OLD}).status_code == 200
        with caplog.at_level(logging.INFO, logger="leadforge"):
            response = change(client)
        assert response.status_code == 200
        assert response.json() == {"message": "Password changed successfully."}
        assert response.headers["cache-control"] == "no-store"
        assert dict(client.cookies) == cookies
        assert client.get("/api/auth/me").status_code == 200
        assert other.get("/api/auth/me").status_code == 401
        assert workspace["clients"]["b"].get("/api/auth/me").status_code == 200
    after = hashes(workspace)
    assert verify_password(NEW, after["a"])
    assert not verify_password(OLD, after["a"])
    assert after["b"] == before["b"] and after["admin"] == before["admin"]
    with SessionLocal() as db:
        sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == workspace["ids"]["users"]["a"])).all()
        assert len(sessions) == 2 and sum(row.revoked_at is not None for row in sessions) == 1
    assert OLD not in caplog.text and NEW not in caplog.text and after["a"] not in caplog.text
    assert "auth.change_password.completed" in caplog.text
    assert client.post("/api/auth/logout", headers={settings.CSRF_HEADER_NAME: cookies[settings.CSRF_COOKIE_NAME]}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "user-a@example.com", "password": OLD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "user-a@example.com", "password": NEW}).status_code == 200


@pytest.mark.parametrize("payload", [
    {"current_password": "wrong current password"}, {"new_password": OLD},
    {"new_password": "short"}, {"new_password": ""}, {"new_password": "x" * 1025},
    {"new_password": "long password with\x00nul"},
    {"current_password": ["private-current"]}, {"new_password": ["private-new"]},
    {"user_id": 2}, {"email": "user-b@example.com"}, {"organization_id": 2},
])
def test_rejections_leave_credentials_and_sessions_unchanged(tenant_workspace, payload):
    before = hashes(tenant_workspace)
    response = change(tenant_workspace["clients"]["a"], **payload)
    assert response.status_code == 422
    assert hashes(tenant_workspace) == before
    assert "private-current" not in response.text and "private-new" not in response.text
    assert OLD not in response.text and NEW not in response.text
    with SessionLocal() as db:
        assert all(row.revoked_at is None for row in db.scalars(select(AuthSession)))


@pytest.mark.parametrize("csrf", [None, "invalid"])
def test_csrf_required(tenant_workspace, csrf):
    client = tenant_workspace["clients"]["a"]
    before = hashes(tenant_workspace)
    response = client.post(PATH, headers={} if csrf is None else {settings.CSRF_HEADER_NAME: csrf},
                           json={"current_password": OLD, "new_password": NEW})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_INVALID"
    assert hashes(tenant_workspace) == before


def test_unauthenticated_and_inactive_user(tenant_workspace):
    with TestClient(app, base_url="https://testserver") as anonymous:
        assert anonymous.post(PATH, json={"current_password": OLD, "new_password": NEW}).status_code == 401
    with SessionLocal() as db:
        db.get(User, tenant_workspace["ids"]["users"]["a"]).is_active = False
        db.commit()
    assert change(tenant_workspace["clients"]["a"]).status_code == 401


@pytest.mark.parametrize("stage", ["revoke", "commit"])
def test_transaction_failure_rolls_back_all_writes(tenant_workspace, monkeypatch, stage):
    before = hashes(tenant_workspace)
    client = tenant_workspace["clients"]["a"]
    # A second session must survive a failed operation as well.
    assert client.post("/api/auth/login", json={"email": "user-a@example.com", "password": OLD}).status_code == 200
    with SessionLocal() as db:
        service = AuthenticationService(db)
        session = service.resolve_session(client.cookies[settings.SESSION_COOKIE_NAME])
        def fail(*args, **kwargs):
            db.flush()
            raise RuntimeError("synthetic persistence failure")
        if stage == "revoke":
            monkeypatch.setattr(service.repository, "revoke_other_sessions", fail)
        else:
            monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(RuntimeError):
            service.change_password(session, OLD, NEW)
    assert hashes(tenant_workspace) == before
    with SessionLocal() as db:
        assert all(row.revoked_at is None for row in db.scalars(select(AuthSession)))


def test_stale_credentials_cannot_overwrite_change(tenant_workspace):
    client = tenant_workspace["clients"]["a"]
    before = hashes(tenant_workspace)
    assert change(client).status_code == 200
    with SessionLocal() as db:
        repo = AuthRepository(db)
        session = AuthenticationService(db).resolve_session(client.cookies[settings.SESSION_COOKIE_NAME])
        from backend.services.authentication_service import utc_now
        assert not repo.replace_password(session.user_id, session.id, before["a"], before["a"], utc_now())
        db.rollback()
    assert verify_password(NEW, hashes(tenant_workspace)["a"])


def test_attempt_budget_shared_across_sessions_separate_from_login(tenant_workspace):
    client = tenant_workspace["clients"]["a"]
    for _ in range(5):
        assert change(client, current_password="wrong password").status_code == 422
    limiter.reset()
    assert client.post("/api/auth/login", json={"email": "user-a@example.com", "password": OLD}).status_code == 200
    response = change(client)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
    assert change(tenant_workspace["clients"]["b"]).status_code == 200


@pytest.mark.parametrize("upgrade_hash", [False, True])
def test_inflight_old_password_login_cannot_issue_session(tenant_workspace, monkeypatch, upgrade_hash):
    """Pause after credential verification, commit a change, then resume issuance."""
    client = tenant_workspace["clients"]["a"]
    user_id = tenant_workspace["ids"]["users"]["a"]
    if upgrade_hash:
        from argon2 import PasswordHasher, Type
        with SessionLocal() as db:
            db.get(User, user_id).password_hash = PasswordHasher(
                type=Type.ID, time_cost=1, memory_cost=8192,
            ).hash(OLD)
            db.commit()
    with TestClient(app, base_url="https://testserver") as other:
        assert other.post("/api/auth/login", json={"email": "user-a@example.com", "password": OLD}).status_code == 200
        # Restore a legacy hash to exercise an in-flight automatic hash upgrade.
        if upgrade_hash:
            with SessionLocal() as db:
                db.get(User, user_id).password_hash = PasswordHasher(
                    type=Type.ID, time_cost=1, memory_cost=8192,
                ).hash(OLD)
                db.commit()
        with SessionLocal() as db:
            before_ids = set(db.scalars(select(AuthSession.id)))
        original = AuthenticationService.create_session
        paused = False

        def resume_after_change(service, user, *args, **kwargs):
            nonlocal paused
            if not paused:
                paused = True
                assert change(client).status_code == 200
            return original(service, user, *args, **kwargs)

        monkeypatch.setattr(AuthenticationService, "create_session", resume_after_change)
        with TestClient(app, base_url="https://testserver") as inflight:
            response = inflight.post("/api/auth/login", json={"email": "user-a@example.com", "password": OLD})
            assert paused
            assert response.status_code == 401
            assert response.json() == {"success": False, "error": {
                "code": "AUTHENTICATION_FAILED", "message": "Invalid credentials.",
            }}
            assert not response.headers.get_list("set-cookie")
            with SessionLocal() as db:
                assert set(db.scalars(select(AuthSession.id))) == before_ids
            assert verify_password(NEW, hashes(tenant_workspace)["a"])
            assert not verify_password(OLD, hashes(tenant_workspace)["a"])
            assert client.get("/api/auth/me").status_code == 200
            assert other.get("/api/auth/me").status_code == 401
            assert inflight.get("/api/auth/me").status_code == 401
            assert inflight.post("/api/auth/login", json={"email": "user-a@example.com", "password": NEW}).status_code == 200


@pytest.mark.parametrize("upgrade_hash", [False, True])
def test_session_commit_failure_rolls_back_guard_hash_upgrade_and_insert(tenant_workspace, monkeypatch, upgrade_hash):
    user_id = tenant_workspace["ids"]["users"]["a"]
    if upgrade_hash:
        from argon2 import PasswordHasher, Type
        with SessionLocal() as db:
            db.get(User, user_id).password_hash = PasswordHasher(
                type=Type.ID, time_cost=1, memory_cost=8192,
            ).hash(OLD)
            db.commit()
    before_hashes = hashes(tenant_workspace)
    with SessionLocal() as db:
        before_ids = set(db.scalars(select(AuthSession.id)))
    with SessionLocal() as db:
        def fail_commit():
            db.flush()
            raise RuntimeError("synthetic session commit failure")
        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError):
            AuthenticationService(db).login("user-a@example.com", OLD)
    assert hashes(tenant_workspace) == before_hashes
    with SessionLocal() as db:
        assert set(db.scalars(select(AuthSession.id))) == before_ids
    # The failed operation releases its guard; a subsequent normal login works.
    client = tenant_workspace["clients"]["a"]
    assert client.post("/api/auth/login", json={"email": "user-a@example.com", "password": OLD}).status_code == 200
