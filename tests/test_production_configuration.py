"""Configuration tests use synthetic values and never construct a provider client."""
import json
import os
import subprocess
import sys
import uuid
import logging
import pytest
from pydantic import ValidationError
from backend.core.config import Settings, secret_value, settings
from backend.core.redaction import SecretFilter


def production(**overrides):
    values = dict(ENVIRONMENT="production", DATABASE_URL="postgresql+psycopg://runtime:synthetic-test-password@db.internal/app",
                  AI_PROVIDER="mock", CORS_ORIGINS="https://app.example.com")
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("mode", ["", "Production", "prod", "staging", "developmnt"])
def test_environment_is_strict(mode):
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT=mode)


@pytest.mark.parametrize("overrides", [
    {"DATABASE_URL": "sqlite:///disposable.db"},
    {"DATABASE_URL": "postgresql+psycopg://leadforge_dev:leadforge_dev_only@postgres/leadforge_dev"},
    {"DATABASE_URL": "postgresql+psycopg://runtime:password@db.internal/app"},
    {"DATABASE_URL": "postgresql+psycopg://runtime@db.internal/app"},
    {"DATABASE_URL": "postgresql+psycopg://runtime:synthetic-test-password@localhost/app"},
    {"DATABASE_URL": "postgresql+psycopg://runtime:synthetic-test-password@db.internal:bad/app"},
    {"DATABASE_URL": "postgresql+psycopg://runtime:synthetic-test-password@db.internal/app?password=development"},
    {"DATABASE_URL": "postgresql+psycopg://runtime:synthetic-test-password@db.internal/app?host=localhost"},
    {"AI_PROVIDER": "deepseek"}, {"AI_PROVIDER": "gemni"},
    {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": ""},
    {"AI_PROVIDER": "ollama"},
    {"CORS_ORIGINS": "*"}, {"CORS_ORIGINS": "https://*.example.com"},
    {"CORS_ORIGINS": "https://app.example.com/path"},
    {"CORS_ORIGINS": "https://user:password@app.example.com"},
    {"CORS_ORIGINS": "http://app.example.com"}, {"CORS_ORIGINS": "https://localhost"},
    {"CORS_ORIGINS": ""}, {"SESSION_COOKIE_SECURE": False},
    {"SESSION_COOKIE_NAME": "bad name"}, {"CSRF_COOKIE_NAME": "leadforge_session"},
    {"CSRF_HEADER_NAME": "bad\nheader"}, {"LOG_LEVEL": "DEBUG"}, {"RATE_LIMIT_ENABLED": False},
])
def test_production_rejects_unsafe_configuration(overrides):
    with pytest.raises(ValidationError):
        production(**overrides)


def test_provider_contract_without_network():
    assert production().AI_PROVIDER == "mock"
    assert production(AI_PROVIDER="gemini", GEMINI_API_KEY="synthetic-key").AI_PROVIDER == "gemini"
    assert production(AI_PROVIDER="ollama", OLLAMA_HOST="http://models.internal:11434", OLLAMA_MODEL="fixture-model").AI_PROVIDER == "ollama"


def test_development_http_and_test_are_explicit():
    for mode in ("development", "test"):
        config = Settings(ENVIRONMENT=mode, SESSION_COOKIE_SECURE=False)
        assert config.AI_PROVIDER == "mock"
        assert not config.SESSION_COOKIE_SECURE
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="development", SESSION_COOKIE_SECURE=False, SESSION_COOKIE_NAME="__Host-session")


def test_origins_normalized_and_deduplicated():
    assert production(CORS_ORIGINS=" HTTPS://APP.EXAMPLE.COM:443/,https://app.example.com ").allowed_origins == ["https://app.example.com"]


def test_dotenv_opt_in_and_precedence(tmp_path, monkeypatch):
    fixture = tmp_path / "configuration.fixture"
    fixture.write_text("APP_NAME=File value\nAI_PROVIDER=mock\n")
    monkeypatch.setenv("APP_NAME", "OS value")
    assert Settings(ENVIRONMENT="development", _env_file=fixture).APP_NAME == "OS value"
    assert Settings(ENVIRONMENT="development", _env_file=fixture, APP_NAME="Init value").APP_NAME == "Init value"
    for mode in ("test", "production"):
        with pytest.raises(ValueError, match="development"):
            Settings(ENVIRONMENT=mode, _env_file=fixture)


def test_secret_representations_validation_and_logging(monkeypatch):
    sentinel = "synthetic-" + uuid.uuid4().hex
    config = production(HUBSPOT_ACCESS_TOKEN=sentinel)
    assert sentinel not in repr(config)
    assert sentinel not in config.model_dump_json()
    with pytest.raises(ValidationError) as caught:
        production(DATABASE_URL=sentinel)
    assert sentinel not in str(caught.value)
    assert sentinel not in repr(caught.value.errors())
    monkeypatch.setattr(settings, "HUBSPOT_ACCESS_TOKEN", sentinel)
    record = logging.LogRecord("leadforge", logging.ERROR, __file__, 1, "credential=%s", (sentinel,), None)
    SecretFilter().filter(record)
    assert sentinel not in record.getMessage()
    record = logging.LogRecord("leadforge", logging.ERROR, __file__, 1, "postgresql+psycopg://user:another-secret@db/app", (), None)
    SecretFilter().filter(record)
    assert "another-secret" not in record.getMessage()


def clean_environment():
    keys = set(Settings.model_fields) | {"LEADFORGE_ENV_FILE"}
    return {key: value for key, value in os.environ.items() if key not in keys}


@pytest.mark.parametrize("missing", ["ENVIRONMENT", "DATABASE_URL", "AI_PROVIDER", "CORS_ORIGINS"])
def test_missing_required_startup_fails_before_app(missing):
    env = clean_environment()
    env.update(ENVIRONMENT="production", DATABASE_URL="postgresql+psycopg://runtime:synthetic-test-password@db.internal/app", AI_PROVIDER="mock", CORS_ORIGINS="https://app.example.com")
    del env[missing]
    result = subprocess.run([sys.executable, "-c", "import backend.main"], env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert missing in result.stderr
    assert "synthetic-test-password" not in result.stderr


def test_production_app_dry_run_has_no_network_and_no_leaks():
    sentinel = "synthetic-" + uuid.uuid4().hex
    env = clean_environment()
    env.update(ENVIRONMENT="production", DATABASE_URL=f"postgresql+psycopg://runtime:{sentinel}@db.internal/app", AI_PROVIDER="mock", CORS_ORIGINS="https://app.example.com", HUBSPOT_ACCESS_TOKEN=sentinel)
    script = "import socket; socket.socket.connect=lambda *args: (_ for _ in ()).throw(AssertionError('network forbidden')); import backend.main; from backend.core.config import settings; print('PRODUCTION_INITIALIZED', settings.ENVIRONMENT, settings.AI_PROVIDER)"
    result = subprocess.run([sys.executable, "-c", script], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "PRODUCTION_INITIALIZED production mock" in result.stdout
    assert sentinel not in result.stdout + result.stderr
