"""Read one scoped Docker secret then exec the canonical application/migration command."""
import os
from pathlib import Path
import sys
import subprocess

from sqlalchemy.engine import URL


def main():
    role = os.environ["LEADFORGE_STAGE_ROLE"]
    if role not in {"app", "migrator"}:
        raise ValueError("Unsupported staging role")
    value = Path(f"/run/secrets/{role}_password").read_text().strip()
    if len(value) < 32:
        raise ValueError("Invalid staging credential")
    os.environ["DATABASE_URL"] = URL.create("postgresql+psycopg", username="leadforge_stage_" + role,
        password=value, host="postgres", port=5432, database="leadforge_stage").render_as_string(hide_password=False)
    if role == "migrator":
        command = [sys.executable, "-m", "alembic", "upgrade", "head"]
        subprocess.run(command, check=True)
        import psycopg
        with psycopg.connect(host="postgres", port=5432, dbname="leadforge_stage",
                user="leadforge_stage_migrator", password=value, connect_timeout=5) as connection:
            connection.execute("REVOKE INSERT,UPDATE,DELETE ON public.alembic_version FROM leadforge_stage_app")
        return
    else:
        command = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1",
                   "--no-proxy-headers", "--no-access-log", "--no-server-header", "--timeout-graceful-shutdown", "30"]
    os.execv(sys.executable, command)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Staging entrypoint rejected; check private role secret/configuration", file=sys.stderr)
        raise SystemExit(1) from None
