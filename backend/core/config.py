"""Canonical, fail-closed configuration. Dotenv is explicit and development-only."""
import os
import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def secret_value(value: SecretStr | str) -> str:
    return value.get_secret_value() if isinstance(value, SecretStr) else value


def validate_origin(value: str, *, production: bool = False) -> str:
    try:
        url = urlsplit(value)
        port = url.port
        if (url.scheme not in {"http", "https"} or not url.hostname or "*" in value
                or url.username or url.password or url.path not in {"", "/"}
                or url.query or url.fragment or any(c.isspace() for c in value)
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError
        host = url.hostname.lower()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if len(host) > 253 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
                raise ValueError
        if production and (url.scheme != "https" or is_local_host(host)):
            raise ValueError
        authority = f"[{host}]" if ":" in host else host
        if port is not None and port != {"http": 80, "https": 443}[url.scheme]:
            authority += f":{port}"
        return f"{url.scheme}://{authority}"
    except ValueError:
        raise ValueError("CORS_ORIGINS requires explicit valid browser origins; production requires HTTPS and non-local hosts") from None


def is_local_host(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or address.is_unspecified
    except ValueError:
        return host.lower() == "localhost" or host.lower().endswith(".localhost")


class Settings(BaseSettings):
    APP_NAME: str = "LeadForge Engine"
    VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "test", "production"]
    DATABASE_URL: SecretStr = SecretStr("sqlite:///./leadforge.db")
    AI_PROVIDER: Literal["mock", "gemini", "ollama"] = "mock"
    LEADFORGE_STAGING: bool = False
    AI_TIMEOUT_SECONDS: int = Field(default=20, ge=1, le=120)
    AI_MAX_ATTEMPTS: int = Field(default=2, ge=1, le=3)
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OLLAMA_MODEL: str = "llama3.1"
    GEMINI_API_KEY: SecretStr = SecretStr("")
    DEEPSEEK_API_KEY: SecretStr = SecretStr("")
    OLLAMA_HOST: str = "http://localhost:11434"
    HUBSPOT_ACCESS_TOKEN: SecretStr = SecretStr("")
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    TRUSTED_HOSTS: str = ""
    RENDER_EXTERNAL_HOSTNAME: str = ""
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    SLOW_REQUEST_MS: int = Field(default=2000, ge=1, le=600000)
    RATE_LIMIT_ENABLED: bool = True
    SESSION_COOKIE_NAME: str = "leadforge_session"
    CSRF_COOKIE_NAME: str = "leadforge_csrf"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    SESSION_TTL_SECONDS: int = Field(default=604800, ge=60)
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict"] = "lax"

    model_config = SettingsConfigDict(env_file=None, case_sensitive=True, extra="ignore", hide_input_in_errors=True)

    def __init__(self, **values):
        # Decide before any dotenv source reads a file. A file cannot select mode.
        environment = values.get("ENVIRONMENT", os.environ.get("ENVIRONMENT"))
        env_file = values.get("_env_file")
        if env_file and environment != "development":
            raise ValueError("LEADFORGE_ENV_FILE/_env_file is permitted only with explicit ENVIRONMENT=development")
        try:
            super().__init__(**values)
        except ValidationError as exc:
            # .errors() must also be safe, not only the human-readable rendering.
            safe = [{"type": error["type"], "loc": error["loc"],
                     **({"ctx": error["ctx"]} if "ctx" in error else {})}
                    for error in exc.errors(include_input=False, include_url=False)]
            raise ValidationError.from_exception_data(type(self).__name__, safe, hide_input=True) from None

    @property
    def allowed_origins(self) -> list[str]:
        return self.CORS_ORIGINS.split(",")

    @model_validator(mode="after")
    def validate_configuration(self):
        production = self.ENVIRONMENT == "production"
        if self.LEADFORGE_STAGING and (not production or self.AI_PROVIDER != "mock"):
            raise ValueError("LEADFORGE_STAGING requires production configuration and mock AI")
        try:
            database = make_url(secret_value(self.DATABASE_URL))
            port = database.port
            if port is not None and not 1 <= port <= 65535:
                raise ValueError
        except Exception:
            raise ValueError("DATABASE_URL is malformed") from None
        if database.drivername not in {"sqlite", "postgresql+psycopg"}:
            raise ValueError("DATABASE_URL must use sqlite or postgresql+psycopg")
        if database.drivername == "postgresql+psycopg" and not (database.host and database.database and database.username):
            raise ValueError("PostgreSQL DATABASE_URL requires host, database, and username")
        if production:
            for key in ("DATABASE_URL", "AI_PROVIDER", "CORS_ORIGINS"):
                if key not in self.model_fields_set:
                    raise ValueError(f"{key} must be explicitly supplied in production")
            if database.drivername != "postgresql+psycopg":
                raise ValueError("Production DATABASE_URL requires PostgreSQL with psycopg")
            if {"host", "hostaddr", "port", "user", "username", "password", "dbname", "database"} & set(database.query):
                raise ValueError("DATABASE_URL production query must not override connection identity or credentials")
            weak = {"leadforge_dev_only", "changeme", "password", "secret", "development", "postgres", "fake"}
            if (not database.password or len(database.password) < 16 or database.password.lower() in weak
                    or database.username == "leadforge_dev" or database.database == "leadforge_dev"
                    or is_local_host(database.host)):
                raise ValueError("DATABASE_URL production credentials/host must not use development or placeholder values; password requires at least 16 characters")
            if not self.SESSION_COOKIE_SECURE:
                raise ValueError("SESSION_COOKIE_SECURE must be true in production")
            if self.LOG_LEVEL == "DEBUG" or not self.RATE_LIMIT_ENABLED:
                raise ValueError("LOG_LEVEL DEBUG and RATE_LIMIT_ENABLED=false are prohibited in production")
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        if not origins or any(not origin for origin in origins):
            raise ValueError("CORS_ORIGINS must contain explicit non-empty origins")
        self.CORS_ORIGINS = ",".join(dict.fromkeys(validate_origin(origin, production=production) for origin in origins))
        hosts = [host.strip().lower() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]
        if self.RENDER_EXTERNAL_HOSTNAME:
            # Infrastructure configuration only: never derive trust from forwarded headers.
            # Keep validation here so direct Uvicorn startup has the same exact-host policy.
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.onrender\.com", self.RENDER_EXTERNAL_HOSTNAME):
                raise ValueError("RENDER_EXTERNAL_HOSTNAME requires an exact onrender.com hostname")
            hosts.append(self.RENDER_EXTERNAL_HOSTNAME)
        for host in hosts:
            if len(host) > 253 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
                raise ValueError("TRUSTED_HOSTS requires exact DNS hostnames, without wildcards, ports or URLs")
        self.TRUSTED_HOSTS = ",".join(dict.fromkeys(hosts))
        for key in ("SESSION_COOKIE_NAME", "CSRF_COOKIE_NAME", "CSRF_HEADER_NAME"):
            value = getattr(self, key)
            if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", value):
                raise ValueError(f"{key} must be a non-empty HTTP token")
            if key != "CSRF_HEADER_NAME" and value.startswith(("__Host-", "__Secure-")) and not self.SESSION_COOKIE_SECURE:
                raise ValueError(f"{key} prefix requires SESSION_COOKIE_SECURE=true")
        if self.SESSION_COOKIE_NAME == self.CSRF_COOKIE_NAME:
            raise ValueError("SESSION_COOKIE_NAME and CSRF_COOKIE_NAME must differ")
        if self.AI_PROVIDER == "gemini":
            if not secret_value(self.GEMINI_API_KEY).strip() or not self.GEMINI_MODEL.strip():
                raise ValueError("GEMINI_API_KEY and GEMINI_MODEL are required for AI_PROVIDER=gemini")
        if self.AI_PROVIDER == "ollama":
            try:
                url = urlsplit(self.OLLAMA_HOST)
                port = url.port
                if (url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password
                        or url.query or url.fragment or url.path not in {"", "/"}
                        or any(c.isspace() for c in self.OLLAMA_HOST)
                        or (port is not None and not 1 <= port <= 65535)
                        or not self.OLLAMA_MODEL.strip()):
                    raise ValueError
                if production and (is_local_host(url.hostname) or not {"OLLAMA_HOST", "OLLAMA_MODEL"} <= self.model_fields_set):
                    raise ValueError
            except ValueError:
                raise ValueError("OLLAMA_HOST/OLLAMA_MODEL require valid explicit provider configuration; production forbids local defaults") from None
        return self


def load_settings() -> Settings:
    try:
        return Settings(_env_file=os.environ.get("LEADFORGE_ENV_FILE") or None)
    except Exception as exc:
        # Import/startup errors reveal keys and fixed validator text, never sources.
        if isinstance(exc, ValidationError):
            messages = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'configuration'}: {e['msg']}" for e in exc.errors(include_input=False))
        elif isinstance(exc, ValueError) and str(exc).startswith("LEADFORGE_ENV_FILE"):
            messages = str(exc)
        else:
            messages = "configuration source could not be loaded; check externally supplied keys"
        raise RuntimeError(f"LeadForge configuration rejected: {messages}") from None


settings = load_settings()
