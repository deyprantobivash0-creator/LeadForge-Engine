from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.dashboard_routes import (
    router as dashboard_router,
)
from backend.api.routes.auth_routes import router as auth_router
from backend.api.routes.organization_routes import router as organization_router
from backend.api.routes.import_routes import router as import_router
from backend.api.routes.lead_routes import (
    router as lead_router,
)
from backend.api.routes.report_routes import (
    router as report_router,
)
from backend.api.routes.settings_routes import router as settings_router
from backend.core.config import settings
from backend.core.error_handlers import (
    generic_exception_handler,
    leadforge_exception_handler,
    validation_exception_handler,
)
from backend.core.exceptions import LeadForgeException
from backend.core.logger import event
from backend.database.session import engine
from backend.core.rate_limit import limiter
from backend.core.request_id import RequestIDMiddleware
from backend.core.request_security import RequestSecurityMiddleware
from backend.core.request_logging import (
    RequestLoggingMiddleware,
)

from backend.core.security_headers import (
    SecurityHeadersMiddleware,
)

from backend.api.routes.system_routes import (
    router as system_router,
)


from backend.models.organization import Organization
from backend.models.lead import Lead
from backend.models.lead_analysis import LeadAnalysis
from backend.models.ingestion import IngestionJob


class ObservedFastAPI(FastAPI):
    def build_middleware_stack(self):
        return RequestIDMiddleware(RequestLoggingMiddleware(SecurityHeadersMiddleware(
            RequestSecurityMiddleware(super().build_middleware_stack()))))


@asynccontextmanager
async def lifespan(application):
    event("app.starting", version=settings.VERSION)
    event("config.loaded", provider_name=settings.AI_PROVIDER)
    event("database.engine.ready", database_dialect=engine.dialect.name)
    event("app.started", version=settings.VERSION)
    try:
        yield
    finally:
        event("app.stopping")
        engine.dispose()
        event("app.stopped")


app = ObservedFastAPI(
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json",
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Autonomous AI Lead Intelligence Platform"
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    expose_headers=["X-Request-ID"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        settings.CSRF_HEADER_NAME,
        "X-Organization-ID",
        "X-Import-Preview-Token",
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
app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(import_router)
app.include_router(report_router)
app.include_router(settings_router)
app.include_router(dashboard_router)

app.include_router(system_router)



@app.get("/")
def root():
    return {
        "success": True,
        "message": f"{settings.APP_NAME} API is running.",
    }
