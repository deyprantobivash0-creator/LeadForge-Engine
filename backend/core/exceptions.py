class LeadForgeException(Exception):
    """Base exception for LeadForge application errors."""

    status_code = 500
    error_code = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)

        self.message = message

        if status_code is not None:
            self.status_code = status_code

        if error_code is not None:
            self.error_code = error_code


class ResourceNotFoundException(LeadForgeException):
    status_code = 404
    error_code = "RESOURCE_NOT_FOUND"


class DuplicateResourceException(LeadForgeException):
    status_code = 409
    error_code = "DUPLICATE_RESOURCE"


class ValidationException(LeadForgeException):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class TenantAccessException(LeadForgeException):
    status_code = 403
    error_code = "TENANT_ACCESS_DENIED"


class ServiceUnavailableException(LeadForgeException):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"