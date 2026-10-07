"""Real, synthetic-only Step 5G recovery drill. Never targets existing volumes."""
import argparse
import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.postgres_backup import (BackupError, CLIENT_IMAGE, PgTools, TABLES,
                                     backup, docker, inspect_dump, log, restore,
                                     sha256, validate_artifact)

HEAD = "e5d4c3b2a1f0"
LOGIN_PASSWORD = "synthetic 5g recovery fixture password"


def canonical_constraints(constraints):
    # PostgreSQL 16 pg_dump/restore can distribute an array-to-text[] cast
    # into per-element casts when rebuilding this specific CHECK. Preserve all
    # names/other definitions and accept only these two equivalent expressions.
    equivalent = {
        "CHECK (((role)::text = ANY ((ARRAY['owner'::character varying, 'admin'::character varying, 'member'::character varying])::text[])))",
        "CHECK (((role)::text = ANY (ARRAY[('owner'::character varying)::text, ('admin'::character varying)::text, ('member'::character varying)::text])))",
    }
    return [[table, name, "CHECK role IN ('owner','admin','member')"
             if table == "organization_memberships" and definition in equivalent else definition]
            for table, name, definition in constraints]


def fingerprint(tools):
    tables = {}
    for table in TABLES:
        order = "version_num" if table == "alembic_version" else "id"
        # Credential material stays in the dump, never in this manifest.
        rows = json.loads(tools.query(f"SELECT coalesce(jsonb_agg(to_jsonb(t) - ARRAY['password_hash','token_hash','csrf_token_hash'] ORDER BY {order}), '[]'::jsonb) FROM public.{table} t;"))
        encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        tables[table] = {"count": len(rows), "logical_sha256": hashlib.sha256(encoded).hexdigest()}
    integrity = json.loads(tools.query("""SELECT json_build_object(
      'memberships_orphaned',(SELECT count(*) FROM organization_memberships m LEFT JOIN users u ON u.id=m.user_id LEFT JOIN organizations o ON o.id=m.organization_id WHERE u.id IS NULL OR o.id IS NULL),
      'leads_orphaned',(SELECT count(*) FROM leads l LEFT JOIN organizations o ON o.id=l.organization_id WHERE o.id IS NULL),
      'analyses_orphaned',(SELECT count(*) FROM lead_analysis a LEFT JOIN organizations o ON o.id=a.organization_id LEFT JOIN leads l ON l.id=a.lead_id AND l.organization_id=a.organization_id WHERE o.id IS NULL OR (a.lead_id IS NOT NULL AND l.id IS NULL)),
      'sessions_orphaned',(SELECT count(*) FROM auth_sessions s LEFT JOIN users u ON u.id=s.user_id WHERE u.id IS NULL),
      'jobs_orphaned',(SELECT count(*) FROM ingestion_jobs j LEFT JOIN organizations o ON o.id=j.organization_id WHERE o.id IS NULL),
      'invalid_constraints',(SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public' AND NOT convalidated));"""))
    if any(integrity.values()):
        raise BackupError("Synthetic recovery relational integrity failed")
    constraints = json.loads(tools.query("""SELECT coalesce(jsonb_agg(jsonb_build_array(t.relname, c.conname, pg_get_constraintdef(c.oid)) ORDER BY t.relname,c.conname), '[]'::jsonb) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace JOIN pg_class t ON t.oid=c.conrelid WHERE n.nspname='public';"""))
    constraints = canonical_constraints(constraints)
    current = json.loads(tools.query("""SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY organization_id,lead_id), '[]'::jsonb) FROM (SELECT DISTINCT ON (organization_id,lead_id) organization_id,lead_id,id,lead_score,priority,created_at FROM lead_analysis WHERE lead_id IS NOT NULL ORDER BY organization_id,lead_id,created_at DESC,id DESC) r;"""))
    return {"tables": tables, "integrity": integrity,
            "constraint_sha256": hashlib.sha256(json.dumps(constraints, sort_keys=True).encode()).hexdigest(), "constraints": constraints,
            "current_analysis": current, "metadata": tools.server_metadata()}


