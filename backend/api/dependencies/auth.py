"""Session and CSRF dependencies; organization authorization comes later."""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database.dependencies import get_db
from backend.models.auth_session import AuthSession
from backend.models.user import User
from backend.services.authentication_service import AuthenticationService


def get_current_session(request: Request, db: Session = Depends(get_db)) -> AuthSession:
    return AuthenticationService(db).resolve_session(request.cookies.get(settings.SESSION_COOKIE_NAME))


def get_current_user(auth_session: AuthSession = Depends(get_current_session)) -> User:
    return auth_session.user


def require_csrf(
    request: Request,
    auth_session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> AuthSession:
    AuthenticationService(db).verify_csrf(
        auth_session,
        request.headers.get(settings.CSRF_HEADER_NAME),
        request.cookies.get(settings.CSRF_COOKIE_NAME),
    )
    return auth_session
