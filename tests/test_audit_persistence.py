"""E05-I1 storage tests only; no business audit writer or I2 validator claims."""

from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import CheckConstraint, create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from backend.database.base import Base
from backend.models import AuditEvent, Lead, Organization


ROOT = Path(__file__).resolve().parents[1]
HEAD = "5d59e6268f43"
PREVIOUS = "e5d4c3b2a1f0"
COLUMNS = """event_id organization_id occurred_at recorded_at event_type action outcome
reason_code principal_type actor_id delegated_by_type delegated_by_actor_id correlation_id
workflow_run_id agent_id integration_id target_type target_id authorization_evidence
authority_role details schema_version""".split()
INDEXES = {
    "ix_audit_events_org_time": ["organization_id", "occurred_at", "event_id"],
    "ix_audit_events_org_actor_time": ["organization_id", "principal_type", "actor_id", "occurred_at", "event_id"],
    "ix_audit_events_org_correlation": ["organization_id", "correlation_id", "occurred_at", "event_id"],
    "ix_audit_events_org_action_time": ["organization_id", "action", "occurred_at", "event_id"],
    "ix_audit_events_org_target_time": ["organization_id", "target_type", "target_id", "occurred_at", "event_id"],
}
CHECKS = {"ck_audit_events_" + name for name in (
    "domains", "event_outcome", "tenant_positive", "bounds", "delegator_pair", "target",
)}


def audit_values(**changes):
    # Storage fixtures deliberately contain no real user/lead/session data.
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    values = dict(organization_id=123, occurred_at=now, recorded_at=now + timedelta(seconds=1),
                  event_type="business.command.completed", action="lead.create", outcome="SUCCEEDED",
                  reason_code="COMMAND_COMPLETED", principal_type="USER", actor_id="1",
                  correlation_id="schema-test", target_type="lead", target_id="42",
                  authorization_evidence=[], details={}, schema_version=1)
    values.update(changes)
    return values


def assert_schema(engine):
    inspector = inspect(engine)
    columns = inspector.get_columns("audit_events")
    assert [c["name"] for c in columns] == COLUMNS
    assert len(columns) == 22
    assert inspector.get_foreign_keys("audit_events") == []
    assert inspector.get_pk_constraint("audit_events")["constrained_columns"] == ["event_id"]
    assert inspector.get_unique_constraints("audit_events") == []
    assert {i["name"]: i["column_names"] for i in inspector.get_indexes("audit_events")} == INDEXES
    assert {c["name"] for c in inspector.get_check_constraints("audit_events")} == CHECKS
    for column in columns:
        model = AuditEvent.__table__.c[column["name"]]
        assert column["nullable"] == model.nullable
        assert column["default"] is None
        if getattr(model.type, "length", None):
            assert column["type"].length == model.type.length
    # SQLite preserves SQL text. PostgreSQL rewrites IN/casts in reflection;
    # its named constraints are checked behaviorally by the raw-insert matrix.
    if engine.dialect.name == "sqlite":
        normalize = lambda sql: " ".join(sql.split())
        actual = {c["name"]: normalize(c["sqltext"]) for c in inspector.get_check_constraints("audit_events")}
        expected = {str(c.name): normalize(str(c.sqltext)) for c in AuditEvent.__table__.constraints
                    if isinstance(c, CheckConstraint)}
        assert actual == expected


INVALID_CASES = [
    {"organization_id": None}, {"organization_id": 0}, {"organization_id": -1},
    {"event_type": "future.event"}, {"action": "audit.read"}, {"outcome": "FAILED"},
    {"reason_code": "untrusted-reason"}, {"principal_type": "SUPERUSER"},
    {"authority_role": "superuser"}, {"delegated_by_type": "UNKNOWN", "delegated_by_actor_id": "x"},
    {"event_type": "permission.denied"}, {"outcome": "DENIED", "target_id": None},
    {"event_type": "permission.denied", "outcome": "DENIED", "reason_code": "COMMAND_COMPLETED", "target_id": None},
    {"delegated_by_type": "SYSTEM"}, {"delegated_by_actor_id": "parent"},
    {"delegated_by_type": "SYSTEM", "delegated_by_actor_id": "parent"},
    {"workflow_run_id": "run"}, {"agent_id": "agent"}, {"integration_id": "connection"},
    {"principal_type": "AGENT"}, {"principal_type": "WORKFLOW"}, {"principal_type": "INTEGRATION"},
    {"principal_type": "AGENT", "agent_id": "other"},
    {"principal_type": "WORKFLOW", "workflow_run_id": "other"},
    {"principal_type": "INTEGRATION", "integration_id": "other"},
    {"target_id": None}, {"target_type": "account"}, {"action": "lead.import"},
    {"schema_version": None}, {"schema_version": 0}, {"schema_version": 2},
    {"authorization_evidence": None}, {"details": None},
    {"occurred_at": None}, {"recorded_at": None},
    {"event_id": "short"}, {"event_id": "x" * 37}, {"actor_id": ""}, {"actor_id": "x" * 129},
    {"correlation_id": ""}, {"correlation_id": "x" * 65}, {"target_id": ""}, {"target_id": "x" * 129},
    {"principal_type": "SYSTEM", "delegated_by_type": "USER", "delegated_by_actor_id": ""},
    {"principal_type": "SYSTEM", "delegated_by_type": "USER", "delegated_by_actor_id": "x" * 129},
    {"principal_type": "SYSTEM", "workflow_run_id": ""},
    {"principal_type": "SYSTEM", "workflow_run_id": "x" * 129},
    {"principal_type": "SYSTEM", "agent_id": ""},
    {"principal_type": "SYSTEM", "agent_id": "x" * 129},
    {"principal_type": "SYSTEM", "integration_id": ""},
    {"principal_type": "SYSTEM", "integration_id": "x" * 129},
]


