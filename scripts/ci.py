"""Cross-platform CI commands. No private dotenv, customer DB or real AI calls."""
import argparse
import ast
import hashlib
import json
import os
import re
from secrets import token_urlsafe
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
HEAD = "e5d4c3b2a1f0"
GITLEAKS = "ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"


def environment():
    env = os.environ.copy()
    for key in ("LEADFORGE_ENV_FILE", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "HUBSPOT_ACCESS_TOKEN",
                "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"):
        env.pop(key, None)
    env.update(AI_PROVIDER="mock", ENVIRONMENT="development", LEADFORGE_CI="1",
               DATABASE_URL="sqlite:///:memory:", LANGSMITH_TRACING="false",
               LANGCHAIN_TRACING_V2="false", PYTHONDONTWRITEBYTECODE="1")
    return env


def run(args, *, env=None, cwd=ROOT, capture=False, timeout=600):
    # Never echo command arguments: they may contain a disposable database URL.
    return subprocess.run(args, cwd=cwd, env=env or environment(), check=True,
                          capture_output=capture, text=True, timeout=timeout)


def pytest_suite(path, env):
    run([sys.executable, "-B", "-m", "pytest", "-p", "scripts.ci_pytest",
         "-q", "--tb=short", path], env=env)


def backend():
    run([sys.executable, "-m", "pip", "check"])
    pytest_suite("tests", environment())


def migration_modules():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config(str(ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    if scripts.get_heads() != [HEAD]:
        raise RuntimeError("Unexpected Alembic head(s); review migration contract")
    revisions = list(scripts.walk_revisions())  # Imports every revision module.
    for revision in revisions:
        if not callable(revision.module.upgrade) or not callable(revision.module.downgrade):
            raise RuntimeError("Migration entry point missing")
    ast.parse((ROOT / "alembic/env.py").read_text(encoding="utf-8-sig"))
    print(f"Migration modules import cleanly; single head {HEAD}")


def postgres():
    # Reuse the fixture's exact disposable-service contract; never loosen it for CI.
    import psycopg
    from psycopg import sql
    from sqlalchemy.engine import make_url
    raw = os.environ.get("LEADFORGE_POSTGRES_ADMIN_URL")
    if not raw:
        raise RuntimeError("LEADFORGE_POSTGRES_ADMIN_URL is required; refusing skips")
    url = make_url(raw)
    if (url.drivername != "postgresql+psycopg" or url.host != "127.0.0.1"
            or url.port != 55432 or url.database != "leadforge_dev"
            or url.username != "leadforge_dev"):
        raise RuntimeError("Only the disposable loopback PostgreSQL service is allowed")
    connect = dict(host=url.host, port=url.port, dbname=url.database,
                   user=url.username, password=url.password, connect_timeout=5)
    name = "leadforge_ci_" + uuid4().hex[:12]
    # pg_isready over a Unix socket can see the entrypoint's temporary server.
    # Prove the final TCP listener accepts an authenticated query before DDL.
    deadline = time.monotonic() + 60
    while True:
        try:
            admin = psycopg.connect(**connect, autocommit=True)
            break
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise RuntimeError("Disposable PostgreSQL TCP readiness timed out") from None
            time.sleep(1)
    with admin:
        version = admin.execute("SHOW server_version").fetchone()[0]
        if version.split()[0] != "16.15":
            raise RuntimeError("CI requires PostgreSQL 16.15")
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    print("Verified PostgreSQL 16.15; fresh disposable migration database")
    env = environment()
    env["DATABASE_URL"] = url.set(database=name).render_as_string(hide_password=False)
    try:
        migration_modules()
        run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env)
        with psycopg.connect(**{**connect, "dbname": name}) as db:
            heads = db.execute("SELECT version_num FROM alembic_version").fetchall()
            if heads != [(HEAD,)]:
                raise RuntimeError("Stored migration revision does not match expected head")
        print(f"Fresh base -> head verified: {HEAD}")
    finally:
        with psycopg.connect(**connect, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    env = environment()
    env.update(LEADFORGE_POSTGRES_ADMIN_URL=raw, LEADFORGE_REQUIRE_NO_SKIPS="1")
    pytest_suite("tests_postgres", env)


def frontend():
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("Node 22.22.2 and npm are required on PATH")
    for args in (["ci"], ["run", "lint"], ["run", "build"]):
        run([npm, *args], cwd=ROOT / "frontend")


def security():
    run([sys.executable, "-m", "pip", "check"])
    # pip-audit lacks reliable severity for all records: fail closed on ANY finding.
    # Audit the installed resolved environment, including transitives and CI tools.
    run([sys.executable, "-m", "pip_audit", "--progress-spinner", "off", "--timeout", "30"])
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("npm is required")
    run([npm, "audit", "--audit-level=high"], cwd=ROOT / "frontend")


def source_files():
    result = run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], capture=True)
    for name in filter(None, result.stdout.split("\0")):
        path = ROOT / name
        if (not path.is_file() or path.is_symlink() or path.name == ".env"
                or (path.name.startswith(".env.") and path.name != ".env.example")
                or path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}
                or any(part in {".git", ".venv-ci", "node_modules", "venv", "dist"} for part in path.relative_to(ROOT).parts)):
            continue
        yield name, path


