"""Operator-only Render role setup against an explicitly selected existing database."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deploy.render.runtime import configure


def provision(connection, passwords, *, finalize=False):
    from psycopg import sql
    roles = ("leadforge_stage_migrator", "leadforge_stage_app", "leadforge_stage_backup")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        database, owner = cursor.fetchone()
        if database != "leadforge_stage" or owner in roles:
            raise ValueError("Explicit Render staging owner/database required")
        cursor.execute("SELECT datdba = (SELECT oid FROM pg_roles WHERE rolname=current_user) FROM pg_database WHERE datname=current_database()")
        if not cursor.fetchone()[0]:
            raise ValueError("Database owner required")
        if not finalize:
            for role, key in zip(roles, ("migrator", "app", "backup")):
                value = passwords[key]
                if len(value) < 32 or any(c.isspace() for c in value):
                    raise ValueError("Strong externally supplied role passwords required")
                cursor.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s", (role,))
                existing = cursor.fetchone()
                if existing is not None:
                    raise ValueError("Role already exists; inspect instead of overwriting")
                cursor.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Identifier(role), sql.Literal(value)))
            cursor.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(roles[0]), sql.Identifier(owner)))
            cursor.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(roles[0])))
            cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            cursor.execute("REVOKE ALL ON DATABASE leadforge_stage FROM PUBLIC")
            for role in roles:
                cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE leadforge_stage TO {}").format(sql.Identifier(role)))
            for role in roles[1:]:
                cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        for role, tables, sequences in ((roles[1], "SELECT,INSERT,UPDATE,DELETE", "USAGE,SELECT"), (roles[2], "SELECT", "SELECT")):
            cursor.execute(sql.SQL("GRANT " + tables + " ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role)))
            cursor.execute(sql.SQL("GRANT " + sequences + " ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(role)))
            cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT " + tables + " ON TABLES TO {}").format(sql.Identifier(roles[0]), sql.Identifier(role)))
            cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT " + sequences + " ON SEQUENCES TO {}").format(sql.Identifier(roles[0]), sql.Identifier(role)))
        if finalize:
            cursor.execute("SELECT version_num FROM alembic_version")
            if cursor.fetchall() != [("e5d4c3b2a1f0",)]:
                raise ValueError("Required schema head absent")
            cursor.execute("REVOKE INSERT,UPDATE,DELETE ON alembic_version FROM leadforge_stage_app")
    # Caller owns one transaction; any error rolls back role/grant changes.


def main():
    if os.environ.get("LEADFORGE_STAGE_PROVISION") != "true" or os.environ.get("LEADFORGE_RENDER_DB_TLS") != "external":
        raise ValueError("Explicit operator provisioning and external verified TLS required")
    if sys.argv[1:] not in ([], ["finalize"]):
        raise ValueError("Unsupported provisioning operation")
    configure()
    import psycopg
    from sqlalchemy.engine import make_url
    url = make_url(os.environ["DATABASE_URL"])
    values = {key: os.environ.get("LEADFORGE_RENDER_" + key.upper() + "_PASSWORD", "") for key in ("migrator", "app", "backup")}
    with psycopg.connect(host=url.host, port=url.port or 5432, dbname=url.database,
                         user=url.username, password=url.password, connect_timeout=5, **dict(url.query)) as connection:
        provision(connection, values, finalize=sys.argv[1:] == ["finalize"])
    print("PASS scoped Render staging role/grant operation")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Render role operation failed; verify selected database/owner privileges without exposing credentials", file=sys.stderr)
        raise SystemExit(1) from None