@pytest.fixture(scope="module", params=["metadata", "migration"])
def audit_engine(request, tmp_path_factory):
    path = tmp_path_factory.mktemp("audit-persistence") / "audit.db"
    url = f"sqlite:///{path.as_posix()}"
    if request.param == "migration":
        from backend.core.config import settings
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(settings, "DATABASE_URL", url)
            command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enforce_fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    if request.param == "metadata":
        Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_exact_frozen_schema_and_registration(audit_engine):
    assert_schema(audit_engine)
    assert Base.metadata.tables["audit_events"] is AuditEvent.__table__
    assert not set(COLUMNS) & {"permission", "permission_decision", "permission_reason_code",
                               "additional_permission", "additional_permission_decision",
                               "additional_permission_reason_code", "authority_version"}
    assert not AuditEvent.__table__.foreign_keys
    for column in AuditEvent.__table__.columns:
        assert column.server_default is None and column.onupdate is None
        if column.name != "event_id":
            assert column.default is None


@pytest.mark.parametrize("changes", INVALID_CASES)
def test_raw_database_constraints_not_application_validator(audit_engine, changes):
    # Core INSERT bypasses ORM mutation guards; rejection must come from the DB.
    with audit_engine.connect() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(AuditEvent.__table__.insert(), audit_values(**changes))
        connection.rollback()


@pytest.mark.parametrize("event_type,outcome,reason,target", [
    ("business.command.completed", "SUCCEEDED", "COMMAND_COMPLETED", "42"),
    ("permission.denied", "DENIED", "ACTION_PERMISSION_DENIED", None),
    ("security.command.rejected", "DENIED", "EXECUTION_TENANT_MISMATCH", None),
])
def test_initial_events_and_uuid_primary_key(audit_engine, event_type, outcome, reason, target):
    with Session(audit_engine) as db:
        item = AuditEvent(**audit_values(event_type=event_type, outcome=outcome,
                                        reason_code=reason, target_id=target))
        db.add(item)
        db.flush()
        event_id = item.event_id
        assert UUID(event_id).version == 4 and len(event_id) == 36
        db.expunge_all()
        assert db.get(AuditEvent, event_id).outcome == outcome
        with pytest.raises(IntegrityError):
            db.execute(AuditEvent.__table__.insert(), audit_values(event_id=event_id))
        db.rollback()


@pytest.mark.parametrize("kind,provenance", [("USER", {}), ("SYSTEM", {}),
    ("AGENT", {"agent_id": "actor"}), ("WORKFLOW", {"workflow_run_id": "actor"}),
    ("INTEGRATION", {"integration_id": "actor"})])
def test_principal_and_delegation_snapshots(audit_engine, kind, provenance):
    values = audit_values(principal_type=kind, actor_id="1" if kind == "USER" else "actor", **provenance)
    if kind != "USER":
        values.update(delegated_by_type="USER", delegated_by_actor_id="1")
    with Session(audit_engine) as db:
        item = AuditEvent(**values)
        db.add(item)
        db.flush()
        event_id = item.event_id
        db.expunge_all()
        row = db.get(AuditEvent, event_id)
        assert row.principal_type == kind and row.correlation_id == "schema-test"
        if kind != "USER":
            assert row.delegated_by_actor_id == "1"


@pytest.mark.parametrize("evidence", [[], [{"permission": "lead.create", "decision": "PERMIT", "reason_code": "PERMITTED_BY_ROLE"}],
    [{"permission": "lead.import", "decision": "PERMIT", "reason_code": "PERMITTED_BY_ROLE"},
     {"permission": "lead.create", "decision": "PERMIT", "reason_code": "PERMITTED_BY_ROLE"}]])
def test_json_storage_only_not_i2_authorization_validation(audit_engine, evidence):
    with Session(audit_engine) as db:
        item = AuditEvent(**audit_values(action="lead.import", target_type="lead_import",
                          target_id=str(uuid4()), authorization_evidence=evidence,
                          details={"total": 1, "imported": 1, "duplicates": 0, "invalid": 0}))
        db.add(item)
        db.flush()
        event_id = item.event_id
        db.expunge_all()
        row = db.get(AuditEvent, event_id)
        assert row.authorization_evidence == evidence and row.details["imported"] == 1
        # Empty success evidence is storage-valid, NOT a valid I2 command event.