def comparable(manifest):
    # Fresh restore databases intentionally have different names.
    result = json.loads(json.dumps(manifest))
    result["metadata"].pop("database")
    return result


def seed(url):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.core.passwords import hash_password
    from backend.core.session_tokens import generate_session_token, hash_session_token
    from backend.models import (AuthSession, IngestionJob, Lead, LeadAnalysis,
                                Organization, OrganizationMembership, User)
    engine = create_engine(url)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stamp = now - timedelta(days=1)
    token = generate_session_token()
    with Session(engine) as db, db.begin():
        organizations = [Organization(name="Synthetic 恢复 বাংলা Alpha", slug="recovery-synthetic-alpha", created_at=stamp),
                         Organization(name="Synthetic São Paulo Beta", slug="recovery-synthetic-beta", created_at=stamp)]
        users = [User(email="recovery-alpha@example.com", password_hash=hash_password(LOGIN_PASSWORD), created_at=stamp, updated_at=stamp),
                 User(email="recovery-beta@example.com", password_hash=hash_password(LOGIN_PASSWORD), created_at=stamp, updated_at=stamp)]
        db.add_all([*organizations, *users])
        db.flush()
        db.add_all([OrganizationMembership(user_id=users[0].id, organization_id=organizations[0].id, role="owner", created_at=stamp, updated_at=stamp),
                    OrganizationMembership(user_id=users[1].id, organization_id=organizations[1].id, role="member", created_at=stamp, updated_at=stamp)])
        leads = []
        for i, status in enumerate(("New", "Meeting", "Won", "Lost")):
            lead = Lead(organization_id=organizations[i // 2].id, company=f"Synthetic 東京 বাংলা café {i}",
                        email=f"synthetic-lead-{i}@example.com", source="synthetic-recovery", status=status,
                        priority=("Hot", "Warm", "Cold", "Warm")[i], lead_score=(80, 50, 10, 40)[i],
                        notes="Synthetic Unicode 🙂", processing_status="completed", created_at=stamp,
                        last_contacted=stamp, next_follow_up=now + timedelta(days=2))
            db.add(lead)
            leads.append(lead)
        db.flush()
        analyses = []
        for i, lead in enumerate(leads):
            analysis = LeadAnalysis(organization_id=lead.organization_id, lead_id=lead.id,
                                    company=lead.company, email=lead.email, priority=lead.priority,
                                    lead_score=lead.lead_score, result={"synthetic": True, "summary": "恢复 বাংলা café 🙂"}, created_at=stamp)
            db.add(analysis)
            analyses.append(analysis)
        db.flush()
        latest = LeadAnalysis(organization_id=leads[0].organization_id, lead_id=leads[0].id,
                              company=leads[0].company, email=leads[0].email, priority="Hot", lead_score=90,
                              result={"synthetic": True, "summary": "Current analysis tie winner"}, created_at=stamp)
        legacy = LeadAnalysis(organization_id=organizations[0].id, lead_id=None, company="=SYNTHETIC()",
                              email="legacy-synthetic@example.com", priority="Cold", lead_score=5,
                              result={"synthetic": True}, created_at=stamp)
        db.add_all([latest, legacy])
        db.add(IngestionJob(organization_id=organizations[0].id, filename="synthetic-only.csv", source_type="csv",
                            status="completed", total_rows=2, processed_rows=2, successful_rows=2,
                            failed_rows=0, created_at=stamp, started_at=stamp, completed_at=stamp))
        session = AuthSession(user_id=users[0].id, token_hash=hash_session_token(token),
                              csrf_token_hash=hash_session_token(generate_session_token()),
                              created_at=stamp, last_seen_at=stamp, expires_at=now + timedelta(days=7))
        db.add(session)
        db.flush()
        fixture = {"organization_ids": [o.id for o in organizations], "lead_ids": [l.id for l in leads],
                   "latest_analysis_id": latest.id, "session_id": session.id, "raw_token": token,
                   "timestamp": stamp.isoformat()}
    engine.dispose()
    return fixture


def request(base, path, *, opener=None, data=None, headers=None, expected=200):
    headers = {"Origin": base, **(headers or {})}
    if data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    req = urllib.request.Request(base + path, data=data, headers=headers)
    try:
        response = (opener.open(req, timeout=10) if opener else urllib.request.urlopen(req, timeout=10))
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        if response.status != expected:
            raise BackupError("Recovery application HTTP assertion failed")
        return response.read()


def app_validation(container, database, user, password, image, http_port, fixture, run_id):
    started = time.monotonic()
    name = "leadforge-5g-app-" + run_id
    base = f"http://127.0.0.1:{http_port}"
    env = os.environ.copy()
    env.update(DATABASE_URL=f"postgresql+psycopg://{user}:{password}@127.0.0.1:5432/{database}",
               ENVIRONMENT="test", AI_PROVIDER="mock", LEADFORGE_CI="1", SESSION_COOKIE_SECURE="false", CORS_ORIGINS=base,
               LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
    args = ["run", "-d", "--name", name, "--network", f"container:{container}",
            "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges:true", "--tmpfs=/tmp:size=64m"]
    for key in ("DATABASE_URL", "ENVIRONMENT", "AI_PROVIDER", "LEADFORGE_CI", "SESSION_COOKIE_SECURE", "CORS_ORIGINS", "LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        args.extend(["--env", key])
    docker([*args, image], env=env)
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                ready = json.loads(request(base, "/ready"))
                if ready["database"] == "ok":
                    break
            except (OSError, BackupError):
                if time.monotonic() >= deadline:
                    raise BackupError("Restored backend did not become ready") from None
                time.sleep(1)
        # Deliberately prove backed-up server-side sessions survive restoration.
        request(base, "/api/auth/me", headers={"Cookie": "leadforge_session=" + fixture["raw_token"]})
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        request(base, "/api/auth/login", opener=opener,
                data={"email": "recovery-alpha@example.com", "password": LOGIN_PASSWORD})
        workspaces = json.loads(request(base, "/api/organizations", opener=opener))
        if [w["id"] for w in workspaces] != [fixture["organization_ids"][0]]:
            raise BackupError("Restored workspace authorization mismatch")
        headers = {"X-Organization-ID": str(fixture["organization_ids"][0])}
        for path in ("/api/dashboard/v2/overview", "/api/leads/", "/api/reports/v2/overview?preset=7d"):
            json.loads(request(base, path, opener=opener, headers=headers))
        lead_id = fixture["lead_ids"][0]
        detail = json.loads(request(base, f"/api/leads/{lead_id}", opener=opener, headers=headers))
        intelligence = json.loads(request(base, f"/api/leads/{lead_id}/intelligence", opener=opener, headers=headers))
        if (intelligence["analysis"]["id"] != fixture["latest_analysis_id"]
                or detail["company"] != "Synthetic 東京 বাংলা café 0"):
            raise BackupError("Restored Unicode/current-analysis mismatch")
        csv = request(base, "/api/reports/v2/export.csv?preset=7d", opener=opener, headers=headers).decode("utf-8-sig")
        if "Synthetic 東京 বাংলা café 0" not in csv or "'=SYNTHETIC()" not in csv:
            raise BackupError("Restored CSV/history/formula safety mismatch")
        request(base, f"/api/leads/{fixture['lead_ids'][2]}", opener=opener, headers=headers, expected=404)
        csrf = next(cookie.value for cookie in jar if cookie.name == "leadforge_csrf")
        created = json.loads(request(base, "/api/leads/", opener=opener,
                             headers={**headers, "X-CSRF-Token": csrf},
                             data={"company": "Synthetic restored sequence probe", "email": "restored-sequence@example.com", "source": "synthetic"}))
        if created["id"] <= max(fixture["lead_ids"]):
            raise BackupError("Restored sequence did not advance correctly")
        request(base, "/api/auth/logout", opener=opener, headers={"X-CSRF-Token": csrf}, data={})
        request(base, "/api/auth/me", opener=opener, expected=401)
        tools = PgTools(container, database, user, password)
        tools.query("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE revoked_at IS NULL;")
        request(base, "/api/auth/me", headers={"Cookie": "leadforge_session=" + fixture["raw_token"]}, expected=401)
        logs = docker(["logs", name]).decode("utf-8", errors="replace")
        if any(secret in logs for secret in (password, LOGIN_PASSWORD, fixture["raw_token"], csrf)):
            raise BackupError("Recovery runtime log privacy failed")
        return {"backend_ready": True, "login": True, "workspace": True, "dashboard": True,
                "leads": True, "intelligence": True, "reports": True, "csv": True, "tenant_isolation": True,
                "sequence_write": True, "session_survives_restore": True, "session_revocation": True,
                "logout": True, "log_privacy": True, "duration_seconds": round(time.monotonic() - started, 3)}
    finally:
        docker(["rm", "-f", name])  # Only this drill-owned application container.


def failed_cli(arguments, password, artifact_root):
    env = os.environ.copy()
    env["LEADFORGE_BACKUP_PASSWORD"] = password
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/postgres_backup.py"), *arguments],
                            env=env, capture_output=True, timeout=180)
    output = result.stdout + result.stderr
    if result.returncode == 0 or b'"event": "backup.completed"' in output or b'"event": "restore.completed"' in output:
        raise BackupError("Expected nonzero failure was hidden")
    if password.encode() in output or b"postgresql+psycopg://" in output:
        raise BackupError("Failure diagnostics leaked synthetic credentials")
    return {"exit_code": result.returncode, "privacy": True}


def corrupt_copy(artifact, output, label, mutate, resign=False):
    folder = output / label
    folder.mkdir()
    target = folder / artifact.name
    target.write_bytes(mutate(artifact.read_bytes()))
    for suffix in (".json", ".sha256"):
        shutil.copyfile(str(artifact) + suffix, str(target) + suffix)
    if resign:
        metadata = json.loads(Path(str(target) + ".json").read_text())
        metadata.update(size_bytes=target.stat().st_size, sha256=sha256(target))
        Path(str(target) + ".json").write_text(json.dumps(metadata))
        Path(str(target) + ".sha256").write_text(f"{metadata['sha256']}  {target.name}\n")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--backend-image", default="leadforge-backend:5g-verification")
    parser.add_argument("--postgres-port", type=int, default=55433)
    parser.add_argument("--http-port", type=int, default=58400)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT / "backups") or output.exists():
        raise BackupError("Drill output must be a new directory under ignored backups/")
    output.mkdir(parents=True)
    original_hash = sha256(ROOT / "leadforge.db") if (ROOT / "leadforge.db").exists() else None
    run_id = uuid4().hex[:12]
    container = "leadforge-5g-pg-" + run_id
    source = "leadforge_5g_source_" + run_id
    user = "leadforge_5g"
    password = "synthetic-5g-" + uuid4().hex
    env = os.environ.copy()
    env.update(POSTGRES_PASSWORD=password, POSTGRES_USER=user, POSTGRES_DB="postgres")
    started = False
    evidence = {"run_id": run_id, "source_database": source, "source_container": container, "client_image": CLIENT_IMAGE}
    try:
        docker(["run", "-d", "--rm", "--name", container, "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_USER", "--env", "POSTGRES_DB",
                "-p", f"127.0.0.1:{args.postgres_port}:5432", "-p", f"127.0.0.1:{args.http_port}:8000", CLIENT_IMAGE], env=env)
        started = True
        admin = PgTools(container, "postgres", user, password)
        deadline = time.monotonic() + 60
        while True:
            try:
                if admin.query("SELECT 1;") == "1":
                    break
            except BackupError:
                if time.monotonic() >= deadline:
                    raise BackupError("Disposable source TCP readiness timed out")
                time.sleep(1)
        admin.query(f"CREATE DATABASE {source} TEMPLATE template0 ENCODING 'UTF8';")
        url = f"postgresql+psycopg://{user}:{password}@127.0.0.1:{args.postgres_port}/{source}"
        appenv = os.environ.copy()
        for key in ("LEADFORGE_ENV_FILE", "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
            appenv.pop(key, None)
        appenv.update(ENVIRONMENT="test", AI_PROVIDER="mock", LEADFORGE_CI="1", DATABASE_URL=url,
                      LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
        migration = subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=appenv, capture_output=True, timeout=120)
        if migration.returncode or password.encode() in migration.stdout + migration.stderr:
            raise BackupError("Synthetic source migration or privacy check failed")
        # Only ORM seed utilities are imported here; no application session points
        # at the normal runtime or SQLite database.
        os.environ.update(ENVIRONMENT="test", AI_PROVIDER="mock", LEADFORGE_CI="1", DATABASE_URL=url)
        os.environ.pop("LEADFORGE_ENV_FILE", None)
        fixture = seed(url)
        log("recovery_fixture.created", database=source)
        tools = PgTools(container, source, user, password)
        source_manifest = fingerprint(tools)
        if source_manifest["metadata"]["alembic_revision"] != [HEAD]:
            raise BackupError("Unexpected fixture migration head")
        (output / "source-manifest.json").write_text(json.dumps(source_manifest, indent=2, ensure_ascii=True) + "\n")
        begin = time.monotonic()
        artifact = backup(tools, output, "test")
        evidence.update(artifact=str(artifact.relative_to(ROOT)), backup_seconds=round(time.monotonic() - begin, 3),
                        size_bytes=artifact.stat().st_size, sha256=sha256(artifact), inspection=inspect_dump(tools, artifact),
                        source_counts={key: value["count"] for key, value in source_manifest["tables"].items()})
        if comparable(fingerprint(tools)) != comparable(source_manifest):
            raise BackupError("Source changed during synthetic backup")
        # Revoke the old session after the backup: recovery can revive it.
        tools.query(f"UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE id={fixture['session_id']};")
        evidence["restores"] = []
        for index in (1, 2):
            target = f"leadforge_5g_restore_{run_id}_{index}"
            admin.query(f"CREATE DATABASE {target} TEMPLATE template0 ENCODING 'UTF8';")
            recovered = PgTools(container, target, user, password)
            begin = time.monotonic()
            restore(recovered, artifact, f"{container}/{target}")
            duration = round(time.monotonic() - begin, 3)
            restored_manifest = fingerprint(recovered)
            (output / f"restore-{index}-manifest.json").write_text(json.dumps(restored_manifest, indent=2, ensure_ascii=True) + "\n")
            if comparable(restored_manifest) != comparable(source_manifest):
                differences = [key for key in comparable(source_manifest) if comparable(source_manifest)[key] != comparable(restored_manifest)[key]]
                raise BackupError("Full source/restored fingerprint mismatch: " + ",".join(differences))
            app = app_validation(container, target, user, password, args.backend_image, args.http_port, fixture, run_id + str(index))
            evidence["restores"].append({"database": target, "seconds": duration, "fingerprint_matches": True, "application": app})
        common = ["--container", container, "--database", source, "--user", user, "--environment", "test"]
        evidence["failures"] = {}
        bad_output = output / "failure-artifacts"
        for label, credential, extra in (("invalid_credentials", "synthetic-5g-invalid-password", []),
                                         ("unavailable_database", password, ["--database", "leadforge_5g_nonexistent"]),
                                         ("unavailable_service", password, ["--container", "leadforge-5g-unavailable"]),
                                         ("unwritable_output", password, [])):
            destination = bad_output
            if label == "unwritable_output":
                destination = output / "not-a-directory"
                destination.write_text("Synthetic output obstruction")
            evidence["failures"][label] = failed_cli(["backup", *common, *extra, "--output-dir", str(destination)], credential, output)
        if bad_output.exists() and list(bad_output.rglob("*.dump")):
            raise BackupError("Failed backup produced a completed-looking artifact")
        failure_target = "leadforge_5g_failure_" + run_id
        admin.query(f"CREATE DATABASE {failure_target} TEMPLATE template0 ENCODING 'UTF8';")
        restore_common = ["restore", "--container", container, "--database", failure_target, "--user", user,
                          "--environment", "test", "--confirm-target", f"{container}/{failure_target}"]
        damaged = corrupt_copy(artifact, output, "checksum-mismatch", lambda data: data[:-1] + bytes([data[-1] ^ 1]))
        evidence["failures"]["checksum_mismatch"] = failed_cli([*restore_common, "--artifact", str(damaged)], password, output)
        invalid = corrupt_copy(artifact, output, "corrupt-header", lambda data: b"BROKEN" + data[6:], resign=True)
        evidence["failures"]["corrupt_backup"] = failed_cli([*restore_common, "--artifact", str(invalid)], password, output)
        truncated = corrupt_copy(artifact, output, "partial-restore", lambda data: data[:-128], resign=True)
        validate_artifact(truncated)
        inspect_dump(tools, truncated)  # TOC/header still readable, data truncated.
        evidence["failures"]["partial_restore"] = failed_cli([*restore_common, "--artifact", str(truncated)], password, output)
        PgTools(container, failure_target, user, password).require_empty()
        evidence["failures"]["partial_restore"]["transaction_rolled_back_to_empty"] = True
        evidence["failures"]["source_target"] = failed_cli(["restore", *common, "--artifact", str(artifact), "--confirm-target", f"{container}/{source}"], password, output)
        target = evidence["restores"][0]["database"]
        evidence["failures"]["nonempty_target"] = failed_cli([*restore_common, "--database", target, "--confirm-target", f"{container}/{target}", "--artifact", str(artifact)], password, output)
        evidence["failures"]["default_runtime_target"] = failed_cli([*restore_common, "--database", "leadforge_dev", "--confirm-target", f"{container}/leadforge_dev", "--artifact", str(artifact)], password, output)
        evidence["source_metadata"] = source_manifest["metadata"]
        evidence["status"] = "PASS"
        (output / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
        log("recovery_drill.completed", backup_size=evidence["size_bytes"], restores=2, failure_cases=len(evidence["failures"]), evidence=str(output.relative_to(ROOT)))
    finally:
        if started:
            # --rm plus no mounted volume: only this verified created container.
            identity = json.loads(docker(["inspect", container]))[0]
            if identity["Name"] != "/" + container or not container.startswith("leadforge-5g-pg-"):
                raise BackupError("Cleanup identity verification failed")
            if any(mount["Type"] != "volume" or mount.get("Name", "").startswith("leadforge_") for mount in identity["Mounts"]):
                raise BackupError("Unexpected user mount; refusing cleanup")
            docker(["stop", container])
        final_hash = sha256(ROOT / "leadforge.db") if (ROOT / "leadforge.db").exists() else None
        if original_hash != final_hash:
            raise BackupError("leadforge.db integrity changed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("recovery_drill.failed", reason=str(exc) if isinstance(exc, BackupError) else "Drill failed; inspect safe preceding gate output", exception_type=type(exc).__name__)
        raise SystemExit(1) from None
