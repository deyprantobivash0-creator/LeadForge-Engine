from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.dashboard_routes import (
    router as dashboard_router,
)
from backend.api.routes.lead_routes import (
    router as lead_router,
)
from backend.api.routes.report_routes import (
    router as report_router,
)
from backend.core.config import settings
from backend.core.error_handlers import (
    generic_exception_handler,
    leadforge_exception_handler,
    validation_exception_handler,
)
from backend.core.exceptions import LeadForgeException
from backend.core.logger import logger
from backend.core.request_id import RequestIDMiddleware
from backend.core.request_logging import (
    RequestLoggingMiddleware,
)

from backend.core.security_headers import (
    SecurityHeadersMiddleware,
)

from backend.api.routes.system_routes import (
    router as system_router,
)

from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(
    key_func=get_remote_address
)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Autonomous AI Lead Intelligence Platform"
    ),
)


app.add_middleware(
    RequestIDMiddleware
)

app.add_middleware(
    RequestLoggingMiddleware
)

app.add_middleware(
    SecurityHeadersMiddleware
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    ],
)


app.add_exception_handler(
    LeadForgeException,
    leadforge_exception_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)

app.add_exception_handler(
    Exception,
    generic_exception_handler,
)

app.state.limiter = limiter

app.include_router(lead_router)
app.include_router(report_router)
app.include_router(dashboard_router)

app.include_router(system_router)

logger.info(
    "LeadForge Engine Started Successfully"
)


@app.get("/")
def root():
    return {
        "success": True,
        "message": f"{settings.APP_NAME} API is running.",
    }


@app.get("/health")
def health():
    return {
        "success": True,
        "status": "healthy",
        "version": settings.VERSION,
    }


@app.get("/ready")
def readiness():
    return {
        "success": True,
        "status": "ready",
        "version": settings.VERSION,
    }