def test_json_database_does_not_claim_cardinality_or_allowlist_validation(audit_engine):
    with Session(audit_engine) as db:
        item = AuditEvent(**audit_values(authorization_evidence=[{"unknown": "synthetic"}] * 9,
                                        details={"unknown": "synthetic" * 300}))
        db.add(item)
        db.flush()
        assert item.event_id  # I2 must reject this; I1 is representation only.


def test_aware_utc_round_trip_and_naive_rejection(audit_engine):
    offset = timezone(timedelta(hours=6))
    observed = datetime(2026, 10, 13, 18, 0, 1, 123456, tzinfo=offset)
    recorded = observed - timedelta(seconds=1)  # No invented wall-clock ordering constraint.
    with Session(audit_engine) as db:
        item = AuditEvent(**audit_values(occurred_at=observed, recorded_at=recorded))
        db.add(item)
        db.flush()
        event_id = item.event_id
        db.expunge_all()
        row = db.get(AuditEvent, event_id)
        assert row.occurred_at == observed.astimezone(timezone.utc)
        assert row.recorded_at == recorded.astimezone(timezone.utc)
        assert row.occurred_at.tzinfo == timezone.utc
    with Session(audit_engine) as db:
        db.add(AuditEvent(**audit_values(occurred_at=observed.replace(tzinfo=None))))
        with pytest.raises(StatementError):
            db.flush()


@pytest.mark.parametrize("mutation", ["update", "delete"])
def test_mapper_only_append_guard(audit_engine, mutation):
    with Session(audit_engine) as db:
        item = AuditEvent(**audit_values())
        db.add(item)
        db.flush()
        if mutation == "update":
            item.target_id = "43"
        else:
            db.delete(item)
        with pytest.raises(ValueError, match="append-only"):
            db.flush()
        db.rollback()
        org = Organization(name="Synthetic", slug=str(uuid4()))
        db.add(org)
        db.flush()
        org.name = "Changed"
        db.flush()  # Guard must not affect unrelated mappers.
        db.delete(org)
        db.flush()


def test_organization_deletion_does_not_rewrite_history(audit_engine):
    with Session(audit_engine) as db:
        org = Organization(name="Disposable", slug=str(uuid4()))
        db.add(org)
        db.flush()
        historical_id = org.id
        item = AuditEvent(**audit_values(organization_id=historical_id))
        db.add(item)
        db.flush()
        event_id = item.event_id
        db.delete(org)
        db.flush()
        db.expunge_all()
        assert db.get(AuditEvent, event_id).organization_id == historical_id


def test_additive_upgrade_populated_downgrade_and_reupgrade(tmp_path, monkeypatch):
    from backend.core.config import settings
    path = tmp_path / "migration.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{path.as_posix()}")
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, PREVIOUS)
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as db:
        org = Organization(name="Preserved", slug="preserved")
        db.add(org)
        db.flush()
        db.add(Lead(organization_id=org.id, company="Synthetic", email="audit-fixture@example.com", source="fixture"))
        db.commit()
    inspector = inspect(engine)
    before = {name: inspector.get_columns(name) for name in inspector.get_table_names()}
    engine.dispose()
    command.upgrade(config, HEAD)
    engine = create_engine(settings.DATABASE_URL)
    assert_schema(engine)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == set(before) | {"audit_events"}
    for name, columns in before.items():
        assert [(c["name"], str(c["type"]), c["nullable"], c["default"]) for c in columns] == [
            (c["name"], str(c["type"]), c["nullable"], c["default"]) for c in inspector.get_columns(name)]
    with Session(engine) as db:
        assert db.scalar(select(Lead.company)) == "Synthetic"
        assert db.scalar(select(AuditEvent.event_id)) is None  # No backfill.
        db.add(AuditEvent(**audit_values()))
        db.commit()
    engine.dispose()
    command.downgrade(config, PREVIOUS)  # Destroys synthetic evidence only.
    engine = create_engine(settings.DATABASE_URL)
    assert "audit_events" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM leads")) == 1
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREVIOUS
    engine.dispose()
    command.upgrade(config, HEAD)
    engine = create_engine(settings.DATABASE_URL)
    assert_schema(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM audit_events")) == 0
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    engine.dispose()


def test_generated_graph_and_postgres_upgrade_sql_without_database():
    scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert scripts.get_heads() == [HEAD]
    revision = scripts.get_revision(HEAD)
    assert revision.down_revision == PREVIOUS
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        revision.module.upgrade()
    ddl = output.getvalue()
    assert "CREATE TABLE audit_events" in ddl
    assert ddl.count("TIMESTAMP WITH TIME ZONE") == 2
    assert ddl.count("CREATE INDEX") == 5
    assert "FOREIGN KEY" not in ddl and "ALTER TABLE" not in ddl and "CREATE TYPE" not in ddl
