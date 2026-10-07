"""Explicit staging-only provisioning. No schema DDL; Alembic owns application schema."""
import os
from pathlib import Path
import sys

import psycopg
from psycopg import sql

DATABASE = "leadforge_stage"
ROLES = ("leadforge_stage_migrator", "leadforge_stage_app", "leadforge_stage_backup")


def password(name):
    value = Path("/run/secrets/" + name + "_password").read_text().strip()
    if len(value) < 32 or any(c.isspace() for c in value):
        raise ValueError("Invalid externally supplied staging credential")
    return value


def main():
    if os.environ.get("LEADFORGE_STAGE_PROVISION") != "true":
        raise ValueError("Explicit staging provisioning flag required")
    options = dict(host="postgres", port=5432, user="leadforge_stage_admin",
                   password=password("admin"), connect_timeout=5)
    with psycopg.connect(dbname="postgres", autocommit=True, **options) as connection:
        with connection.cursor() as cursor:
            for role, key in zip(ROLES, ("migrator", "app", "backup")):
                cursor.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s", (role,))
                existing = cursor.fetchone()
                if existing and any(existing):
                    raise ValueError("Existing staging role has unexpected privileges")
                if existing is None:
                    cursor.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Identifier(role), sql.Literal(password(key))))
            cursor.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s", (DATABASE,))
            owner = cursor.fetchone()
            if owner and owner[0] != ROLES[0]:
                raise ValueError("Existing staging DB has unexpected owner")
            if owner is None:
                cursor.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(DATABASE), sql.Identifier(ROLES[0])))
            cursor.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(DATABASE)))
            for role in ROLES:
                cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(DATABASE), sql.Identifier(role)))
    with psycopg.connect(dbname=DATABASE, **options) as connection, connection.cursor() as cursor:
        cursor.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(ROLES[0])))
        cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for role in ROLES[1:]:
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        for role, table_grants, sequence_grants in ((ROLES[1], "SELECT,INSERT,UPDATE,DELETE", "USAGE,SELECT"), (ROLES[2], "SELECT", "SELECT")):
            cursor.execute(sql.SQL("GRANT " + table_grants + " ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role)))
            cursor.execute(sql.SQL("GRANT " + sequence_grants + " ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(role)))
            cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT " + table_grants + " ON TABLES TO {}").format(sql.Identifier(ROLES[0]), sql.Identifier(role)))
            cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT " + sequence_grants + " ON SEQUENCES TO {}").format(sql.Identifier(ROLES[0]), sql.Identifier(role)))
    print("Staging roles/database provisioned; application schema remains Alembic-owned")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Staging provisioning failed; check identity, private credentials and privileges", file=sys.stderr)
        raise SystemExit(1) from None
