"""LOCAL staging rehearsal, explicitly not remote staging completion. Own project only."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.staging import prepare
from scripts.staging_smoke import smoke
from scripts.postgres_backup import PgTools, backup, restore, sha256
from scripts.verify_backup_recovery import fingerprint, comparable


def certificate(directory, host):
    # Disposable self-signed local CA only. Public staging needs a real trusted cert.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False).sign(key, hashes.SHA256()))
    (directory / "fullchain.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / "privkey.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (directory / "privkey.pem").chmod(0o444)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT / ".staging-artifacts"):
        raise ValueError("Local rehearsal evidence only under ignored .staging-artifacts/")
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid4().hex[:12]
    project = "leadforge-5h-check-" + run_id
    host = "staging.leadforge.test"
    private = ROOT / "secrets" / project
    prepare(host, private)
    certificate(private, host)
    override = output / "local.yml"
    override.write_text('services:\n  frontend:\n    ports: !override ["127.0.0.1:58080:8080", "127.0.0.1:58443:8443"]\n')
    env = os.environ.copy()
    env.update(LEADFORGE_STAGE_HOST=host, LEADFORGE_STAGE_PRIVATE_DIR=str(private), LEADFORGE_STAGE_RELEASE="5h-local-verification")
    command = ["docker", "compose", "--env-file", "deploy/compose.env", "-f", "compose.staging.yml", "-f", str(override), "-p", project]
    credentials = [path.read_text().strip() for path in private.glob("*_password")]
    started = False
    original_hash = sha256(ROOT / "leadforge.db")
    evidence = {"scope": "LOCAL REHEARSAL ONLY; no public certificate or remote target", "project": project, "status": "RUNNING"}

    def run(args, check=True, timeout=240):
        result = subprocess.run(args, env=env, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        if any(value in result.stdout + result.stderr for value in credentials):
            raise ValueError("Synthetic credential leaked in subprocess output")
        if check and result.returncode:
            # Safe Compose lifecycle messages only; raw application logs handled separately.
            print(result.stderr[-2000:])
            raise ValueError("Local staging subprocess failed")
        return result

    try:
        run([*command, "config", "--quiet"])
        started = True
        run([*command, "up", "-d", "--wait", "--wait-timeout", "180"], timeout=240)
        postgres = run([*command, "ps", "-q", "postgres"]).stdout.strip()
        tools = PgTools(postgres, "leadforge_stage", "leadforge_stage_admin", (private / "admin_password").read_text().strip())
        state = json.loads(tools.query("SELECT json_build_object('head',(SELECT version_num FROM alembic_version),'roles',(SELECT json_agg(json_build_object('name',rolname,'superuser',rolsuper,'createdb',rolcreatedb,'createrole',rolcreaterole,'bypassrls',rolbypassrls)) FROM pg_roles WHERE rolname IN ('leadforge_stage_app','leadforge_stage_migrator','leadforge_stage_backup')),'app_create',has_schema_privilege('leadforge_stage_app','public','CREATE'),'app_alembic_update',has_table_privilege('leadforge_stage_app','alembic_version','UPDATE'));"))
        assert state["head"] == "e5d4c3b2a1f0" and not state["app_create"] and not state["app_alembic_update"]
        assert all(not row[key] for row in state["roles"] for key in ("superuser", "createdb", "createrole", "bypassrls"))
        evidence["role_model"] = state
        seeded = run([*command, "--profile", "qa", "run", "--rm", "seed"]).stdout.strip()
        fixture = json.loads(seeded.splitlines()[-1])
        (output / "fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
        context = ssl.create_default_context(cafile=str(private / "fullchain.pem"))
        original_resolver = socket.getaddrinfo
        # Exact synthetic name only; preserve TLS SNI/hostname validation and Secure cookies.
        def resolve(name, port, *args, **kwargs):
            if name == host:
                return original_resolver("127.0.0.1", 58443, *args, **kwargs)
            return original_resolver(name, port, *args, **kwargs)
        socket.getaddrinfo = resolve
        try:
            evidence["https_smoke"] = smoke(host, fixture["fixtures"], (private / "qa_password").read_text().strip(), context=context)
            # Recreating containers discards their Docker logs. Capture privacy-
            # checked correlation evidence before the persistence/redeploy test.
            initial_logs = run([*command, "logs", "--no-color"]).stdout
            import urllib.request, urllib.error
            def probe(path, expected, headers=None):
                request = urllib.request.Request("https://" + host + path, headers=headers or {})
                try:
                    response = urllib.request.urlopen(request, context=context, timeout=15)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    assert response.status == expected
                    body = response.read()
                    assert not any(value.encode() in body for value in credentials)
            probe("/health", 400, {"Host": "invalid.example"})
            probe("/health", 200, {"X-Forwarded-Proto": "http", "X-Forwarded-For": "untrusted"})
            baseline = fingerprint(tools)
            run([*command, "restart", "backend", "frontend"])
            for _ in range(30):
                try:
                    probe("/ready", 200); break
                except Exception:
                    time.sleep(1)
            else:
                raise ValueError("Restart readiness did not recover")
            assert comparable(fingerprint(tools)) == comparable(baseline)
            evidence["restart_persistence"] = True
            backend_id = run([*command, "ps", "-q", "backend"]).stdout.strip()
            identity = json.loads(run(["docker", "inspect", backend_id]).stdout)[0]
            assert identity["Name"] == "/" + project + "-backend-1" and identity["State"]["Running"]
            # docker kill marks a manual stop and suppresses restart policy.
            # Signal only this verified disposable backend from the ancestor PID
            # namespace, so Docker observes a genuine unexpected process exit.
            pid = identity["State"]["Pid"]
            run(["docker", "run", "--rm", "--network", "none", "--pid=host", "--user", "0:0", "--cap-drop=ALL", "--cap-add=KILL",
                 "--security-opt=no-new-privileges:true", "--entrypoint", "python", "leadforge-backend:5h-local-verification",
                 "-c", f"import os; os.kill({pid},9)"])
            time.sleep(2)
            for _ in range(30):
                try:
                    probe("/ready", 200); break
                except Exception:
                    time.sleep(1)
            else:
                raise ValueError("Process crash did not recover")
            assert int(run(["docker", "inspect", "--format", "{{.RestartCount}}", backend_id]).stdout.strip()) >= 1
            evidence["process_crash_recovery"] = True
            run([*command, "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180"], timeout=240)
            postgres = run([*command, "ps", "-q", "postgres"]).stdout.strip()
            tools = PgTools(postgres, "leadforge_stage", "leadforge_stage_admin", (private / "admin_password").read_text().strip())
            probe("/ready", 200)
            assert comparable(fingerprint(tools)) == comparable(baseline)
            evidence["redeploy_persistence"] = True
            run([*command, "stop", "postgres"])
            probe("/health", 200); probe("/ready", 503)
            run([*command, "start", "postgres"])
            for _ in range(45):
                try:
                    probe("/ready", 200); break
                except Exception:
                    time.sleep(1)
            else:
                raise ValueError("DB recovery readiness did not recover")
            evidence["database_outage_recovery"] = True
        finally:
            socket.getaddrinfo = original_resolver
        archive_tools = PgTools(postgres, "leadforge_stage", "leadforge_stage_backup", (private / "backup_password").read_text().strip())
        artifact = backup(archive_tools, ROOT / "backups" / project, "production")
        backup_fingerprint = fingerprint(tools)
        target = "leadforge_5h_restore_" + run_id
        tools.query(f"CREATE DATABASE {target} TEMPLATE template0 ENCODING 'UTF8';")
        recovered = PgTools(postgres, target, "leadforge_stage_admin", (private / "admin_password").read_text().strip())
        restore(recovered, artifact, f"{postgres}/{target}")
        assert comparable(fingerprint(recovered)) == comparable(backup_fingerprint)
        evidence["backup_restore"] = {"status": "PASS", "size_bytes": artifact.stat().st_size, "sha256": sha256(artifact)}
        logs = initial_logs + run([*command, "logs", "--no-color"]).stdout
        for request_id in evidence["https_smoke"]["request_ids"]:
            assert request_id in logs
        assert '"event": "http.request.completed"' in logs or '"event":"http.request.completed"' in logs
        evidence["log_privacy_correlation"] = True
        images = {}
        for name in ("backend", "frontend", "postgres"):
            images[name] = run(["docker", "image", "inspect", "--format", "{{.Id}}", "leadforge-" + name + ":5h-local-verification"]).stdout.strip()
        evidence["images"] = images
        failed_project = "leadforge-5h-fail-" + run_id
        failure_overlay = output / "failure.yml"
        failure_overlay.write_text('services:\n  migrate:\n    environment:\n      LEADFORGE_STAGE_ROLE: invalid\n')
        failed_command = [*command[:-2], "-f", str(failure_overlay), "-p", failed_project]
        try:
            failed = run([*failed_command, "up", "-d", "backend"], check=False)
            assert failed.returncode != 0
            backend_id = run([*failed_command, "ps", "-a", "-q", "backend"]).stdout.strip()
            if backend_id:
                assert run(["docker", "inspect", "--format", "{{.State.Running}}", backend_id]).stdout.strip() == "false"
            migration_id = run([*failed_command, "ps", "-a", "-q", "migrate"]).stdout.strip()
            assert int(run(["docker", "inspect", "--format", "{{.State.ExitCode}}", migration_id]).stdout.strip()) != 0
            evidence["migration_failure_blocks_backend"] = True
        finally:
            run([*failed_command, "down", "--volumes", "--remove-orphans"])
        evidence["status"] = "PASS"
        (output / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print("PASS local staging TLS/policy/roles/migration/app/restart/redeploy/outage/backup rehearsal; remote validation pending")
    finally:
        if started:
            # Generated unique project only, never normal runtime/staging deployment.
            if not project.startswith("leadforge-5h-check-"):
                raise ValueError("Cleanup identity refusal")
            run([*command, "down", "--volumes", "--remove-orphans"])
        if sha256(ROOT / "leadforge.db") != original_hash:
            raise ValueError("Original SQLite integrity changed")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import traceback
        frame = traceback.extract_tb(error.__traceback__)[-1]
        print("Local staging rehearsal failed (" + type(error).__name__ + ", " + Path(frame.filename).name + ":" + str(frame.lineno) + "); no remote completion claimed", file=sys.stderr)
        raise SystemExit(1) from None
