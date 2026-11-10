"""P2-B contracts against migrated, disposable PostgreSQL 16.15 storage."""

from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests import test_decision_ledger as contracts


ROOT = Path(__file__).resolve().parents[1]


def migrate(url, operation, revision):
    env = os.environ.copy()
    env.update(DATABASE_URL=url, AI_PROVIDER="mock", ENVIRONMENT="test", LEADFORGE_ENV_FILE="")
    result = subprocess.run([sys.executable, "-B", "-m", "alembic", operation, revision],
        cwd=ROOT, env=env, capture_output=True, timeout=60)
    assert result.returncode == 0, "Owned P2-B migration failed; private connection output withheld"


@contextmanager
def private_database(parent, revision):
    # Keep new fixtures outside pre-existing synthetic tenant ID namespaces.
    url = make_url(parent)
    name = "leadforge_p2b_" + uuid4().hex[:12]
    connect = dict(host=url.host, port=url.port, user=url.username, password=url.password,
                   dbname="leadforge_dev", connect_timeout=3, autocommit=True)
    with psycopg.connect(**connect) as admin:
        assert admin.execute("SHOW server_version").fetchone()[0].split()[0] == "16.15"
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    private = url.set(database=name).render_as_string(hide_password=False)
    try:
        migrate(private, "upgrade", revision)
        yield private
    finally:
        with psycopg.connect(**connect) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture(scope="module")
def ledger_database(pg_database):
    with private_database(pg_database["url"], contracts.HEAD) as url:
        yield url


@pytest.fixture
def ledger_engine(ledger_database):
    engine = create_engine(ledger_database)
    try:
        yield engine
    finally:
        engine.dispose()


# Run the same semantic contracts on real PostgreSQL, rather than asserting
# dialect parity from SQLite results or maintaining weaker duplicate cases.
@pytest.mark.parametrize("state", ["none", "partial", "full"])
def test_snapshot_truthfulness_json_and_single_settlement(ledger_engine, monkeypatch, state):
    contracts.test_exact_canonical_snapshot_one_compute_and_truthfulness(ledger_engine, monkeypatch, state)


def test_historical_snapshot_after_authorized_lifecycle_change(ledger_engine):
    contracts.test_history_is_stable_after_authorized_lifecycle_change(ledger_engine)


def test_distinct_record_events_and_detached_json(ledger_engine):
    contracts.test_identical_current_decisions_append_distinct_events_and_detached_lists(ledger_engine)


def test_history_order_and_stored_policy_version(ledger_engine):
    contracts.test_policy_history_and_tied_timestamp_order_are_stored_not_live(ledger_engine)


@pytest.mark.parametrize("operation", ["orm_update", "orm_delete", "sql_update", "sql_delete"])
def test_immutable_history_including_database_triggers(ledger_engine, operation):
    contracts.test_immutable_orm_and_database_guards(ledger_engine, operation)


def test_tenant_lead_foreign_key_and_restrict_deletion(ledger_engine):
    contracts.test_tenant_lead_fk_restrict_and_scoped_reads(ledger_engine)


def test_insert_failure_rolls_back_all_mutations(ledger_engine, monkeypatch):
    contracts.test_failure_after_flush_rolls_back_without_lead_or_audit_mutation(ledger_engine, monkeypatch)


def test_caught_nested_failure_poisoning(ledger_engine, monkeypatch):
    contracts.test_nested_failure_is_rollback_only_even_if_caught(ledger_engine, monkeypatch)


@pytest.mark.parametrize("state", ["missing_principal", "machine", "revoked_user", "tenant_mismatch"])
def test_fresh_human_tenant_authority(ledger_engine, state):
    contracts.test_record_service_requires_user_identity_and_fresh_membership(ledger_engine, state)


@pytest.mark.parametrize("score", [0, 100])
def test_extreme_score_json_and_timestamp_fidelity(ledger_engine, score):
    contracts.test_extreme_score_and_exact_json_timestamp_roundtrip(ledger_engine, score)


@pytest.mark.parametrize("invalid", ["raw_dict", "nan", "too_many_reasons", "unsafe_evidence"])
def test_typed_snapshot_validation_before_insert(ledger_engine, invalid):
    contracts.test_repository_revalidates_typed_bounded_snapshot(ledger_engine, invalid)


def test_no_ungoverned_repository_settlement(ledger_engine):
    contracts.test_repository_cannot_settle_an_ungoverned_insert(ledger_engine)


@pytest.mark.parametrize("field,value", [("opportunity_score", -1), ("fit_score", 101),
    ("confidence", float("nan")), ("confidence", float("inf")), ("confidence", -.1),
    ("confidence", 1.1), ("decision_version", ""), ("recommended_action", "SEND_EMAIL"),
    ("reasons", ["x"] * 40000)])
def test_invalid_storage_values_are_rejected(ledger_engine, field, value):
    contracts.test_storage_constraints_reject_invalid_raw_inserts(ledger_engine, field, value)


def test_missing_int64_id_non_disclosure(ledger_engine):
    case = contracts.prepare(ledger_engine)
    before = contracts.snapshot(ledger_engine)
    with Session(ledger_engine) as db:
        service = contracts.service(db)
        org = case["ids"]["org"]
        assert service.record(case["principal"], 2**63 - 1, org) is None
        assert service.history(2**63 - 1, org) is None
        assert service.get(2**63 - 1, org, uuid4()) is None
    assert contracts.snapshot(ledger_engine) == before


def test_migrated_schema_types_index_and_ownership(ledger_engine):
    inspector = inspect(ledger_engine)
    columns = {c["name"]: c for c in inspector.get_columns("decision_ledger")}
    assert len(columns) == 16 and all(not c["nullable"] for c in columns.values())
    assert columns["decision_generated_at"]["type"].timezone
    assert columns["recorded_at"]["type"].timezone
    assert all(str(columns[c]["type"]) == "JSON" for c in ("reasons", "evidence", "risk_flags", "missing_signals"))
    indexes = inspector.get_indexes("decision_ledger")
    assert any(i["column_names"] == ["organization_id", "lead_id", "recorded_at", "id"] for i in indexes)
    keys = inspector.get_foreign_keys("decision_ledger")
    assert any(k["constrained_columns"] == ["organization_id", "lead_id"] and
               k["referred_columns"] == ["organization_id", "id"] and k["options"]["ondelete"] == "RESTRICT" for k in keys)
    with ledger_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == [contracts.HEAD]


def test_populated_postgres_migration_roundtrip_no_backfill(pg_database):
    with private_database(pg_database["url"], contracts.PUBLISHED) as url:
        engine = create_engine(url)
        case = contracts.seed_case(engine)
        before = contracts.migration_rows(engine)
        engine.dispose()
        migrate(url, "upgrade", contracts.HEAD)
        engine = create_engine(url)
        after = contracts.migration_rows(engine)
        assert after["decision_ledger"] == []
        assert {k: v for k, v in after.items() if k != "decision_ledger"} == before
        with Session(engine) as db:
            dto = contracts.record(db, case)
            assert contracts.service(db).get(dto.lead_id, dto.organization_id, dto.id) == dto
        engine.dispose()
        migrate(url, "downgrade", contracts.PUBLISHED)
        engine = create_engine(url)
        assert "decision_ledger" not in inspect(engine).get_table_names()
        assert contracts.migration_rows(engine) == before
        engine.dispose()
        migrate(url, "upgrade", contracts.HEAD)
        engine = create_engine(url)
        assert contracts.snapshot(engine)["decision_ledger"] == []
        engine.dispose()