def secrets():
    # Stage only nonprivate source. Do not mount the live repo (with .env/DBs).
    with tempfile.TemporaryDirectory(prefix="leadforge-ci-secrets-") as folder:
        stage = Path(folder)
        for name, path in source_files():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        native = shutil.which("gitleaks")
        if native:
            if run([native, "version"], capture=True).stdout.strip() != "8.30.1":
                raise RuntimeError("Local Gitleaks must be version 8.30.1")
            report = stage / "redacted-report.json"
            result = subprocess.run([native, "dir", str(stage), "--config", str(stage / ".gitleaks.toml"),
                                     "--redact=100", "--exit-code=1", "--report-format=json",
                                     "--report-path", str(report)], cwd=ROOT, env=environment(), timeout=120)
            if result.returncode:
                if report.exists():
                    for finding in json.loads(report.read_text()):
                        print(json.dumps({key: finding.get(key) for key in ("File", "StartLine", "RuleID")}))
                raise RuntimeError("Gitleaks failed; only finding locations are displayed")
            secret_negative_probe(stage, [native, "dir", str(stage), "--config", str(stage / ".gitleaks.toml"), "--redact=100", "--exit-code=1"])
            return
        args = ["docker", "run", "--rm", "--network=none", "-v", f"{stage}:/audit:ro", GITLEAKS]
        run(["docker", "pull", GITLEAKS])
        run([*args, "dir", "/audit", "--config", "/audit/.gitleaks.toml", "--redact=100", "--exit-code=1"])
        secret_negative_probe(stage, [*args, "dir", "/audit", "--config", "/audit/.gitleaks.toml", "--redact=100", "--exit-code=1"])


def secret_negative_probe(stage, command):
    # Never save this synthetic probe to repository source. A global path waiver
    # must not make a new secret in the reviewed migration-test file invisible.
    target = stage / "tests/test_auth_migration.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('api_key = "sk-' + token_urlsafe(48) + '"\n', encoding="utf-8")
    result = subprocess.run(command, cwd=ROOT, env=environment(), capture_output=True, timeout=120)
    if result.returncode != 1:
        raise RuntimeError("Gitleaks negative control failed; narrow exception must detect new secrets")
    print("Secret scanner negative control passed")


