"""Database URL validation must never silently select SQLite in production."""

import pytest
from pydantic import ValidationError

from backend.core.config import Settings


def test_explicit_postgres_and_local_sqlite_urls():
    assert Settings(_env_file=None, ENVIRONMENT="production",
                    DATABASE_URL="postgresql+psycopg://user:synthetic-long-password@db.internal:5432/db",
                    AI_PROVIDER="mock", CORS_ORIGINS="https://app.example.com").ENVIRONMENT == "production"
    assert Settings(_env_file=None, ENVIRONMENT="development",
                    DATABASE_URL="sqlite:///./leadforge.db").ENVIRONMENT == "development"


@pytest.mark.parametrize("url", [
    "sqlite:///./leadforge.db",
    "postgresql://user:fake@localhost/db",
    "postgresql+psycopg://user:fake@localhost",
    "invalid",
])
def test_production_rejects_unsupported_or_malformed_database_url(url):
    with pytest.raises(ValidationError, match="DATABASE_URL|PostgreSQL"):
        Settings(_env_file=None, ENVIRONMENT="production", DATABASE_URL=url,
                 AI_PROVIDER="mock", CORS_ORIGINS="https://app.example.com")
