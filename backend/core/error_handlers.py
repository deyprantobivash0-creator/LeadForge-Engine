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
    logger.warning(
        "Application error | method=%s path=%s code=%s",
        request.method,
        request.url.path,
        exc.error_code,
    )

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
    logger.warning(
        "Validation error | method=%s path=%s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
            },
        },
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        "Unhandled exception | method=%s path=%s",
        request.method,
        request.url.path,
    )

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