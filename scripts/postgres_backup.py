"""Explicit PostgreSQL backup/inspect/restore operations; standard library only."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
CLIENT_IMAGE = "postgres:16.15@sha256:65b16a8b326e0cfbdf33fa7e783f2a0cb352a61448616ccccfd616ef42aa0f65"
TABLES = ("alembic_version", "organizations", "users", "organization_memberships",
          "auth_sessions", "leads", "lead_analysis", "ingestion_jobs")
PASSWORD_ENV = "LEADFORGE_BACKUP_PASSWORD"


class BackupError(Exception):
    """Only fixed, credential-free diagnostics are raised to the CLI."""


def log(event, **fields):
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                      "event": event, **fields}, ensure_ascii=True), flush=True)


def identifier(value):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
        raise BackupError("Database/user must be a simple lowercase PostgreSQL identifier")
    return value


def container_name(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise BackupError("Explicit Docker container name or ID is required")
    return value


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def docker(args, *, env=None, stdin=None, stdout=None, timeout=300):
    try:
        result = subprocess.run(["docker", *args], env=env, stdin=stdin,
                                stdout=stdout if stdout is not None else subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupError("Docker operation unavailable or timed out") from exc
    if result.returncode:
        # Driver stderr can contain SQL, passwords, DSNs and row data.
        state = re.search(rb"(?:ERROR|FATAL):\s+([A-Z0-9]{5})\b", result.stderr)
        category = "; SQLSTATE=" + state.group(1).decode() if state else ""
        raise BackupError(f"PostgreSQL/container operation failed (exit {result.returncode}{category}); check readiness, credentials and privileges")
    return result.stdout


class PgTools:
    def __init__(self, container, database, user, password=None):
        self.container = container_name(container)
        self.database = identifier(database)
        self.user = identifier(user)
        self.password = os.environ.get(PASSWORD_ENV) if password is None else password
        self._connection = None

    def network_connection(self):
        if self._connection is None:
            networks = json.loads(docker(["inspect", "--format", "{{json .NetworkSettings.Networks}}", self.container]))
            candidates = [(name, config["IPAddress"]) for name, config in networks.items() if config.get("IPAddress")]
            if len(candidates) != 1:
                raise BackupError("Source/target PostgreSQL needs exactly one Docker IPv4 network")
            network, host = candidates[0]
            if ipaddress.ip_address(host).is_loopback:
                raise BackupError("Refusing loopback trust-auth transport")
            self._connection = (network, host)
        return self._connection

    def command(self, tool, *args, connected=True):
        network, host = self.network_connection() if connected else ("none", None)
        command = ["run", "--rm", "-i", "--network", network]
        if connected:
            command.extend(["--env", "PGPASSWORD", "--env", "PGCONNECT_TIMEOUT=5",
                            "--env", "PGOPTIONS=-c statement_timeout=120000 -c lock_timeout=10000"])
        command.extend([CLIENT_IMAGE, tool])
        if connected:
            command.extend([f"--host={host}", "--port=5432", f"--username={self.user}",
                            f"--dbname={self.database}", "--no-password"])
        return [*command, *args]

    def execute(self, tool, *args, connected=True, stdin=None, stdout=None):
        env = os.environ.copy()
        # docker forwards a variable name, never the password value in argv.
        if connected:
            if not self.password:
                raise BackupError("Set LEADFORGE_BACKUP_PASSWORD externally; no password argument is accepted")
            env["PGPASSWORD"] = self.password
        else:
            env.pop("PGPASSWORD", None)
        return docker(self.command(tool, *args, connected=connected), env=env, stdin=stdin, stdout=stdout)

    def query(self, sql):
        # SQL is passed on stdin, not logged or interpolated through a shell.
        import tempfile
        with tempfile.TemporaryFile() as stream:
            stream.write(sql.encode("utf-8"))
            stream.seek(0)
            try:
                return self.execute("psql", "-X", "-q", "-A", "-t", "--set=ON_ERROR_STOP=1", "--set=VERBOSITY=sqlstate", stdin=stream).decode("utf-8").strip()
            except BackupError as exc:
                raise BackupError(str(exc) + "; query_id=" + hashlib.sha256(sql.encode()).hexdigest()[:12]) from None

    def server_metadata(self):
        sql = """SELECT json_build_object(
          'database',current_database(), 'postgres_version',current_setting('server_version'),
          'encoding',current_setting('server_encoding'),
          'lc_collate',(SELECT datcollate FROM pg_database WHERE datname=current_database()),
          'lc_ctype',(SELECT datctype FROM pg_database WHERE datname=current_database()),
          'alembic_revision',(SELECT json_agg(version_num ORDER BY version_num) FROM alembic_version),
          'extensions',(SELECT json_agg(extname ORDER BY extname) FROM pg_extension));"""
        metadata = json.loads(self.query(sql))
        if metadata["database"] != self.database or metadata["postgres_version"].split()[0] != "16.15":
            raise BackupError("Database identity/version mismatch; this tool supports PostgreSQL 16.15")
        if metadata["encoding"] != "UTF8" or len(metadata["alembic_revision"] or []) != 1:
            raise BackupError("Expected UTF8 and one stored Alembic revision")
        return metadata

    def require_empty(self):
        sql = """SELECT json_build_object('database',current_database(),
          'encoding',current_setting('server_encoding'), 'version',current_setting('server_version'),
          'objects',(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
          'functions',(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                       WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
          'schemas',(SELECT count(*) FROM pg_namespace WHERE nspname !~ '^pg_'
                     AND nspname NOT IN ('information_schema','public')),
          'extensions',(SELECT count(*) FROM pg_extension WHERE extname <> 'plpgsql'));
        """
        state = json.loads(self.query(sql))
        if (state["database"] != self.database or state["encoding"] != "UTF8"
                or state["version"].split()[0] != "16.15"
                or any(state[key] for key in ("objects", "functions", "schemas", "extensions"))):
            raise BackupError("Restore target must already exist and be empty; no reset/clean is performed")


def inspect_dump(tools, path):
    with Path(path).open("rb") as stream:
        listing = tools.execute("pg_restore", "--list", connected=False, stdin=stream).decode("utf-8")
    schema = set(re.findall(r"^\d+; \d+ \d+ TABLE public (\w+) ", listing, re.MULTILINE))
    data = set(re.findall(r"^\d+; \d+ \d+ TABLE DATA public (\w+) ", listing, re.MULTILINE))
    if not set(TABLES) <= schema or not set(TABLES) <= data:
        raise BackupError("Archive lacks required LeadForge schema/table-data objects")
    return {"tables": sorted(schema), "table_data": sorted(data), "toc_entries": len(re.findall(r"^\d+;", listing, re.MULTILINE))}


def validate_artifact(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix != ".dump":
        raise BackupError("A regular .dump artifact is required")
    metadata_path = Path(str(path) + ".json")
    checksum_path = Path(str(path) + ".sha256")
    if (not metadata_path.is_file() or not checksum_path.is_file()
            or metadata_path.is_symlink() or checksum_path.is_symlink()
            or metadata_path.stat().st_size > 65536 or checksum_path.stat().st_size > 512):
        raise BackupError("Bounded regular manifest/checksum sidecars are required")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected_line = f"{metadata['sha256']}  {path.name}"
        if (metadata["schema_version"] != 1 or metadata["format"] != "custom"
                or metadata["artifact"] != path.name or metadata["size_bytes"] != path.stat().st_size
                or not re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"])
                or checksum_path.read_text(encoding="utf-8").strip() != expected_line
                or sha256(path) != metadata["sha256"]):
            raise BackupError("Backup manifest/checksum/size mismatch")
        container_name(metadata["source"]["container"])
        identifier(metadata["source"]["database"])
        if metadata["postgres_version"].split()[0] != "16.15":
            raise BackupError("Unsupported backup PostgreSQL version")
        revisions = metadata["alembic_revision"]
        if not isinstance(revisions, list) or len(revisions) != 1 or not re.fullmatch(r"[a-zA-Z0-9_]{1,64}", revisions[0]):
            raise BackupError("Invalid stored migration revision")
        with path.open("rb") as stream:
            magic = stream.read(5)
        if magic != b"PGDMP":
            raise BackupError("Not a PostgreSQL custom archive")
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise BackupError("Backup manifest/checksum is invalid or unreadable") from exc
    return metadata


def safe_output_directory(path):
    directory = Path(path).absolute()
    # Local test backups may only enter the ignored backups tree, not src/public.
    resolved = directory.resolve()
    if resolved.is_relative_to(ROOT) and not resolved.is_relative_to(ROOT / "backups"):
        raise BackupError("Inside the repository, output is allowed only under ignored backups/")
    if any(parent.is_symlink() for parent in (directory, *directory.parents)):
        raise BackupError("Backup output must not traverse symbolic links")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not directory.is_dir():
        raise BackupError("Backup destination is not a directory")
    return directory


def backup(tools, output_dir, environment):
    started = time.monotonic()
    log("backup.started", source_container=tools.container, database=tools.database, environment=environment)
    bundle = None
    created = []
    try:
        directory = safe_output_directory(output_dir)
        name = "leadforge-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
        bundle = directory / name
        bundle.mkdir(mode=0o700)  # Exclusive bundle: never overwrite an older backup.
        metadata = tools.server_metadata()
        for tool in ("pg_dump", "pg_restore"):
            version = docker(["run", "--rm", "--network=none", CLIENT_IMAGE, tool, "--version"]).decode()
            if " 16.15 " not in version:
                raise BackupError("Matching PostgreSQL 16.15 clients are required")
        partial = bundle / (name + ".dump.partial")
        created.append(partial)
        with partial.open("xb") as stream:
            tools.execute("pg_dump", "--format=custom", "--no-privileges", "--lock-wait-timeout=10s", stdout=stream)
            stream.flush()
            os.fsync(stream.fileno())
        inspection = inspect_dump(tools, partial)
        artifact = bundle / (name + ".dump")
        checksum = sha256(partial)
        metadata.update(schema_version=1, format="custom", artifact=artifact.name,
                        created_at_utc=datetime.now(timezone.utc).isoformat(),
                        source={"container": tools.container, "database": tools.database},
                        environment=environment, size_bytes=partial.stat().st_size, sha256=checksum,
                        inspection=inspection)
        for sidecar, text in ((Path(str(artifact) + ".json"), json.dumps(metadata, indent=2) + "\n"),
                              (Path(str(artifact) + ".sha256"), f"{checksum}  {artifact.name}\n")):
            created.append(sidecar)
            with sidecar.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
        # Only an inspected completed archive receives the .dump suffix.
        if artifact.exists():
            raise BackupError("Backup name collision; refusing overwrite")
        partial.rename(artifact)
        created.append(artifact)
        validate_artifact(artifact)
        log("backup.completed", artifact=artifact.name, size_bytes=metadata["size_bytes"],
            sha256=checksum, duration_seconds=round(time.monotonic() - started, 3))
        return artifact
    except Exception:
        # Remove only paths allocated by this operation in its exclusive bundle.
        for path in created:
            if path.is_file() and not path.is_symlink():
                path.unlink()
        if bundle is not None and bundle.exists():
            try:
                bundle.rmdir()
            except OSError:
                pass
        raise


def restore(tools, artifact, confirm_target):
    started = time.monotonic()
    metadata = validate_artifact(artifact)
    log("restore.started", target_container=tools.container, database=tools.database)
    if confirm_target != f"{tools.container}/{tools.database}":
        raise BackupError("Confirm the exact container/database target; empty database only")
    if tools.database in {metadata["source"]["database"], "leadforge_dev", "leadforge", "postgres", "template0", "template1"}:
        raise BackupError("Refusing source/default/runtime database target")
    inspect_dump(tools, artifact)
    tools.require_empty()
    with Path(artifact).open("rb") as stream:
        tools.execute("pg_restore", "--single-transaction", "--exit-on-error",
                      "--no-owner", "--no-privileges", stdin=stream)
    restored = tools.server_metadata()
    if restored["alembic_revision"] != metadata["alembic_revision"]:
        raise BackupError("Restored migration revision mismatch; recovery not verified")
    log("restore.completed", database=tools.database, alembic_revision=restored["alembic_revision"],
        duration_seconds=round(time.monotonic() - started, 3))
    return restored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["backup", "inspect", "restore"])
    parser.add_argument("--container")
    parser.add_argument("--database")
    parser.add_argument("--user")
    parser.add_argument("--environment", choices=["test", "development", "production"])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--confirm-target")
    args = parser.parse_args()
    try:
        if args.operation != "inspect" and not all((args.container, args.database, args.user, args.environment)):
            raise BackupError("Explicit --container, --database, --user and --environment are required")
        tools = PgTools(args.container or "offline", args.database or "offline", args.user or "offline")
        if args.operation == "backup":
            if args.output_dir is None:
                raise BackupError("Explicit --output-dir is required")
            backup(tools, args.output_dir, args.environment)
        else:
            if args.artifact is None:
                raise BackupError("Explicit --artifact is required")
            if args.operation == "inspect":
                validate_artifact(args.artifact)
                log("backup.inspected", **inspect_dump(tools, args.artifact))
            else:
                restore(tools, args.artifact, args.confirm_target)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, BackupError) else "Operation failed; check filesystem/container prerequisites"
        log(f"{args.operation}.failed", reason=reason, exception_type=type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
