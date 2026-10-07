"""Identity and session persistence without transaction ownership."""

from sqlalchemy import select
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

    def get_session_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession)
            .options(joinedload(AuthSession.user))
            .where(AuthSession.token_hash == token_hash)
        )
