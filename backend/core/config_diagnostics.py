"""Fail-closed startup diagnostics: only fixed text and canonical field names."""
from pydantic import ValidationError


# Exact matches only. Validator text is trusted only when it matches this catalog;
# unknown/new exceptions retain a useful category without exposing their contents.
_VALIDATOR_MESSAGES = frozenset({
    "LEADFORGE_ENV_FILE/_env_file is permitted only with explicit ENVIRONMENT=development",
    "LEADFORGE_STAGING requires production configuration and mock AI",
    "DATABASE_URL is malformed",
    "DATABASE_URL must use sqlite or postgresql+psycopg",
    "PostgreSQL DATABASE_URL requires host, database, and username",
    "Production DATABASE_URL requires PostgreSQL with psycopg",
    "DATABASE_URL production query must not override connection identity or credentials",
    "DATABASE_URL production credentials/host must not use development or placeholder values; password requires at least 16 characters",
    "SESSION_COOKIE_SECURE must be true in production",
    "LOG_LEVEL DEBUG and RATE_LIMIT_ENABLED=false are prohibited in production",
    "CORS_ORIGINS must contain explicit non-empty origins",
    "CORS_ORIGINS requires explicit valid browser origins; production requires HTTPS and non-local hosts",
    "RENDER_EXTERNAL_HOSTNAME requires an exact onrender.com hostname",
    "TRUSTED_HOSTS requires exact DNS hostnames, without wildcards, ports or URLs",
    "SESSION_COOKIE_NAME and CSRF_COOKIE_NAME must differ",
    "GEMINI_API_KEY and GEMINI_MODEL are required for AI_PROVIDER=gemini",
    "OLLAMA_HOST/OLLAMA_MODEL require valid explicit provider configuration; production forbids local defaults",
    *(f"{key} must be explicitly supplied in production" for key in ("DATABASE_URL", "AI_PROVIDER", "CORS_ORIGINS")),
    *(f"{key} must be a non-empty HTTP token" for key in ("SESSION_COOKIE_NAME", "CSRF_COOKIE_NAME", "CSRF_HEADER_NAME")),
    *(f"{key} prefix requires SESSION_COOKIE_SECURE=true" for key in ("SESSION_COOKIE_NAME", "CSRF_COOKIE_NAME")),
})
_TYPE_MESSAGES = {
    "missing": "required setting is missing",
    "literal_error": "unsupported setting choice",
    "bool_parsing": "expected a boolean",
    "bool_type": "expected a boolean",
    "int_parsing": "expected an integer",
    "int_type": "expected an integer",
    "string_type": "expected text",
    "greater_than_equal": "below the permitted minimum",
    "less_than_equal": "above the permitted maximum",
}


def configuration_diagnostic(exc, fields=()):
    if isinstance(exc, ValidationError):
        issues = []
        # Never render the exception, input, ctx (which can contain exceptions),
        # source URL or arbitrary location names. Multiple errors are bounded.
        for error in exc.errors(include_input=False, include_context=False, include_url=False)[:8]:
            location = error["loc"]
            field = location[0] if len(location) == 1 and location[0] in fields else "configuration"
            message = error["msg"].removeprefix("Value error, ")
            safe = next((known for known in _VALIDATOR_MESSAGES if message == known), None)
            reason = safe or _TYPE_MESSAGES.get(error["type"], "invalid setting")
            issues.append(f"{field}: {reason}")
        return "; ".join(issues) or "configuration validation failed"
    if type(exc) is ValueError:
        safe = next((known for known in _VALIDATOR_MESSAGES if str(exc) == known), None)
        if safe:
            return safe
    return "configuration source could not be loaded; check externally supplied keys"


class ConfigurationError(RuntimeError):
    def __init__(self, cause, fields=()):
        self.diagnostic = configuration_diagnostic(cause, fields)
        super().__init__(f"LeadForge configuration rejected: {self.diagnostic}")
