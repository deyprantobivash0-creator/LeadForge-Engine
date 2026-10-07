"""Backup helper safety; real PostgreSQL/pg_restore proof is a separate drill."""
import json
from pathlib import Path

import pytest

from scripts import postgres_backup as backup


def artifact(tmp_path):
    path = tmp_path / "synthetic.dump"
    path.write_bytes(b"PGDMPsynthetic-header-probe")
    metadata = {"schema_version": 1, "format": "custom", "artifact": path.name,
                "size_bytes": path.stat().st_size, "sha256": backup.sha256(path),
                "source": {"container": "synthetic-source", "database": "synthetic_source"},
                "postgres_version": "16.15", "alembic_revision": ["e5d4c3b2a1f0"]}
    Path(str(path) + ".json").write_text(json.dumps(metadata))
    Path(str(path) + ".sha256").write_text(f"{metadata['sha256']}  {path.name}\n")
    return path


def test_checksum_detects_tampering_before_restore(tmp_path):
    path = artifact(tmp_path)
    assert backup.validate_artifact(path)["format"] == "custom"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(backup.BackupError, match="mismatch"):
        backup.validate_artifact(path)


@pytest.mark.parametrize("field,value", [("format", "plain"), ("schema_version", 99),
                                       ("sha256", "invalid"), ("alembic_revision", []),
                                       ("postgres_version", "15.0")])
def test_untrusted_manifest_fails_closed(tmp_path, field, value):
    path = artifact(tmp_path)
    metadata = json.loads(Path(str(path) + ".json").read_text())
    metadata[field] = value
    Path(str(path) + ".json").write_text(json.dumps(metadata))
    with pytest.raises(backup.BackupError):
        backup.validate_artifact(path)


@pytest.mark.parametrize("database", ["synthetic_source", "leadforge_dev", "postgres", "template0", "template1"])
def test_restore_refuses_source_and_default_targets_before_connecting(tmp_path, database):
    path = artifact(tmp_path)
    tools = backup.PgTools("synthetic-target", database, "synthetic_user", "synthetic-password")
    with pytest.raises(backup.BackupError, match="Refusing source/default/runtime"):
        backup.restore(tools, path, f"synthetic-target/{database}")


def test_restore_requires_exact_confirmation(tmp_path):
    tools = backup.PgTools("synthetic-target", "synthetic_restore", "synthetic_user", "synthetic-password")
    with pytest.raises(backup.BackupError, match="Confirm the exact"):
        backup.restore(tools, artifact(tmp_path), "other-target/synthetic_restore")


def test_no_output_inside_public_or_source_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "ROOT", tmp_path)
    with pytest.raises(backup.BackupError, match="ignored backups"):
        backup.safe_output_directory(tmp_path / "frontend/public")
    assert not (tmp_path / "frontend").exists()
    assert backup.safe_output_directory(tmp_path / "backups/synthetic").is_dir()


def test_password_not_in_process_arguments(monkeypatch):
    value = "synthetic-argument-sentinel"
    tools = backup.PgTools("synthetic-target", "synthetic_restore", "synthetic_user", value)
    monkeypatch.setattr(backup, "docker", lambda *args, **kwargs: b'{"synthetic-network":{"IPAddress":"172.18.0.2"}}')
    command = tools.command("pg_restore", "--single-transaction", "--no-owner")
    assert value not in " ".join(command)
    assert "PGPASSWORD" in command


@pytest.mark.parametrize("value", ["db;DROP", "../source", "-option", "postgresql://secret@example/db"])
def test_database_arguments_cannot_be_sql_or_options(value):
    with pytest.raises(backup.BackupError):
        backup.identifier(value)


def test_schema_comparison_does_not_ignore_changed_role_constraint():
    from scripts.verify_backup_recovery import canonical_constraints
    before = "CHECK (((role)::text = ANY ((ARRAY['owner'::character varying, 'admin'::character varying, 'member'::character varying])::text[])))"
    after = "CHECK (((role)::text = ANY (ARRAY[('owner'::character varying)::text, ('admin'::character varying)::text, ('member'::character varying)::text])))"
    wrap = lambda value: [["organization_memberships", "role_check", value]]
    assert canonical_constraints(wrap(before)) == canonical_constraints(wrap(after))
    assert canonical_constraints(wrap(before)) != canonical_constraints(wrap(after.replace("member", "attacker")))
