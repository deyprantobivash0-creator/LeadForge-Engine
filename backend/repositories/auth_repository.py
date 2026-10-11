"""Identity and session persistence without transaction ownership."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from backend.models.auth_session import AuthSession
from backend.models.user import User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, normalized_email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == normalized_email))

    def create_session(self, session: AuthSession) -> None:
        self.db.add(session)

    def guard_session_issuance(self, user_id: int, verified_hash: str,
                              replacement_hash: str | None = None) -> bool:
        # A conditional UPDATE both checks the verified credential and holds the
        # user-row write lock through session commit. Password changes use that
        # same row, so they either precede issuance or revoke the issued session.
        values = {"password_hash": replacement_hash or verified_hash,
                  "updated_at": datetime.now(timezone.utc).replace(tzinfo=None) if replacement_hash else User.updated_at}
        with self.db.no_autoflush:
            result = self.db.execute(update(User).where(
                User.id == user_id, User.is_active.is_(True),
                User.password_hash == verified_hash,
            ).values(**values).execution_options(synchronize_session=False))
        return result.rowcount == 1

    def replace_password(self, user_id: int, session_id: int, old_hash: str,
                         new_hash: str, now: datetime) -> bool:
        # Compare-and-swap prevents concurrent changes using a stale credential.
        active_session = select(AuthSession.id).where(
            AuthSession.id == session_id, AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None), AuthSession.expires_at > now,
        ).exists()
        result = self.db.execute(update(User).where(
            User.id == user_id, User.is_active.is_(True),
            User.password_hash == old_hash, active_session,
        ).values(password_hash=new_hash, updated_at=now).execution_options(synchronize_session=False))
        return result.rowcount == 1

    def revoke_other_sessions(self, user_id: int, current_session_id: int, now: datetime) -> None:
        self.db.execute(update(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.id != current_session_id,
            AuthSession.revoked_at.is_(None), AuthSession.expires_at > now,
        ).values(revoked_at=now))

    def get_session_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession)
            .options(joinedload(AuthSession.user))
            .where(AuthSession.token_hash == token_hash)
        )
