import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.core.exceptions import LeadForgeException

logger = logging.getLogger("leadforge")


async def leadforge_exception_handler(
    request: Request,
    exc: LeadForgeException,
):
    from backend.core.logger import event
    event("http.domain.rejected", level=logging.WARNING, reason=exc.error_code, status_code=exc.status_code)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
            },
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    from backend.core.logger import event
    event("http.validation.rejected", level=logging.WARNING, status_code=422)

    # Validator context can contain exception objects that are not JSON-safe.
    details = [{key: value for key, value in error.items() if key != "ctx"}
               for error in exc.errors()]
    if request.url.path == "/api/auth/login":
        # Validation details must not echo a submitted password or request body.
        details = [
            {key: value for key, value in error.items() if key not in {"input", "ctx"}}
            for error in details
        ]

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": details,
            },
        },
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
):
    from backend.core.logger import event
    event("http.exception", level=logging.ERROR, exc=exc)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
            },
        },
    )
