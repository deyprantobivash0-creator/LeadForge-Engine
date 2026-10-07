from backend.core.logger import operation
"""First-party authentication and server-side session lifecycle."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import LeadForgeException
from backend.core.passwords import hash_password, verify_password, needs_rehash
from backend.core.session_tokens import generate_session_token, hash_session_token, verify_session_token
from backend.models.auth_session import AuthSession
from backend.models.user import User
from backend.repositories.auth_repository import AuthRepository


# Existing DateTime columns are naïve UTC. Keep that storage boundary explicit.
def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


_DUMMY_PASSWORD_HASH = hash_password("leadforge unknown account timing equalizer")


class AuthenticationFailed(LeadForgeException):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"

    def __init__(self):
        super().__init__("Invalid credentials.")


class SessionRequired(LeadForgeException):
    status_code = 401
    error_code = "AUTHENTICATION_REQUIRED"

    def __init__(self):
        super().__init__("Authentication required.")


class CsrfRejected(LeadForgeException):
    status_code = 403
    error_code = "CSRF_INVALID"

    def __init__(self):
        super().__init__("CSRF validation failed.")


@dataclass(frozen=True)
class IssuedSession:
    user: User
    raw_token: str
    csrf_token: str


class AuthenticationService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AuthRepository(db)

    def authenticate_user(self, email: str, password: str) -> User:
        user = self.repository.get_user_by_email(email.strip().lower())
        valid_password = verify_password(password, user.password_hash if user else _DUMMY_PASSWORD_HASH)
        if not user or not valid_password or not user.is_active:
            raise AuthenticationFailed()
        if needs_rehash(user.password_hash):
            # Commit the upgrade together with issuance of the new session.
            user.password_hash = hash_password(password)
        return user

    def create_session(self, user: User) -> IssuedSession:
        if not user.is_active:
            raise AuthenticationFailed()
        raw_token = generate_session_token()
        csrf_token = generate_session_token()
        self.repository.create_session(
            AuthSession(
                user_id=user.id,
                token_hash=hash_session_token(raw_token),
                csrf_token_hash=hash_session_token(csrf_token),
                expires_at=utc_now() + timedelta(seconds=settings.SESSION_TTL_SECONDS),
            )
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return IssuedSession(user=user, raw_token=raw_token, csrf_token=csrf_token)

    @operation("auth.login")
    def login(self, email: str, password: str) -> IssuedSession:
        user = self.authenticate_user(email, password)
        return self.create_session(user)

    @operation("auth.session", success=False)
    def resolve_session(self, raw_token: str | None) -> AuthSession:
        if not raw_token or len(raw_token) != 43:
            raise SessionRequired()
        auth_session = self.repository.get_session_by_token_hash(hash_session_token(raw_token))
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= utc_now()
            or auth_session.user is None
            or not auth_session.user.is_active
        ):
            raise SessionRequired()
        return auth_session

    def verify_csrf(self, auth_session: AuthSession, header_token: str | None, cookie_token: str | None) -> None:
        if (
            not header_token
            or not cookie_token
            or not verify_session_token(header_token, auth_session.csrf_token_hash)
            or not verify_session_token(cookie_token, auth_session.csrf_token_hash)
        ):
            raise CsrfRejected()

    @operation("auth.logout")
    def revoke_session(self, auth_session: AuthSession) -> None:
        auth_session.revoked_at = utc_now()
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