def hygiene():
    run(["git", "diff", "--check"])
    if os.environ.get("GITHUB_ACTIONS") == "true":
        base = os.environ.get("CI_DIFF_BASE", "")
        if base and base != "0" * 40:
            if not re.fullmatch(r"[0-9a-f]{40}", base):
                raise RuntimeError("Invalid CI diff base")
            run(["git", "diff", "--check", base, "HEAD"])
    # git diff does not include untracked files. Check only new 5F files here;
    # existing source is not subject to a new repository-wide formatting policy.
    bad = []
    for name, path in source_files():
        if not (name.startswith(".github/workflows/") or name.startswith("scripts/ci")
                or name in {"requirements-ci.txt", ".gitleaks.toml", "docs/CI.md", "docs/STEP_5F_VERIFICATION.md"}):
            continue
        if path.suffix.lower() not in {".py", ".yml", ".yaml", ".toml", ".md", ".txt"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if line.rstrip(" \t") != line:
                bad.append(f"{name}:{number}")
    if bad:
        raise RuntimeError("Trailing whitespace: " + ", ".join(bad[:20]))
    print("Diff and source whitespace checks passed")


def containers():
    # Unique Compose project isolates containers/volumes from existing local stack.
    project = "leadforge-ci-" + uuid4().hex[:12]
    env = environment()
    env["LEADFORGE_RUNTIME_DB_PASSWORD"] = "synthetic-ci-" + uuid4().hex
    env["LEADFORGE_CI_IMAGE_NAMESPACE"] = project
    command = ["docker", "compose", "--env-file", "deploy/compose.env",
               "-f", "compose.runtime.yml", "-f", "deploy/compose.ci.yml", "-p", project]
    run(["docker", "compose", "--env-file", "deploy/compose.env", "-f", "docker-compose.yml", "config", "--quiet"], env=env)
    run([*command, "config", "--quiet"], env=env)
    try:
        run([*command, "build", "--no-cache"], env=env, timeout=1500)
        run([*command, "up", "-d", "--wait", "--wait-timeout", "180"], env=env, timeout=240)
        smoke = '''
import json, os, urllib.request
from urllib.parse import urlsplit
assert os.environ["AI_PROVIDER"] == "mock"
assert os.environ["LEADFORGE_CI"] == "1"
secret = urlsplit(os.environ["DATABASE_URL"]).password.encode()
for endpoint in ("/", "/frontend-health", "/health", "/ready"):
    request = urllib.request.Request("http://frontend:8080" + endpoint,
                                     headers={"Host": "127.0.0.1:8080"})
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read()
        assert response.status == 200
        assert secret not in body
        if endpoint == "/":
            assert b'<div id="root">' in body
        if endpoint == "/ready":
            assert json.loads(body)["database"] == "ok"
print("PASS private HTTP smoke; mock AI; no response secret leak")
'''
        run([*command, "exec", "-T", "backend", "python", "-c", smoke], env=env, timeout=60)
        logs = run([*command, "logs", "--no-color"], env=env, capture=True)
        if env["LEADFORGE_RUNTIME_DB_PASSWORD"] in logs.stdout + logs.stderr:
            raise RuntimeError("Synthetic secret leaked in runtime logs")
        print("Clean image builds, Compose, HTTP smoke and log privacy passed")
    finally:
        run([*command, "down", "--volumes", "--remove-orphans"], env=env, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", choices=["backend", "postgres", "frontend", "security", "secrets", "containers", "hygiene", "migrations", "full"])
    args = parser.parse_args()
    original = ROOT / "leadforge.db"
    before = hashlib.sha256(original.read_bytes()).hexdigest() if original.exists() else None
    try:
        gates = {"backend": backend, "postgres": postgres, "frontend": frontend,
                 "security": security, "secrets": secrets, "containers": containers,
                 "hygiene": hygiene, "migrations": migration_modules}
        if args.gate == "full":
            for gate in ("backend", "postgres", "frontend", "security", "secrets", "containers", "hygiene"):
                print(f"Starting {gate}", flush=True)
                gates[gate]()
        else:
            gates[args.gate]()
    finally:
        after = hashlib.sha256(original.read_bytes()).hexdigest() if original.exists() else None
        if before != after:
            raise RuntimeError("leadforge.db integrity changed")
        print("leadforge.db unchanged" if before else "leadforge.db absent; not created")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No raw subprocess/DB exception repr: URLs and credentials may be embedded.
        print(f"CI gate failed ({type(exc).__name__}); inspect preceding gate output", file=sys.stderr)
        raise SystemExit(1) from None
