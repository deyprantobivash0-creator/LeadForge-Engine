"""E05-I1 production-dialect persistence, on the guarded disposable PG fixture."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from backend.models import AuditEvent
from tests.test_audit_persistence import HEAD, PREVIOUS, INVALID_CASES, assert_schema, audit_values


@pytest.fixture
def audit_pg_engine(pg_database):
    # pg_database refuses anything except the disposable loopback service.
    engine = create_engine(pg_database["url"])
    try:
        yield engine
    finally:
        engine.dispose()


def test_postgres_migrated_schema(audit_pg_engine):
    assert_schema(audit_pg_engine)
    columns = {c["name"]: c for c in inspect(audit_pg_engine).get_columns("audit_events")}
    assert columns["occurred_at"]["type"].timezone
    assert columns["recorded_at"]["type"].timezone


@pytest.mark.parametrize("changes", INVALID_CASES)
def test_postgres_raw_constraints(audit_pg_engine, changes):
    with audit_pg_engine.connect() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(AuditEvent.__table__.insert(), audit_values(**changes))
        connection.rollback()


@pytest.mark.parametrize("evidence", [[], [{"permission": "lead.create", "decision": "PERMIT", "reason_code": "PERMITTED_BY_ROLE"}],
    [{"permission": "lead.import", "decision": "PERMIT", "reason_code": "PERMITTED_BY_ROLE"},
     {"permission": "lead.create", "decision": "PERMIT", "reason_code": "PERMITTED_BY_ROLE"}]])
def test_postgres_uuid_utc_and_json_storage(audit_pg_engine, evidence):
    observed = datetime(2026, 10, 13, 18, 0, tzinfo=timezone(timedelta(hours=6)))
    with Session(audit_pg_engine) as db:
        item = AuditEvent(**audit_values(occurred_at=observed, authorization_evidence=evidence))
        db.add(item)
        db.flush()
        event_id = item.event_id
        assert UUID(event_id).version == 4 and len(event_id) == 36
        db.expunge_all()
        row = db.get(AuditEvent, event_id)
        assert row.authorization_evidence == evidence and row.details == {}
        assert row.occurred_at == observed.astimezone(timezone.utc)
        assert row.occurred_at.tzinfo == timezone.utc
        with pytest.raises(IntegrityError):
            db.execute(AuditEvent.__table__.insert(), audit_values(event_id=event_id))
        db.rollback()


@pytest.mark.parametrize("field", ["occurred_at", "recorded_at"])
def test_postgres_rejects_naive_timestamp(audit_pg_engine, field):
    with Session(audit_pg_engine) as db:
        db.add(AuditEvent(**audit_values(**{field: datetime(2026, 10, 13)})))
        with pytest.raises(StatementError):
            db.flush()


def test_postgres_populated_downgrade_destroys_only_disposable_evidence_and_reupgrade(pg_database):
    from backend.core.config import settings, secret_value
    assert secret_value(settings.DATABASE_URL) == pg_database["url"]
    engine = create_engine(pg_database["url"])
    with Session(engine) as db:
        db.add(AuditEvent(**audit_values()))
        db.commit()
    before_tables = set(inspect(engine).get_table_names())
    engine.dispose()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, PREVIOUS)
    engine = create_engine(pg_database["url"])
    assert set(inspect(engine).get_table_names()) == before_tables - {"audit_events"}
    engine.dispose()
    command.upgrade(config, HEAD)
    engine = create_engine(pg_database["url"])
    assert_schema(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM audit_events")) == 0
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    engine.dispose()
