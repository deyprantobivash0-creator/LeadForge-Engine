"""Read-only Alembic gate. Application pods cannot migrate or bypass a missing head."""
import os
from pathlib import Path
import sys
import psycopg

try:
    with psycopg.connect(host="postgres", dbname="leadforge_stage",
            user="leadforge_stage_app",
            password=Path("/run/secrets/app_password").read_text().strip(),
            connect_timeout=5) as connection:
        heads = connection.execute("SELECT version_num FROM public.alembic_version").fetchall()
    if heads != [(os.environ["LEADFORGE_SCHEMA_HEAD"],)]:
        raise ValueError("Schema not at required release head")
except Exception:
    print("Migration gate closed; required Alembic head unavailable", file=sys.stderr)
    raise SystemExit(1) from None
print("Required Alembic head verified; application startup permitted")
