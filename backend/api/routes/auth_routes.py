"""Login, logout, and current-user HTTP endpoints."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from backend.api.dependencies.auth import get_current_user, require_csrf
from backend.core.config import settings
from backend.core.exceptions import LeadForgeException
from backend.core.rate_limit import limiter
from backend.database.dependencies import get_db
from backend.models.auth_session import AuthSession
from backend.models.user import User
from backend.schemas.auth_schema import LoginRequest, LoginResponse, LogoutResponse, UserResponse
from backend.services.authentication_service import AuthenticationService


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _validate_login_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in {value.strip() for value in settings.CORS_ORIGINS.split(",") if value.strip()}:
        raise LeadForgeException("Origin not allowed.", status_code=403, error_code="ORIGIN_NOT_ALLOWED")


@router.post("/login", response_model=LoginResponse)
def login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_db),
          budget: None = Depends(limiter.check)):
    _validate_login_origin(request)
    issued = AuthenticationService(db).login(payload.email, payload.password)
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        issued.raw_token,
        max_age=settings.SESSION_TTL_SECONDS,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        issued.csrf_token,
        max_age=settings.SESSION_TTL_SECONDS,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=False,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    return LoginResponse(user=UserResponse.model_validate(issued.user))


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response, auth_session: AuthSession = Depends(require_csrf), db: Session = Depends(get_db)):
    AuthenticationService(db).revoke_session(auth_session)
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/", secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite=settings.SESSION_COOKIE_SAMESITE)
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/", secure=settings.SESSION_COOKIE_SECURE, httponly=False, samesite=settings.SESSION_COOKIE_SAMESITE)
    return LogoutResponse(success=True)


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return user
