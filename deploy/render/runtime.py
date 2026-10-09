"""Render administration and container launch adapter; startup never migrates."""
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def database_url(raw, mode, ca=None):
    from sqlalchemy.engine import make_url
    try:
        url = make_url(raw)
        if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
            raise ValueError
        query = dict(url.query)
        if mode == "internal":
            if query.get("sslmode", "require") != "require":
                raise ValueError
            query["sslmode"] = "require"
        elif mode == "external":
            if not ca or not Path(ca).is_file() or query.get("sslmode", "verify-full") != "verify-full":
                raise ValueError
            query.update(sslmode="verify-full", sslrootcert=str(Path(ca).resolve()))
        else:
            raise ValueError
        return url.set(drivername="postgresql+psycopg", query=query).render_as_string(hide_password=False)
    except Exception:
        raise ValueError("Render DATABASE_URL/TLS configuration rejected") from None


def configure():
    if (os.environ.get("ENVIRONMENT") != "production" or os.environ.get("AI_PROVIDER") != "mock"
            or os.environ.get("LEADFORGE_STAGING") != "true" or os.environ.get("LEADFORGE_ENV_FILE")):
        raise ValueError("Render requires strict production settings and explicit synthetic mock staging")
    if any(os.environ.get(key) for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY", "HUBSPOT_ACCESS_TOKEN")):
        raise ValueError("Real integration credentials are forbidden in Render mock staging")
    os.environ["DATABASE_URL"] = database_url(os.environ.get("DATABASE_URL", ""),
        os.environ.get("LEADFORGE_RENDER_DB_TLS", "internal"), os.environ.get("LEADFORGE_RENDER_DB_CA"))
    from backend.core.config import settings
    # Canonical Settings still validates credentials, identity overrides, origins and cookies.
    return settings


def server_command():
    port = os.environ.get("PORT", "8000")
    if not re.fullmatch(r"[0-9]{1,5}", port) or not 1024 <= int(port) <= 65535:
        raise ValueError("PORT must be an unprivileged TCP port")
    return [sys.executable, "-m", "uvicorn", "backend.main:app",
        "--host", "0.0.0.0", "--port", str(int(port)), "--workers", "1", "--no-proxy-headers",
        "--no-access-log", "--no-server-header", "--timeout-graceful-shutdown", "30"]


def main():
    if len(sys.argv) > 2:
        raise ValueError("Unsupported Render arguments")
    mode = sys.argv[1] if len(sys.argv) == 2 else "start"
    if mode != "container" or os.environ.get("RENDER") == "true" or os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
        configure()
    if mode == "migrate":
        if os.environ.get("LEADFORGE_RENDER_DB_TLS") != "external":
            raise ValueError("Operator migration requires external verified TLS")
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True)
        from backend.services.runtime_readiness_service import RuntimeReadinessService
        if not RuntimeReadinessService().status()["success"]:
            raise ValueError("Migration required-head gate failed")
        print("PASS Render migration and required-head gate")
    elif mode == "seed":
        if os.environ.get("LEADFORGE_STAGE_SEED") != "synthetic-only":
            raise ValueError("Explicit synthetic seed confirmation required")
        password = os.environ.get("LEADFORGE_RENDER_QA_PASSWORD", "")
        if len(password) < 32:
            raise ValueError("Strong externally supplied synthetic QA password required")
        from deploy.staging.seed import seed
        seed(password)
    elif mode in {"start", "container"}:
        # Render edge terminates TLS. Cookies are explicitly Secure; no redirect logic
        # needs forwarded scheme. Peer-based limiter stays bounded, never spoofable.
        os.execv(sys.executable, server_command())
    else:
        raise ValueError("Unsupported Render operation")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Render operation rejected; check scoped configuration, TLS, privileges and schema", file=sys.stderr)
        raise SystemExit(1) from None
