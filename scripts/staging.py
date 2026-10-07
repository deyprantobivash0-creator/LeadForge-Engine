"""Small staging preparation, safe source packaging and trusted-HTTPS health helper."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("backend", "alembic", "frontend", "deploy", "scripts", "tests", "tests_postgres", "docs", ".github")
SOURCE_FILES = ("Dockerfile", "compose.runtime.yml", "compose.staging.yml", "docker-compose.yml", "alembic.ini",
                "requirements.txt", "requirements-dev.txt", "requirements-ci.txt", "README.md", "AGENTS.md",
                ".dockerignore", ".gitignore", ".gitleaks.toml", "pytest.ini", "package.json", "package-lock.json")


def hostname(value):
    if len(value) > 253 or "." not in value or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in value.split(".")):
        raise ValueError("Supply one explicit lowercase DNS hostname, without scheme, port or path")
    return value


def render_proxy(host):
    host = hostname(host)
    source = (ROOT / "deploy/nginx.conf").read_text()
    marker = "        listen 8080;"
    if source.count(marker) != 1:
        raise ValueError("Canonical proxy changed; review staging rendering")
    source = source.replace(marker, "\n".join((
        "        listen 8443 ssl;", f"        server_name {host};",
        "        ssl_certificate /run/secrets/tls_certificate;",
        "        ssl_certificate_key /run/secrets/tls_private_key;",
        "        ssl_protocols TLSv1.2 TLSv1.3;", "        ssl_session_tickets off;",
        f'        if ($host != "{host}") {{ return 400; }}')))
    # Nginx terminates TLS itself; no outer proxy whose headers need trust.
    # URI redirects must never downgrade the publicly HTTPS same-origin URL.
    source = source.replace("            proxy_pass $backend$request_uri;", "            proxy_pass $backend$request_uri;\n            proxy_redirect http://$http_host/ https://$http_host/;")
    source = source.replace("    server {", f'''    server {{
        listen 8080;
        server_name {host};
        if ($host != "{host}") {{ return 400; }}
        return 308 https://{host}$request_uri;
    }}
    server {{
        listen 127.0.0.1:8081;
        location = /frontend-health {{ access_log off; return 200 'healthy'; }}
    }}
    server {{''', 1)
    source = source.replace("        location /assets/ {", '''        location = /robots.txt { default_type text/plain; return 200 "User-agent: *\\nDisallow: /\\n"; }
        location ~ ^/(docs|redoc|openapi\\.json)$ { return 404; }
        location /assets/ {''')
    headers = (ROOT / "deploy/security-headers.conf").read_text()
    headers += '\nadd_header Strict-Transport-Security "max-age=86400" always;\nadd_header X-Robots-Tag "noindex, nofollow, noarchive" always;\n'
    return source, headers


def source_paths():
    candidates = [ROOT / name for name in SOURCE_FILES]
    for directory in SOURCE_DIRS:
        candidates.extend((ROOT / directory).rglob("*"))
    for path in sorted(set(candidates)):
        relative = path.relative_to(ROOT)
        # This report records the digest; it is not a build/runtime input.
        if relative.as_posix() == "docs/STEP_5H_VERIFICATION.md":
            continue
        if (path.is_symlink() or not path.is_file() or any(part in {"node_modules", "dist", "__pycache__", ".pytest_cache", "secrets", "backups"} for part in relative.parts)
                or any(part.startswith(".env") for part in relative.parts)
                or path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".dump", ".pem", ".key", ".pyc", ".log", ".env"}
                or path.name.endswith((".dump.json", ".dump.sha256", "_password"))):
            continue
        if path.suffix.lower() not in {".py", ".js", ".jsx", ".mjs", ".json", ".toml", ".ini", ".yml", ".yaml", ".md", ".txt", ".conf", ".css", ".html", ".svg", ".png", ".ico", ""}:
            continue
        yield path


def snapshot(output):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / ".staging-artifacts"):
        raise ValueError("Repository release artifacts belong only under ignored .staging-artifacts/")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    rows = [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in source_paths()]
    rows.sort(key=lambda row: row["path"])  # Identical canonical order on Windows/Linux.
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    manifest = {"source_sha256": digest, "release": "5h-" + digest[:16], "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "git_head": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")), "files": rows}
    archive = output / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for row in rows:
            path = ROOT / row["path"]
            # Refuse concurrent source changes instead of claiming a stale identity.
            if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError("Source changed while packaging; create a fresh snapshot")
            bundle.add(path, arcname=row["path"], recursive=False)
    with tarfile.open(archive, "r:gz") as bundle:
        for row in rows:
            with bundle.extractfile(row["path"]) as stream:
                if hashlib.sha256(stream.read()).hexdigest() != row["sha256"]:
                    raise ValueError("Archive/source fingerprint mismatch")
    manifest["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({key: value for key, value in manifest.items() if key != "files"}))


def prepare(host, directory):
    host = hostname(host)
    directory = Path(directory).absolute()
    if any(parent.is_symlink() for parent in (directory, *directory.parents)):
        raise ValueError("Private staging directory must not traverse symlinks")
    resolved = directory.resolve()
    if resolved.is_relative_to(ROOT) and not resolved.is_relative_to(ROOT / "secrets"):
        raise ValueError("Repository private files belong only under ignored secrets/")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    for name in ("admin", "migrator", "app", "backup", "qa"):
        path = directory / (name + "_password")
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise ValueError("Private credential must be a regular file")
            value = path.read_text().strip()
            if len(value) < 32 or any(c.isspace() for c in value):
                raise ValueError("Existing staging credential is invalid; coordinate rotation explicitly")
            continue  # Never rotate initialized DB passwords by accident.
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(secrets.token_urlsafe(48) + "\n")
        # Parent 0700 protects the bind-mounted file on host; container non-root
        # users need to read these Docker Compose file-backed secrets.
        path.chmod(0o444)
    proxy, headers = render_proxy(host)
    for name, value in (("nginx.conf", proxy), ("security-headers.conf", headers)):
        path = directory / name
        if path.is_symlink():
            raise ValueError("Refusing linked config target")
        path.write_text(value)
    print("Staging private credentials/config prepared; supply trusted fullchain.pem and privkey.pem separately")


def health(host):
    host = hostname(host)
    for endpoint in ("/health", "/ready"):
        with urllib.request.urlopen("https://" + host + endpoint, timeout=15) as response:
            body = json.load(response)
            if response.status != 200 or not body.get("success"):
                raise ValueError("Staging health check failed")
    print("PASS trusted HTTPS liveness/readiness")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "snapshot", "health"])
    parser.add_argument("--hostname")
    parser.add_argument("--private-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "snapshot":
            if args.output_dir is None:
                raise ValueError("Explicit new --output-dir required")
            snapshot(args.output_dir)
        elif args.operation == "prepare":
            if args.private_dir is None:
                raise ValueError("Explicit --private-dir required")
            prepare(args.hostname, args.private_dir)
        else:
            health(args.hostname)
    except Exception:
        print("Staging helper failed; check explicit paths/hostname, source stability or trusted HTTPS readiness", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
