from backend.core.logger import operation
"""First-party authentication and server-side session lifecycle."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.database.transactions import service_transaction

from backend.core.config import settings
from backend.core.exceptions import LeadForgeException, ValidationException
from backend.core.passwords import hash_password, verify_password, needs_rehash, validate_new_password
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
        return user

    def create_session(self, user: User, *, replacement_hash: str | None = None) -> IssuedSession:
        with service_transaction(self.db):
            if not user.is_active or not self.repository.guard_session_issuance(
                user.id, user.password_hash, replacement_hash,
            ):
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
        return IssuedSession(user=user, raw_token=raw_token, csrf_token=csrf_token)

    @operation("auth.login")
    def login(self, email: str, password: str) -> IssuedSession:
        with service_transaction(self.db):
            user = self.authenticate_user(email, password)
            # Do not dirty the ORM User before the conditional credential guard:
            # a stale automatic hash upgrade must never overwrite a password change.
            replacement_hash = hash_password(password) if needs_rehash(user.password_hash) else None
            return self.create_session(user, replacement_hash=replacement_hash)

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

    @operation("auth.change_password")
    def change_password(self, auth_session: AuthSession, current_password: str, new_password: str) -> None:
        with service_transaction(self.db):
            user = auth_session.user
            now = utc_now()
            if not user.is_active or auth_session.revoked_at is not None or auth_session.expires_at <= now:
                raise SessionRequired()
            old_hash = user.password_hash
            if not verify_password(current_password, old_hash):
                raise ValidationException("Current password is incorrect.", error_code="CURRENT_PASSWORD_INCORRECT")
            validate_new_password(new_password)
            if verify_password(new_password, old_hash):
                raise ValidationException("New password must differ from current password.")
            if not self.repository.replace_password(user.id, auth_session.id, old_hash, hash_password(new_password), now):
                raise LeadForgeException("Account credentials changed. Sign in again before retrying.",
                                         status_code=409, error_code="CREDENTIALS_CHANGED")
            self.repository.revoke_other_sessions(user.id, auth_session.id, now)

    @operation("auth.logout")
    def revoke_session(self, auth_session: AuthSession) -> None:
        with service_transaction(self.db):
            auth_session.revoked_at = utc_now()
