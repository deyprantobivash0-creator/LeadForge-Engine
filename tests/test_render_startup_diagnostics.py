"""Real startup entrypoint tests: synthetic configuration, no sockets or exec."""
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from backend.core.config import Settings
from backend.core.config_diagnostics import ConfigurationError
from deploy.render import runtime


SENTINEL = "synthetic-private-marker-do-not-emit"
DATABASE = f"postgresql+psycopg://private_user:{SENTINEL}@private-db-host/leadforge_stage"
HOST = "actual-backend.onrender.com"
CANONICAL = {
    "ENVIRONMENT": "production", "LEADFORGE_STAGING": "true", "AI_PROVIDER": "mock",
    "LEADFORGE_RENDER_DB_TLS": "internal", "SESSION_COOKIE_SECURE": "true", "LOG_LEVEL": "INFO",
    "DATABASE_URL": DATABASE, "CORS_ORIGINS": "https://actual-frontend.onrender.com",
    "TRUSTED_HOSTS": HOST, "PORT": "10000", "RENDER": "true", "RENDER_EXTERNAL_HOSTNAME": HOST,
}


def launch(overrides=None, *, mode="container", direct=False):
    # Drop inherited app/adapter inputs so each case proves the entire env contract.
    excluded = set(Settings.model_fields) | set(runtime._FORBIDDEN_INTEGRATIONS) | {
        "LEADFORGE_ENV_FILE", "LEADFORGE_RENDER_DB_TLS", "LEADFORGE_RENDER_DB_CA", "PORT", "RENDER",
    }
    env = {key: value for key, value in os.environ.items() if key not in excluded}
    env.update(CANONICAL)
    for key, value in (overrides or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    # Unused secrets also must not leak via environment dumps.
    env["UNUSED_PRIVATE_CONFIGURATION"] = SENTINEL
    code = """import socket,sys
socket.socket.connect=lambda *args: (_ for _ in ()).throw(AssertionError('network forbidden'))
from deploy.render import runtime
def no_exec(executable, command):
    assert command[command.index('--host')+1]=='0.0.0.0'
    assert command[command.index('--port')+1]=='10000'
    from backend.core.config import settings,secret_value
    from sqlalchemy.engine import make_url
    assert make_url(secret_value(settings.DATABASE_URL)).query['sslmode']=='require'
    assert settings.TRUSTED_HOSTS=='actual-backend.onrender.com'
    assert settings.allowed_origins==['https://actual-frontend.onrender.com']
    assert settings.SESSION_COOKIE_SECURE
    print('PASS pre-Uvicorn canonical configuration and launch')
runtime.os.execv=no_exec
sys.argv=['runtime.py',sys.argv[1]]
raise SystemExit(runtime.run_cli())
"""
    command = [sys.executable, "deploy/render/runtime.py", mode] if direct else [sys.executable, "-c", code, mode]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    for private in (SENTINEL, DATABASE, "private_user", "private-db-host", "UNUSED_PRIVATE_CONFIGURATION"):
        assert private not in output
    assert "Traceback" not in output
    return result


@pytest.mark.parametrize("mode", ["start", "container"])
@pytest.mark.parametrize("driver", ["postgresql+psycopg", "postgresql", "postgres"])
def test_canonical_render_environment_passes_pre_uvicorn(mode, driver):
    result = launch({"DATABASE_URL": DATABASE.replace("postgresql+psycopg", driver)}, mode=mode)
    assert result.returncode == 0
    assert "PASS pre-Uvicorn" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("changes,expected", [
    ({"ENVIRONMENT": "Production"}, "ENVIRONMENT must be production"),
    ({"AI_PROVIDER": "gemini"}, "AI_PROVIDER must be mock"),
    ({"LEADFORGE_STAGING": "True"}, "LEADFORGE_STAGING must be true"),
    ({"LEADFORGE_ENV_FILE": SENTINEL}, "LEADFORGE_ENV_FILE must be absent"),
    ({"OPENAI_API_KEY": SENTINEL}, "OPENAI_API_KEY must be absent"),
    ({"DATABASE_URL": None}, "DATABASE_URL/TLS configuration rejected"),
    ({"DATABASE_URL": SENTINEL}, "DATABASE_URL/TLS configuration rejected"),
    ({"DATABASE_URL": DATABASE + "?sslmode=disable"}, "DATABASE_URL/TLS configuration rejected"),
    ({"DATABASE_URL": DATABASE + "?sslmode=verify-full"}, "DATABASE_URL/TLS configuration rejected"),
    ({"LEADFORGE_RENDER_DB_TLS": "external", "LEADFORGE_RENDER_DB_CA": SENTINEL}, "DATABASE_URL/TLS configuration rejected"),
    ({"DATABASE_URL": DATABASE + "?password=" + SENTINEL}, "DATABASE_URL production query must not override"),
    ({"DATABASE_URL": DATABASE.replace(SENTINEL, "short")}, "password requires at least 16 characters"),
    ({"DATABASE_URL": DATABASE.replace("private-db-host", "localhost")}, "DATABASE_URL production credentials/host"),
    ({"CORS_ORIGINS": None}, "CORS_ORIGINS must be explicitly supplied"),
    ({"CORS_ORIGINS": '["https://actual-frontend.onrender.com"]'}, "CORS_ORIGINS requires explicit valid browser origins"),
    ({"CORS_ORIGINS": "https://user:" + SENTINEL + "@frontend.onrender.com"}, "CORS_ORIGINS requires explicit valid browser origins"),
    ({"CORS_ORIGINS": "*"}, "CORS_ORIGINS requires explicit valid browser origins"),
    ({"TRUSTED_HOSTS": '["actual-backend.onrender.com"]'}, "TRUSTED_HOSTS requires exact DNS hostnames"),
    ({"TRUSTED_HOSTS": "https://user:" + SENTINEL + "@backend.onrender.com"}, "TRUSTED_HOSTS requires exact DNS hostnames"),
    ({"TRUSTED_HOSTS": "*.onrender.com"}, "TRUSTED_HOSTS requires exact DNS hostnames"),
    ({"RENDER_EXTERNAL_HOSTNAME": "https://" + SENTINEL + ".onrender.com"}, "RENDER_EXTERNAL_HOSTNAME requires an exact"),
    ({"SESSION_COOKIE_SECURE": "false"}, "SESSION_COOKIE_SECURE must be true"),
    ({"SESSION_COOKIE_SECURE": SENTINEL}, "SESSION_COOKIE_SECURE: expected a boolean"),
    ({"SESSION_COOKIE_SAMESITE": SENTINEL}, "SESSION_COOKIE_SAMESITE: unsupported setting choice"),
    ({"SESSION_COOKIE_NAME": SENTINEL + "\n"}, "SESSION_COOKIE_NAME must be a non-empty HTTP token"),
    ({"CSRF_COOKIE_NAME": "leadforge_session"}, "SESSION_COOKIE_NAME and CSRF_COOKIE_NAME must differ"),
    ({"LOG_LEVEL": "DEBUG"}, "LOG_LEVEL DEBUG and RATE_LIMIT_ENABLED=false"),
    ({"LOG_LEVEL": SENTINEL}, "LOG_LEVEL: unsupported setting choice"),
    ({"RATE_LIMIT_ENABLED": "false"}, "LOG_LEVEL DEBUG and RATE_LIMIT_ENABLED=false"),
    ({"AI_TIMEOUT_SECONDS": SENTINEL}, "AI_TIMEOUT_SECONDS: expected an integer"),
    ({"AI_TIMEOUT_SECONDS": "0"}, "AI_TIMEOUT_SECONDS: below the permitted minimum"),
    ({"PORT": SENTINEL}, "ValueError: PORT must be an unprivileged TCP port"),
    ({"PORT": "80"}, "ValueError: PORT must be an unprivileged TCP port"),
])
def test_real_entrypoint_rejects_config_with_safe_field_and_reason(changes, expected):
    result = launch(changes)
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith("Render startup rejected: ")
    assert expected in result.stderr


@pytest.mark.parametrize("error", [ValueError(SENTINEL), RuntimeError(SENTINEL),
    RuntimeError("LeadForge configuration rejected: " + SENTINEL),
    OSError(SENTINEL), ModuleNotFoundError(SENTINEL),
    subprocess.CalledProcessError(1, SENTINEL, output=SENTINEL, stderr=SENTINEL),
    ValueError("PORT must be an unprivileged TCP port " + SENTINEL)])
def test_unknown_exception_messages_and_operator_commands_are_never_printed(monkeypatch, capsys, error):
    def fail():
        raise error
    monkeypatch.setattr(runtime, "main", fail)
    assert runtime.run_cli() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert SENTINEL not in output.err
    assert "Traceback" not in output.err
    assert output.err.startswith("Render startup rejected:")


def test_pydantic_locations_messages_context_and_input_are_all_sanitized(monkeypatch, capsys):
    error = ValidationError.from_exception_data("PrivateModel", [{
        "type": "value_error", "loc": (SENTINEL,), "input": DATABASE,
        "ctx": {"error": ValueError(SENTINEL)},
    }])
    for failure in (error, ConfigurationError(error, Settings.model_fields)):
        def fail():
            raise failure
        monkeypatch.setattr(runtime, "main", fail)
        assert runtime.run_cli() == 1
        output = capsys.readouterr().err
        assert "configuration: invalid setting" in output
        assert SENTINEL not in output
        assert DATABASE not in output


def test_multiple_typed_field_errors_are_safe_and_named():
    with pytest.raises(ValidationError) as caught:
        Settings(ENVIRONMENT="development", AI_TIMEOUT_SECONDS=SENTINEL, SESSION_COOKIE_SAMESITE=SENTINEL)
    error = ConfigurationError(caught.value, Settings.model_fields)
    assert "AI_TIMEOUT_SECONDS: expected an integer" in error.diagnostic
    assert "SESSION_COOKIE_SAMESITE: unsupported setting choice" in error.diagnostic
    assert SENTINEL not in str(error)


@pytest.mark.parametrize("changes,expected", [
    ({"PORT": SENTINEL}, "PORT must be an unprivileged TCP port"),
    ({"SESSION_COOKIE_SECURE": SENTINEL}, "SESSION_COOKIE_SECURE: expected a boolean"),
    ({"DATABASE_URL": SENTINEL}, "DATABASE_URL/TLS configuration rejected"),
])
def test_actual_script_entrypoint_exits_without_traceback_or_secrets(changes, expected):
    result = launch(changes, direct=True)
    assert result.returncode == 1
    assert expected in result.stderr
    assert result.stdout == ""
