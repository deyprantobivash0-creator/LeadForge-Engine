"""Standalone TX acceptance: no dependency on the unpublished P1 API."""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, event, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.base import Base
from backend.database.transactions import service_transaction as tx, TransactionAborted
from backend.database.transaction_policy import (
    TransactionPolicyViolation, current_root, require_governed_physical_root,
    service_savepoint, Operation, _permit, _flushing,
)
from backend.models import Organization, Lead


@pytest.fixture
def policy_engine(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "policy.db").as_posix(), connect_args={"timeout": 0})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Organization(id=1, name="Synthetic", slug="synthetic"))
        db.flush()
        db.add(Lead(id=1, organization_id=1, company="Synthetic", email="tx@example.invalid", source="test"))
        db.commit()
    try:
        yield engine
    finally:
        engine.dispose()


def value(engine):
    with Session(engine) as db:
        return db.scalar(select(Lead.status).where(Lead.id == 1))


def change(db):
    db.execute(update(Lead).where(Lead.id == 1, Lead.organization_id == 1).values(status="Lost"))


@pytest.mark.parametrize("api", ["session_commit", "session_rollback", "connection_commit", "connection_rollback", "session_close"])
def test_settlement_denial_is_permanent(policy_engine, api):
    with Session(policy_engine) as db:
        with pytest.raises((TransactionPolicyViolation, TransactionAborted)):
            with tx(db):
                change(db)
                target = db if api.startswith("session") else db.connection()
                method = api.split("_")[1]
                with pytest.raises(TransactionPolicyViolation):
                    getattr(target, method)()
                for operation in [lambda: db.scalar(select(Lead.id)), db.flush,
                                  lambda: require_governed_physical_root(db)]:
                    with pytest.raises(TransactionPolicyViolation):
                        operation()
                with pytest.raises(TransactionPolicyViolation):
                    with tx(db):
                        pass
                with pytest.raises(TransactionPolicyViolation):
                    with service_savepoint(db):
                        pass
        assert current_root(db) is None and _permit.get() is None
    assert value(policy_engine) == "New"


RAW = ["COMMIT", " commit", "/*x*/ COMMIT", "ROLLBACK", "ROLLBACK TO x", "BEGIN",
       "BEGIN IMMEDIATE", "SAVEPOINT x", 'SAVEPOINT "x"', "SAVEPOINT [x]", "SAVEPOINT `x`",
       "RELEASE x", "END", "SELECT 1; COMMIT", "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"]


@pytest.mark.parametrize("statement", RAW)
@pytest.mark.parametrize("via_session", [False, True])
def test_opaque_statements_are_denied(policy_engine, statement, via_session):
    with Session(policy_engine) as db:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)
                if via_session:
                    db.execute(text(statement))
                else:
                    db.connection().exec_driver_sql(statement)
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("unmanaged", ["BEGIN", "SAVEPOINT x", 'SAVEPOINT "x"'])
def test_unknown_physical_root_rejected(policy_engine, unmanaged):
    with Session(policy_engine) as db:
        db.connection().exec_driver_sql(unmanaged)
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)
    assert value(policy_engine) == "New"


def test_empty_read_and_autobegin_are_lazy(policy_engine):
    with Session(policy_engine) as db:
        db.scalar(select(Lead.id))
        for _ in range(3):
            with tx(db):
                root = current_root(db)
                assert root.authority.driver is None or not root.authority.driver.in_transaction
                db.scalar(select(Lead.id))
                assert not root.authority.driver.in_transaction
            assert current_root(db) is None and _permit.get() is None


def test_first_write_and_flushed_nested_composition_rollback(policy_engine):
    with Session(policy_engine) as db:
        with pytest.raises(RuntimeError):
            with tx(db):
                root = current_root(db)
                change(db)
                assert root.physical and root.authority.driver.in_transaction
                with tx(db):
                    db.get(Lead, 1).notes = "Synthetic"
                    db.flush()
                raise RuntimeError("Synthetic later failure")
    assert value(policy_engine) == "New"


def test_approved_savepoint_release_cannot_commit_root(policy_engine):
    with Session(policy_engine) as db:
        with pytest.raises(RuntimeError):
            with tx(db):
                with service_savepoint(db):
                    change(db)
                assert current_root(db).authority.driver.in_transaction
                assert value(policy_engine) == "New"
                raise RuntimeError("Synthetic outer failure")
    assert value(policy_engine) == "New"


def test_duplicate_savepoint_recovery_and_later_success(policy_engine):
    with Session(policy_engine) as db, tx(db):
        with pytest.raises(IntegrityError):
            with service_savepoint(db):
                db.add(Lead(organization_id=1, company="Synthetic", email="tx@example.invalid", source="test"))
                db.flush()
        with service_savepoint(db):
            change(db)
    assert value(policy_engine) == "Lost"


def test_savepoint_failure_cleanup_and_no_permit_leak(policy_engine):
    with Session(policy_engine) as db:
        with tx(db):
            with pytest.raises(ValueError):
                with service_savepoint(db):
                    change(db)
                    raise ValueError("Synthetic row failure")
            assert _permit.get() is None
            assert db.scalar(select(Lead.status).where(Lead.id == 1)) == "New"
    assert value(policy_engine) == "New"


def test_direct_managed_savepoint_denied(policy_engine):
    with Session(policy_engine) as db:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                db.begin_nested()
                db.connection()


def test_caller_info_cannot_supply_authority(policy_engine):
    with Session(policy_engine) as db:
        db.info["leadforge.service_transaction"] = {"failed": False}
        assert current_root(db) is None
        with pytest.raises(TransactionPolicyViolation):
            require_governed_physical_root(db)


def test_connection_invalidation_cannot_continue(policy_engine):
    with Session(policy_engine) as db:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)
                db.connection().invalidate()
                db.scalar(select(Lead.id))
    assert value(policy_engine) == "New"


def test_permit_is_bound_and_consumed(policy_engine):
    with Session(policy_engine) as a, Session(policy_engine) as b:
        with pytest.raises((TransactionPolicyViolation, TransactionAborted)):
            with tx(a):
                root = current_root(a)
                with tx(b):
                    with root.permit(Operation.ROOT_COMMIT, "session_commit_api"):
                        with pytest.raises(TransactionPolicyViolation):
                            b.commit()


def test_raw_savepoint_negative_control(policy_engine):
    with Session(policy_engine) as db:
        db.connection().exec_driver_sql("SAVEPOINT unchecked")
        change(db)
        db.connection().exec_driver_sql("RELEASE SAVEPOINT unchecked")
        db.rollback()
    assert value(policy_engine) == "Lost"  # Absent governance, rollback cannot repair it.


def test_raw_dbapi_is_explicit_unsupported_escape(policy_engine):
    with Session(policy_engine) as db:
        with pytest.raises(RuntimeError):
            with tx(db):
                change(db)
                current_root(db).authority.driver.commit()
                raise RuntimeError("Synthetic root failure")
    assert value(policy_engine) == "Lost"


@pytest.mark.parametrize("method", ["commit", "rollback"])
def test_native_connection_event_failure_discards_unit(policy_engine, method):
    with Session(policy_engine) as db:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)
                connection = db.connection()
                # Exercise the native event fence beneath the public API gate.
                getattr(type(connection), method)(connection)
        assert current_root(db) is None
    assert value(policy_engine) == "New"


def test_mode_change_is_fatal(policy_engine):
    with Session(policy_engine) as db:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                db.connection().execution_options(isolation_level="AUTOCOMMIT")


def test_consumed_permit_cannot_be_reused(policy_engine):
    with Session(policy_engine) as db:
        with pytest.raises((TransactionPolicyViolation, TransactionAborted)):
            with tx(db):
                root = current_root(db)
                with root.permit(Operation.ROOT_COMMIT, "probe"):
                    root.consume("probe", {Operation.ROOT_COMMIT})
                    with pytest.raises(TransactionPolicyViolation):
                        root.consume("probe", {Operation.ROOT_COMMIT})


def test_guards_and_listeners_removed_after_repeated_roots(policy_engine):
    with Session(policy_engine) as db:
        original = set(db.__dict__)
        for _ in range(8):
            with tx(db):
                root = current_root(db)
                db.scalar(select(Lead.id))
            assert root.listeners == root.methods == []
            assert not {"commit", "rollback", "close", "flush", "begin_nested"}.intersection(db.__dict__)
            assert _permit.get() is None and current_root(db) is None


def test_expired_root_cannot_mint_permit(policy_engine):
    with Session(policy_engine) as db:
        with tx(db):
            root = current_root(db)
        with pytest.raises(TransactionPolicyViolation):
            with root.permit(Operation.ROOT_COMMIT, "session_commit_api"):
                pass


def test_savepoint_cleanup_failure_discards_without_masking_body(policy_engine, monkeypatch):
    with Session(policy_engine) as db:
        original = ValueError("Synthetic original body failure")
        with pytest.raises(ValueError) as caught:
            with tx(db):
                with service_savepoint(db):
                    change(db)
                    nested = db.get_nested_transaction()
                    monkeypatch.setattr(nested, "rollback", lambda: (_ for _ in ()).throw(RuntimeError("Synthetic cleanup failure")))
                    raise original
        assert caught.value is original and current_root(db) is None and _permit.get() is None
    assert value(policy_engine) == "New"


def test_replaced_bind_cannot_continue(policy_engine, tmp_path):
    other = create_engine("sqlite:///" + (tmp_path / "unowned.db").as_posix())
    try:
        with Session(policy_engine) as db:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    change(db)
                    db.bind = other
                    db.scalar(select(Lead.id))
        assert value(policy_engine) == "New"
    finally:
        other.dispose()


def test_external_connection_transaction_cannot_be_adopted(policy_engine):
    with policy_engine.connect() as connection, Session(bind=connection) as db:
        connection.begin()
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)


def test_empty_scope_preserves_no_database_access(policy_engine):
    checkouts = []
    def checkout(*args): checkouts.append(True)
    event.listen(policy_engine, "checkout", checkout)
    try:
        with Session(policy_engine) as db:
            with tx(db):
                assert not db.in_transaction()
                assert current_root(db).authority.connection is None
            assert not db.in_transaction()
        assert checkouts == []
    finally:
        event.remove(policy_engine, "checkout", checkout)


def test_sqlite_pep249_autocommit_is_not_governed(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "autocommit.db").as_posix(),
                           connect_args={"autocommit": True})
    try:
        with Session(engine) as db:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    require_governed_physical_root(db)
    finally:
        engine.dispose()


def test_savepoint_permit_does_not_authorize_reentrant_raw_commit(policy_engine):
    connection = None
    def unexpected(conn, name, context):
        conn.exec_driver_sql("COMMIT")
    try:
        with Session(policy_engine) as db:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    with service_savepoint(db):
                        change(db)
                        connection = db.connection()
                        event.listen(connection, "release_savepoint", unexpected)
        assert value(policy_engine) == "New"
    finally:
        if connection is not None:
            event.remove(connection, "release_savepoint", unexpected)


@contextmanager
def injected_creation_failure(db, engine, phase, original, monkeypatch):
    def fail(*args, **kwargs):
        raise original

    if phase == "object":
        # Install before E02 captures and guards the public API.
        with monkeypatch.context() as patch:
            patch.setattr(db, "begin_nested", fail)
            yield
    else:
        # A real SQLAlchemy savepoint event, before physical materialization.
        event.listen(engine, "savepoint", fail)
        try:
            yield
        finally:
            event.remove(engine, "savepoint", fail)


@pytest.mark.parametrize("phase", ["object", "materialize"])
@pytest.mark.parametrize("prior_work", [False, True], ids=["empty", "flushed"])
@pytest.mark.parametrize("error_type", [RuntimeError, BaseException], ids=["exception", "baseexception"])
def test_savepoint_creation_failure_is_fatal(policy_engine, monkeypatch, phase, prior_work, error_type):
    original = error_type("Synthetic savepoint creation failure")
    body_entered = False
    with Session(policy_engine, autoflush=False) as db:
        cached = db.get(Lead, 1)
        with injected_creation_failure(db, policy_engine, phase, original, monkeypatch):
            with pytest.raises(TransactionAborted):
                with tx(db):
                    root = current_root(db)
                    if prior_work:
                        cached.status = "Contacted"
                        db.flush()
                    connection = db.connection()
                    with pytest.raises(error_type) as caught:
                        with service_savepoint(db):
                            body_entered = True
                    assert caught.value is original and not body_entered
                    assert root.broken and root.failed
                    assert _permit.get() is None and _flushing.get() is None
                    for operation in (
                        lambda: db.query(Lead).filter(Lead.id == 1).first(),
                        lambda: db.execute(select(Lead.id)).all(),
                        lambda: connection.scalar(select(Lead.status)),
                        lambda: connection.execute(update(Lead).values(status="Lost")),
                        db.commit,
                    ):
                        with pytest.raises(TransactionPolicyViolation):
                            operation()
                    cached.status = "Lost"
                    with pytest.raises(TransactionPolicyViolation):
                        db.flush()
                    with pytest.raises(TransactionPolicyViolation):
                        with tx(db):
                            pytest.fail("Nested E02 resumed after failed savepoint creation")
                    with pytest.raises(TransactionPolicyViolation):
                        with service_savepoint(db):
                            pytest.fail("A second savepoint resumed a broken root")
                    assert root.broken and root.failed and _permit.get() is None
        assert current_root(db) is None and _permit.get() is None and _flushing.get() is None
        assert root.finished and root.listeners == root.methods == []
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("error_type", [RuntimeError, BaseException], ids=["exception", "baseexception"])
def test_uncaught_creation_failure_survives_cleanup_failure(policy_engine, monkeypatch, error_type):
    original = error_type("Synthetic original creation failure")
    def fail_cleanup():
        raise RuntimeError("Synthetic invalidation failure")

    with Session(policy_engine, autoflush=False) as db:
        monkeypatch.setattr(db, "invalidate", fail_cleanup)
        with injected_creation_failure(db, policy_engine, "materialize", original, monkeypatch):
            with pytest.raises(error_type) as caught:
                with tx(db):
                    root = current_root(db)
                    change(db)
                    with service_savepoint(db):
                        pytest.fail("Savepoint body entered after creation failed")
        assert caught.value is original and root.broken and root.failed
        assert current_root(db) is None and _permit.get() is None and _flushing.get() is None
        assert root.finished and root.listeners == root.methods == []
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("phase", ["object", "materialize"])
def test_creation_failure_breaks_a_fresh_empty_root(policy_engine, monkeypatch, phase):
    original = RuntimeError("Synthetic empty-root creation failure")
    with Session(policy_engine, autoflush=False) as db:
        assert not db.in_transaction()
        with injected_creation_failure(db, policy_engine, phase, original, monkeypatch):
            with pytest.raises(TransactionAborted):
                with tx(db):
                    root = current_root(db)
                    assert root.authority.connection is None and not db.in_transaction()
                    with pytest.raises(RuntimeError) as caught:
                        with service_savepoint(db):
                            pytest.fail("An empty root entered a failed savepoint body")
                    assert caught.value is original and root.broken and root.failed
                    assert _permit.get() is None and _flushing.get() is None
                    with pytest.raises(TransactionPolicyViolation):
                        db.scalar(select(Lead.id))
        assert current_root(db) is None and _permit.get() is None
    assert value(policy_engine) == "New"


def test_creation_failure_rolls_back_prior_lead_and_audit(policy_engine, monkeypatch):
    from backend.models.audit_event import AuditEvent
    from backend.schemas.action_permission import ActionPermission, MachineAuthorizationContext
    from backend.schemas.execution_principal import ExecutionPrincipal
    from backend.services.lead_service import LeadService

    original = RuntimeError("Synthetic composed-command creation failure")
    principal = ExecutionPrincipal.for_system("test-fixture", 1)
    context = MachineAuthorizationContext(principal, frozenset({ActionPermission.LEAD_CREATE}))
    with Session(policy_engine, autoflush=False) as db:
        with injected_creation_failure(db, policy_engine, "materialize", original, monkeypatch):
            with pytest.raises(TransactionAborted):
                with tx(db):
                    LeadService(db).create_lead(principal, company="Synthetic",
                        email="r1-composed@example.invalid", source="test", organization_id=1,
                        machine_context=context)
                    assert len(list(db.scalars(select(AuditEvent.event_id)))) == 1
                    with pytest.raises(RuntimeError) as caught:
                        with service_savepoint(db):
                            pytest.fail("Failed creation exposed its body")
                    assert caught.value is original
                    assert current_root(db).broken and current_root(db).failed
    with Session(policy_engine) as observer:
        assert observer.scalar(select(Lead.id).where(Lead.email == "r1-composed@example.invalid")) is None
        assert list(observer.scalars(select(AuditEvent.event_id))) == []


def test_caught_release_failure_remains_fatal(policy_engine):
    original = RuntimeError("Synthetic release failure")
    def fail_release(*args):
        raise original

    event.listen(policy_engine, "release_savepoint", fail_release)
    try:
        with Session(policy_engine, autoflush=False) as db:
            with pytest.raises(TransactionAborted):
                with tx(db):
                    with pytest.raises(RuntimeError) as caught:
                        with service_savepoint(db):
                            change(db)
                    assert caught.value is original
                    assert current_root(db).broken and current_root(db).failed
                    assert _permit.get() is None
                    with pytest.raises(TransactionPolicyViolation):
                        db.scalar(select(Lead.id))
            assert current_root(db) is None and _permit.get() is None
    finally:
        event.remove(policy_engine, "release_savepoint", fail_release)
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("attack", ["COMMIT", "ROLLBACK", "RELEASE x", "SAVEPOINT x",
                                  "session_commit", "connection_rollback"])
def test_create_permit_cannot_authorize_reentrant_control(policy_engine, attack):
    with Session(policy_engine, autoflush=False) as db:
        def unexpected(connection, name):
            if attack == "session_commit":
                db.commit()
            elif attack == "connection_rollback":
                connection.rollback()
            else:
                connection.exec_driver_sql(attack)

        event.listen(policy_engine, "savepoint", unexpected)
        try:
            with pytest.raises(TransactionAborted):
                with tx(db):
                    change(db)
                    with pytest.raises(TransactionPolicyViolation):
                        with service_savepoint(db):
                            pytest.fail("Reentrant control exposed a savepoint body")
                    assert current_root(db).broken and current_root(db).failed
                    assert _permit.get() is None
            assert current_root(db) is None and _permit.get() is None
        finally:
            event.remove(policy_engine, "savepoint", unexpected)
    assert value(policy_engine) == "New"


# Public compiler extensions exercise the final SQL boundary without DDL or text.
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import Executable, ClauseElement


class CompiledProbe(Executable, ClauseElement):
    inherit_cache = False

    def __init__(self, sql):
        self.sql = sql


@compiles(CompiledProbe)
def compile_probe(element, compiler, **kwargs):
    return element.sql


R3A_CONTROL_SQL = [
    "COMMIT", "END", "ROLLBACK", "ROLLBACK WORK", "BEGIN", "BEGIN DEFERRED",
    "BEGIN IMMEDIATE", "BEGIN EXCLUSIVE", "SAVEPOINT x", "RELEASE x",
    "ROLLBACK TO x", "ROLLBACK TO SAVEPOINT x", " commit ", "/*x*/ COMMIT",
    "--x\nCOMMIT", "--x\rCOMMIT", "CoMmIt;", "SELECT 1; COMMIT", "SELECT 1; /*x*/ ROLLBACK",
    "START TRANSACTION", "PREPARE TRANSACTION 'x'", "ABORT", "SET TRANSACTION READ ONLY",
    "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY", "; ; COMMIT;",
    "ROLLBACK /*x*/ TO SAVEPOINT x", "SAVEPOINT \"x\"", "SAVEPOINT [x]", "SAVEPOINT `x`",
]


@pytest.mark.parametrize("representation", ["ddl", "text", "driver", "custom"])
@pytest.mark.parametrize("sql", R3A_CONTROL_SQL)
def test_r3a_control_is_denied_before_driver(policy_engine, representation, sql):
    from sqlalchemy import DDL

    reached_driver = []
    def executed(conn, cursor, statement, parameters, context, many):
        if statement == sql:
            reached_driver.append(statement)

    event.listen(policy_engine, "after_cursor_execute", executed)
    try:
        with Session(policy_engine) as db:
            with pytest.raises(TransactionAborted):
                with tx(db):
                    change(db)
                    reached_driver.clear()  # Exclude E02's authorized physical BEGIN.
                    with pytest.raises(TransactionPolicyViolation):
                        if representation == "driver":
                            db.connection().exec_driver_sql(sql)
                        else:
                            constructor = {"ddl": DDL, "text": text, "custom": CompiledProbe}[representation]
                            db.execute(constructor(sql))
                    assert current_root(db).broken and current_root(db).failed
                    assert _permit.get() is None
        assert reached_driver == []
        assert value(policy_engine) == "New"
    finally:
        event.remove(policy_engine, "after_cursor_execute", executed)


@pytest.mark.parametrize("exit_mode", ["normal", "outer_failure"])
def test_r3a_ddl_commit_observer(policy_engine, exit_mode):
    from sqlalchemy import DDL, Table, Column, Integer, String, MetaData

    items = Table("probe_items", MetaData(), Column("id", Integer, primary_key=True), Column("value", String))
    items.create(policy_engine)
    with policy_engine.begin() as connection:
        connection.execute(items.insert().values(id=1, value="original"))
    original = RuntimeError("Synthetic outer failure")
    expected = TransactionAborted if exit_mode == "normal" else RuntimeError
    with Session(policy_engine) as db:
        with pytest.raises(expected) as caught:
            with tx(db):
                db.execute(update(items).where(items.c.id == 1).values(value="changed"))
                with pytest.raises(TransactionPolicyViolation):
                    db.execute(DDL("COMMIT"))
                root = current_root(db)
                assert root.broken and root.failed and root.authority.driver.in_transaction
                assert db.is_active and db.in_transaction()
                assert root.authority.connection.in_transaction()
                if exit_mode == "outer_failure":
                    raise original
        if exit_mode == "outer_failure":
            assert caught.value is original
        assert current_root(db) is None and _permit.get() is None
    with policy_engine.connect() as observer:
        assert observer.scalar(select(items.c.value)) == "original"


def test_r3a_caught_ddl_cannot_resume_business(policy_engine):
    from sqlalchemy import DDL

    with Session(policy_engine, autoflush=False) as db:
        with pytest.raises(TransactionAborted):
            with tx(db):
                cached = db.get(Lead, 1)
                change(db)
                connection = db.connection()
                with pytest.raises(TransactionPolicyViolation):
                    db.execute(DDL("COMMIT"))
                for operation in (
                    lambda: db.query(Lead).first(), lambda: db.get(Lead, 1),
                    lambda: db.execute(select(Lead.id)), lambda: connection.scalar(select(Lead.id)),
                    lambda: connection.execute(update(Lead).where(Lead.id == 1).values(status="Won")),
                    db.flush, db.commit,
                ):
                    with pytest.raises(TransactionPolicyViolation):
                        operation()
                cached.status = "Won"
                with pytest.raises(TransactionPolicyViolation):
                    db.flush()
                with pytest.raises(TransactionPolicyViolation):
                    with tx(db):
                        pytest.fail("Broken root resumed nested E02")
                with pytest.raises(TransactionPolicyViolation):
                    with service_savepoint(db):
                        pytest.fail("Broken root resumed savepoint")
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("kind", ["CreateTable", "DropTable", "CreateIndex", "DropIndex", "DDL"])
def test_r3a_runtime_schema_ddl_denied(policy_engine, kind):
    from sqlalchemy import Table, Column, Integer, MetaData, Index, inspect, schema

    table = Table("schema_probe", MetaData(), Column("id", Integer))
    table.create(policy_engine)
    index = Index("ix_schema_probe", table.c.id)
    index.create(policy_engine)
    statement = schema.DDL("SELECT 1") if kind == "DDL" else getattr(schema, kind)(index if "Index" in kind else table)
    before = (inspect(policy_engine).get_table_names(), inspect(policy_engine).get_indexes(table.name))
    with Session(policy_engine) as db:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)
                db.execute(statement)
    assert before == (inspect(policy_engine).get_table_names(), inspect(policy_engine).get_indexes(table.name))
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("sql", [
    "CREATE TABLE unexpected (id INTEGER)", "DROP TABLE leads",
    "CREATE INDEX unexpected ON leads (id)", "DROP INDEX ix_leads_id",
    "ALTER TABLE leads ADD COLUMN unexpected INTEGER", "TRUNCATE leads",
    "COMMENT ON TABLE leads IS 'unexpected'", "GRANT SELECT ON leads TO PUBLIC",
    "REVOKE SELECT ON leads FROM PUBLIC",
])
def test_r3a_custom_compiler_cannot_emit_schema_ddl(policy_engine, sql):
    from sqlalchemy import inspect

    before = inspect(policy_engine).get_table_names()
    with Session(policy_engine) as db:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)
                db.execute(CompiledProbe(sql))
    assert inspect(policy_engine).get_table_names() == before
    assert value(policy_engine) == "New"


def test_r3a_typed_crud_orm_and_authorized_control(policy_engine):
    from sqlalchemy import insert, delete, func

    statements = []
    def executed(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(policy_engine, "after_cursor_execute", executed)
    try:
        with Session(policy_engine) as db, tx(db):
            assert db.scalar(select(func.count()).select_from(Lead)) == 1
            assert not current_root(db).physical
            db.execute(insert(Lead).values(organization_id=1, company="Synthetic", email="typed@example.invalid", source="test"))
            assert current_root(db).physical
            change(db)
            with service_savepoint(db):
                db.get(Lead, 1).notes = "typed flush"
                db.flush()
            with pytest.raises(ValueError):
                with service_savepoint(db):
                    db.get(Lead, 1).status = "Won"
                    db.flush()
                    raise ValueError("Synthetic row failure")
            db.execute(delete(Lead).where(Lead.organization_id == 1, Lead.email == "typed@example.invalid"))
        assert statements.count("BEGIN") == 1
        assert any(s.startswith("SAVEPOINT ") for s in statements)
        assert any(s.startswith("RELEASE SAVEPOINT ") for s in statements)
        assert any(s.startswith("ROLLBACK TO SAVEPOINT ") for s in statements)
        assert value(policy_engine) == "Lost"
    finally:
        event.remove(policy_engine, "after_cursor_execute", executed)


def test_r3a_ddl_outside_governance_is_not_globally_blocked(policy_engine):
    from sqlalchemy import DDL, inspect

    with policy_engine.begin() as connection:
        connection.execute(DDL("CREATE TABLE operator_probe (id INTEGER)"))
    assert "operator_probe" in inspect(policy_engine).get_table_names()


@pytest.mark.parametrize("sql,commands", [
    ("/*x*/ CoMmIt; -- end", ("COMMIT",)),
    ("--x\rCOMMIT", ("COMMIT",)),
    ("SELECT 'COMMIT; ROLLBACK'", ()),
    ('SELECT "COMMIT; ROLLBACK"', ()),
    ("SELECT 'it''s; COMMIT'", ()),
    ("SELECT $$COMMIT; ROLLBACK$$", ()),
    ("SELECT $tag$COMMIT; ROLLBACK$tag$; COMMIT", ("COMMIT",)),
    ("SELECT 1 /* COMMIT; */; -- x\nBEGIN", ("BEGIN",)),
    ("ROLLBACK WORK TO SAVEPOINT x", ("ROLLBACK TO",)),
    ("START TRANSACTION; END", ("START TRANSACTION", "END")),
    ("SELECT 'unterminated", None), ("/* unterminated", None),
    ("/* outer /* nested */ COMMIT */ SELECT 1", None),
    (r"SELECT 'escape\'; COMMIT --'", None),
])
def test_r3a_sql_classification_literals_and_comments(sql, commands):
    from backend.database.transaction_policy import _restricted_sql_commands

    assert _restricted_sql_commands(sql) == commands


@pytest.mark.parametrize("sql", ["SELECT 'COMMIT; ROLLBACK'", "SELECT 'it''s; COMMIT'"])
def test_r3a_compiled_literal_is_not_transaction_control(policy_engine, sql):
    with Session(policy_engine) as db, tx(db):
        assert isinstance(db.scalar(CompiledProbe(sql)), str)


def assert_r4a_context_clean(db):
    assert current_root(db) is None
    assert _permit.get() is None
    assert _flushing.get() is None


@pytest.mark.parametrize("later_session", ["same", "different", "copied_context"])
def test_r4a_flush_policy_recovery_does_not_poison_later_root(policy_engine, later_session):
    from contextvars import copy_context
    from sqlalchemy import DDL

    def attack(_mapper, connection, _target):
        connection.execute(DDL("COMMIT"))

    with Session(policy_engine) as db:
        event.listen(Lead, "before_insert", attack)
        try:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    change(db)
                    root = current_root(db)
                    with service_savepoint(db):
                        db.add(Lead(organization_id=1, company="Synthetic",
                                    email="r4a@example.invalid", source="test"))
                        db.flush()
        finally:
            event.remove(Lead, "before_insert", attack)
        assert_r4a_context_clean(db)
        assert root.finished and root.listeners == root.methods == []
        assert not db.in_transaction()
        assert value(policy_engine) == "New"
        with Session(policy_engine) as observer:
            assert observer.scalar(select(Lead.id).where(Lead.email == "r4a@example.invalid")) is None

        def later(session):
            assert_r4a_context_clean(session)
            with tx(session):
                assert current_root(session).authority.nonce is not root.authority.nonce
                change(session)
            assert_r4a_context_clean(session)

        if later_session == "same":
            later(db)
        else:
            with Session(policy_engine) as other:
                if later_session == "copied_context":
                    copy_context().run(later, other)
                else:
                    later(other)
        assert_r4a_context_clean(db)
    assert value(policy_engine) == "Lost"


@pytest.mark.parametrize("exit_kind", [
    "success", "business_error", "baseexception", "session_commit", "connection_commit",
    "text_commit", "driver_commit", "ddl_commit", "invalidate",
])
def test_r4a_root_exit_context_matrix(policy_engine, exit_kind):
    from sqlalchemy import DDL

    original = BaseException("Synthetic root interruption") if exit_kind == "baseexception" else ValueError("Synthetic root failure")
    with Session(policy_engine) as db:
        def operation():
            with tx(db):
                change(db)
                if exit_kind in {"business_error", "baseexception"}:
                    raise original
                if exit_kind == "session_commit":
                    db.commit()
                elif exit_kind == "connection_commit":
                    db.connection().commit()
                elif exit_kind == "text_commit":
                    db.execute(text("COMMIT"))
                elif exit_kind == "driver_commit":
                    db.connection().exec_driver_sql("COMMIT")
                elif exit_kind == "ddl_commit":
                    db.execute(DDL("COMMIT"))
                elif exit_kind == "invalidate":
                    db.connection().invalidate()
                    db.scalar(select(Lead.id))

        if exit_kind == "success":
            operation()
        elif exit_kind in {"business_error", "baseexception"}:
            with pytest.raises(type(original)) as caught:
                operation()
            assert caught.value is original
        else:
            with pytest.raises(TransactionPolicyViolation):
                operation()
        assert_r4a_context_clean(db)
    assert value(policy_engine) == ("Lost" if exit_kind == "success" else "New")


@pytest.mark.parametrize("phase", ["create", "release", "rollback"])
@pytest.mark.parametrize("error_type", [RuntimeError, BaseException])
def test_r4a_savepoint_mechanism_failure_context(policy_engine, phase, error_type):
    original = error_type("Synthetic savepoint mechanism interruption")
    body_error = ValueError("Synthetic recoverable row failure")

    def fail(*args):
        raise original

    event_name = {"create": "savepoint", "release": "release_savepoint", "rollback": "rollback_savepoint"}[phase]
    event.listen(policy_engine, event_name, fail)
    try:
        with Session(policy_engine) as db:
            with pytest.raises(TransactionAborted):
                with tx(db):
                    change(db)
                    with pytest.raises(type(body_error) if phase == "rollback" else error_type) as caught:
                        with service_savepoint(db):
                            if phase == "create":
                                pytest.fail("Failed creation exposed the body")
                            if phase == "rollback":
                                raise body_error
                    assert caught.value is (body_error if phase == "rollback" else original)
                    assert current_root(db).broken and current_root(db).failed
                    assert _permit.get() is None and _flushing.get() is None
            assert_r4a_context_clean(db)
    finally:
        event.remove(policy_engine, event_name, fail)
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("error_type", [RuntimeError, BaseException])
@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_r4a_interrupted_recovery_resets_unconsumed_permit(policy_engine, monkeypatch, error_type, cleanup_failure):
    original = error_type("Synthetic recovery interruption")
    observed = []

    def interrupt(*args):
        p = _permit.get()
        assert p.operation is Operation.SAVEPOINT_ROLLBACK
        assert p.remaining == ["savepoint_sql"]
        observed.append(p)
        raise original

    with Session(policy_engine) as db:
        if cleanup_failure:
            def fail_cleanup():
                raise RuntimeError("Synthetic invalidation failure")
            monkeypatch.setattr(db, "invalidate", fail_cleanup)
        with pytest.raises(error_type) as caught:
            with tx(db):
                change(db)
                with service_savepoint(db):
                    connection = db.connection()
                    event.listen(connection, "rollback_savepoint", interrupt)
                    db.add(Lead(organization_id=1, company="Synthetic", email="tx@example.invalid", source="test"))
                    db.flush()
        assert caught.value is original and len(observed) == 1
        assert observed[0].remaining == []
        assert_r4a_context_clean(db)
        event.remove(connection, "rollback_savepoint", interrupt)
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("broken", [False, True], ids=["healthy_recovery", "broken_recovery"])
@pytest.mark.parametrize("attack", ["commit", "rollback", "savepoint", "release", "ddl", "select", "insert", "update", "delete"])
def test_r4a_recovery_permit_rejects_reentrant_execution(policy_engine, broken, attack):
    from sqlalchemy import DDL, delete, insert
    from sqlalchemy.sql.expression import ReleaseSavepointClause

    observed = []

    def reject_from_mapper(_mapper, connection, _target):
        connection.execute(DDL("COMMIT"))

    def reenter(connection, name, _context):
        p = _permit.get()
        assert p.operation is Operation.SAVEPOINT_ROLLBACK
        assert p.remaining == ["savepoint_sql"]
        operations = {
            "commit": connection.commit,
            "rollback": connection.rollback,
            "savepoint": connection.begin_nested,
            "release": lambda: connection.execute(ReleaseSavepointClause(name)),
            "ddl": lambda: connection.execute(DDL("CREATE TABLE unexpected (id INTEGER)")),
            "select": lambda: connection.execute(select(Lead.id)),
            "insert": lambda: connection.execute(insert(Lead).values(organization_id=1, company="Synthetic", email="reentrant@example.invalid", source="test")),
            "update": lambda: connection.execute(update(Lead).values(status="Won")),
            "delete": lambda: connection.execute(delete(Lead)),
        }
        with pytest.raises(TransactionPolicyViolation):
            operations[attack]()
        observed.append(p)

    with Session(policy_engine) as db:
        if broken:
            event.listen(Lead, "before_insert", reject_from_mapper)
        try:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    change(db)
                    with service_savepoint(db):
                        connection = db.connection()
                        event.listen(connection, "rollback_savepoint", reenter)
                        db.add(Lead(organization_id=1, company="Synthetic", email="tx@example.invalid", source="test"))
                        db.flush()
        finally:
            if broken:
                event.remove(Lead, "before_insert", reject_from_mapper)
            event.remove(connection, "rollback_savepoint", reenter)
        assert len(observed) == 1 and observed[0].remaining == []
        assert_r4a_context_clean(db)
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("body_error", [None, ValueError, BaseException])
def test_r4a_successful_savepoint_and_recoverable_error_context(policy_engine, body_error):
    with Session(policy_engine) as db, tx(db):
        if body_error is None:
            with service_savepoint(db):
                change(db)
        else:
            with pytest.raises(body_error):
                with service_savepoint(db):
                    change(db)
                    raise body_error("Synthetic savepoint body interruption")
            assert value(policy_engine) == "New"
            change(db)
        assert _permit.get() is None and _flushing.get() is None
        assert not current_root(db).broken
    assert_r4a_context_clean(db)
    assert value(policy_engine) == "Lost"


@pytest.mark.parametrize("consumed", [0, 1, 2])
@pytest.mark.parametrize("interrupted", [False, True])
def test_r4a_permit_scope_resets_every_consumption_state(policy_engine, consumed, interrupted):
    with Session(policy_engine) as db, tx(db):
        root = current_root(db)

        def scope():
            with root.permit(Operation.SAVEPOINT_ROLLBACK, "first", "second"):
                nonlocal permit
                permit = _permit.get()
                for stage in ["first", "second"][:consumed]:
                    root.consume(stage, {Operation.SAVEPOINT_ROLLBACK})
                if interrupted:
                    raise BaseException("Synthetic permit interruption")

        permit = None
        if interrupted:
            with pytest.raises(BaseException):
                scope()
        else:
            scope()
        assert permit.remaining == [] and _permit.get() is None
    assert_r4a_context_clean(db)


def test_r4a_nested_permit_is_rejected_without_erasing_outer(policy_engine):
    with Session(policy_engine) as db:
        with pytest.raises(TransactionAborted):
            with tx(db):
                root = current_root(db)
                with root.permit(Operation.PHYSICAL_BEGIN, "outer"):
                    outer = _permit.get()
                    with pytest.raises(TransactionPolicyViolation):
                        with root.permit(Operation.ROOT_COMMIT, "inner"):
                            pytest.fail("Nested permit entry must be rejected")
                    assert _permit.get() is outer and outer.remaining == ["outer"]
                assert _permit.get() is None
        assert_r4a_context_clean(db)


def test_r4a_other_root_cleanup_preserves_enclosing_permit(policy_engine):
    with Session(policy_engine) as a, Session(policy_engine) as b, tx(a):
        root = current_root(a)
        with root.permit(Operation.PHYSICAL_BEGIN, "outer"):
            outer = _permit.get()
            with pytest.raises(TransactionPolicyViolation):
                with tx(b):
                    with current_root(b).permit(Operation.ROOT_COMMIT, "inner"):
                        pytest.fail("Cross-root permit nesting must be rejected")
            assert current_root(b) is None
            assert _permit.get() is outer and outer.remaining == ["outer"]
        assert _permit.get() is None
    assert_r4a_context_clean(a)


def test_r4a_root_removal_revokes_active_permit_idempotently(policy_engine):
    original = ValueError("Synthetic root exit during infrastructure scope")
    with Session(policy_engine) as db:
        with pytest.raises(ValueError) as caught:
            with tx(db):
                root = current_root(db)
                with root.permit(Operation.SAVEPOINT_ROLLBACK, "savepoint_sql"):
                    permit = _permit.get()
                    root.remove()
                    assert_r4a_context_clean(db)
                    assert permit.remaining == []
                    root.remove()
                    raise original
        assert caught.value is original
        assert_r4a_context_clean(db)


def test_r4a_old_root_permit_cannot_authorize_new_root(policy_engine):
    with Session(policy_engine) as db:
        with tx(db):
            root = current_root(db)
            with root.permit(Operation.ROOT_COMMIT, "session_commit_api"):
                old = _permit.get()
        old.remaining[:] = ["session_commit_api"]  # Nonce rejection must precede consumption.
        token = _permit.set(old)
        try:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    assert current_root(db).authority.nonce is not old.authority.nonce
                    db.commit()
            assert _permit.get() is old and old.remaining == ["session_commit_api"]
        finally:
            _permit.reset(token)
        assert_r4a_context_clean(db)


def test_r4a_permit_connection_binding_cannot_be_transferred(policy_engine):
    from dataclasses import replace

    with Session(policy_engine) as db, policy_engine.connect() as other:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                db.connection()
                root = current_root(db)
                with root.permit(Operation.ROOT_COMMIT, "session_commit_api"):
                    p = _permit.get()
                    p.authority = replace(p.authority, connection=other)
                    db.commit()
        assert_r4a_context_clean(db)


def r5a_lead(email):
    return Lead(organization_id=1, company="Synthetic", email=email, source="test")


def r5a_emails(db):
    return list(db.scalars(select(Lead.email).where(Lead.organization_id == 1).order_by(Lead.email)))


@pytest.mark.parametrize("explicit", [False, True], ids=["implicit", "explicit"])
@pytest.mark.parametrize("outer_failure", [False, True], ids=["commit", "outer_rollback"])
@pytest.mark.parametrize("sibling", [False, True], ids=["duplicate_only", "valid_sibling"])
def test_r5a_conflict_recovery_and_outer_authority(policy_engine, explicit, outer_failure, sibling):
    commits, errors, rollbacks, flushes = [], [], [], []
    event.listen(policy_engine, "commit", lambda connection: commits.append(True))
    event.listen(policy_engine, "handle_error", lambda context: errors.append(context.sqlalchemy_exception))

    def before_flush(db, context, instances):
        assert _permit.get() is None
        assert _flushing.get().nonce is current_root(db).authority.nonce
        flushes.append(True)

    def executed(connection, cursor, statement, parameters, context, many):
        if statement.startswith("ROLLBACK TO SAVEPOINT"):
            rollbacks.append(statement)

    event.listen(policy_engine, "after_cursor_execute", executed)
    with Session(policy_engine, autoflush=False) as db:
        event.listen(db, "before_flush", before_flush)

        def operation():
            with tx(db):
                original = db.get(Lead, 1)
                original.notes = "prior outer work"
                db.flush()
                with pytest.raises(IntegrityError) as caught:
                    with service_savepoint(db):
                        if sibling:
                            db.add(r5a_lead("failed-sibling@example.invalid"))
                        db.add(r5a_lead("tx@example.invalid"))
                        if explicit:
                            db.flush()
                assert caught.value is errors[0]
                root = current_root(db)
                assert not root.broken and not root.failed and db.is_active
                assert not db.in_nested_transaction()
                assert _permit.get() is None and _flushing.get() is None
                assert db.scalar(select(Lead.notes).where(Lead.id == 1)) == "prior outer work"
                assert r5a_emails(db) == ["tx@example.invalid"]
                db.add(r5a_lead("later@example.invalid"))
                db.flush()
                with service_savepoint(db):
                    db.add(r5a_lead("second-savepoint@example.invalid"))
                assert _permit.get() is None and _flushing.get() is None
                with Session(policy_engine) as observer:
                    assert r5a_emails(observer) == ["tx@example.invalid"]
                    assert observer.get(Lead, 1).notes is None
                if outer_failure:
                    raise ValueError("Synthetic later outer failure")

        if outer_failure:
            with pytest.raises(ValueError):
                operation()
        else:
            operation()
        assert_r4a_context_clean(db)
    assert len(rollbacks) == 1  # Automatic recovery; helper cleanup emits no second rollback SQL.
    assert len(commits) == (0 if outer_failure else 1)
    assert flushes
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == (["tx@example.invalid"] if outer_failure else [
            "later@example.invalid", "second-savepoint@example.invalid", "tx@example.invalid",
        ])
        assert observer.get(Lead, 1).notes == (None if outer_failure else "prior outer work")


@pytest.mark.parametrize("kind", ["empty", "core", "explicit_insert", "implicit_insert", "multiple_inserts", "update", "delete"])
@pytest.mark.parametrize("outer_failure", [False, True], ids=["commit", "outer_rollback"])
def test_r5a_materializes_business_state_before_release(policy_engine, kind, outer_failure):
    from sqlalchemy import insert

    releases, flushes = [], []
    with Session(policy_engine, autoflush=False) as db:
        def before_flush(db, context, instances):
            assert _permit.get() is None
            flushes.append(True)

        def before_commit(db):
            p = _permit.get()
            if p is not None and p.operation is Operation.SAVEPOINT_RELEASE:
                assert not db.new and not db.dirty and not db.deleted

        def release(connection, name, context):
            assert _permit.get().operation is Operation.SAVEPOINT_RELEASE
            assert not db.new and not db.dirty and not db.deleted
            releases.append(name)

        event.listen(db, "before_flush", before_flush)
        event.listen(db, "before_commit", before_commit)
        event.listen(policy_engine, "release_savepoint", release)

        def operation():
            with tx(db):
                with service_savepoint(db):
                    if kind == "core":
                        db.execute(insert(Lead).values(organization_id=1, company="Synthetic", email="core@example.invalid", source="test"))
                        change(db)
                    elif kind in {"explicit_insert", "implicit_insert", "multiple_inserts"}:
                        db.add(r5a_lead("one@example.invalid"))
                        if kind == "multiple_inserts":
                            db.add(r5a_lead("two@example.invalid"))
                        if kind == "explicit_insert":
                            db.flush()
                    elif kind == "update":
                        db.get(Lead, 1).status = "Lost"
                    elif kind == "delete":
                        db.delete(db.get(Lead, 1))
                assert _permit.get() is None and _flushing.get() is None
                assert not current_root(db).broken
                with Session(policy_engine) as observer:
                    assert r5a_emails(observer) == ["tx@example.invalid"]
                    assert observer.get(Lead, 1).status == "New"
                if outer_failure:
                    raise ValueError("Synthetic outer rollback")

        if outer_failure:
            with pytest.raises(ValueError):
                operation()
        else:
            operation()
        assert_r4a_context_clean(db)
    assert len(releases) == 1
    assert len(flushes) == (0 if kind in {"empty", "core"} else 1)
    with Session(policy_engine) as observer:
        expected = ["tx@example.invalid"]
        if not outer_failure:
            if kind == "core":
                expected = ["core@example.invalid", "tx@example.invalid"]
            elif kind in {"explicit_insert", "implicit_insert"}:
                expected = ["one@example.invalid", "tx@example.invalid"]
            elif kind == "multiple_inserts":
                expected = ["one@example.invalid", "two@example.invalid", "tx@example.invalid"]
            elif kind == "delete":
                expected = []
        assert r5a_emails(observer) == expected
        if kind != "delete" or outer_failure:
            assert observer.get(Lead, 1).status == ("Lost" if not outer_failure and kind in {"core", "update"} else "New")


def test_r5a_postflush_callback_work_is_materialized_before_release(policy_engine):
    flushes, releases = [], []
    with Session(policy_engine, autoflush=False) as db, tx(db):
        def before_flush(db, context, instances):
            assert _permit.get() is None
            flushes.append(True)

        def followup(db, context):
            if len(flushes) == 1:
                db.add(r5a_lead("callback@example.invalid"))

        def release(connection, name, context):
            assert not db.new and not db.dirty and not db.deleted
            releases.append(name)

        event.listen(db, "before_flush", before_flush)
        event.listen(db, "after_flush_postexec", followup)
        event.listen(policy_engine, "release_savepoint", release)
        with service_savepoint(db):
            db.add(r5a_lead("body@example.invalid"))
        assert len(flushes) == 2 and len(releases) == 1
        assert _permit.get() is None
    assert_r4a_context_clean(db)
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["body@example.invalid", "callback@example.invalid", "tx@example.invalid"]


def test_r5a_before_commit_callback_cannot_start_business_flush_under_release(policy_engine):
    flushes = []
    with Session(policy_engine, autoflush=False) as db:
        def before_commit(db):
            if _permit.get().operation is Operation.SAVEPOINT_RELEASE:
                db.add(r5a_lead("late-callback@example.invalid"))

        def before_flush(db, context, instances):
            flushes.append(_permit.get())

        event.listen(db, "before_commit", before_commit)
        event.listen(db, "before_flush", before_flush)
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                with service_savepoint(db):
                    db.add(r5a_lead("body@example.invalid"))
        assert_r4a_context_clean(db)
    assert flushes == [None]
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["tx@example.invalid"]


@pytest.mark.parametrize("phase", ["event", "driver"])
@pytest.mark.parametrize("explicit", [False, True], ids=["implicit", "explicit"])
@pytest.mark.parametrize("error_type", [RuntimeError, BaseException])
def test_r5a_failed_automatic_rollback_breaks_root(policy_engine, monkeypatch, phase, explicit, error_type):
    original = error_type("Synthetic physical savepoint rollback failure")
    observed = []

    def fail(*args):
        p = _permit.get()
        assert p.operation is Operation.SAVEPOINT_ROLLBACK
        assert p.remaining == (["savepoint_sql"] if phase == "event" else [])
        observed.append(p)
        raise original

    with Session(policy_engine, autoflush=False) as db:
        with pytest.raises(TransactionAborted):
            with tx(db):
                change(db)
                connection = db.connection()
                if phase == "event":
                    event.listen(connection, "rollback_savepoint", fail)
                else:
                    original_execute = policy_engine.dialect.do_execute

                    def driver_failure(cursor, statement, parameters, context=None):
                        if statement.startswith("ROLLBACK TO SAVEPOINT"):
                            fail()
                        return original_execute(cursor, statement, parameters, context)

                    monkeypatch.setattr(policy_engine.dialect, "do_execute", driver_failure)
                with pytest.raises(error_type) as caught:
                    with service_savepoint(db):
                        db.add(r5a_lead("failed-sibling@example.invalid"))
                        db.add(r5a_lead("tx@example.invalid"))
                        if explicit:
                            db.flush()
                assert caught.value is original and len(observed) == 1
                root = current_root(db)
                assert root.broken and root.failed
                assert _permit.get() is None and _flushing.get() is None
                with pytest.raises(TransactionPolicyViolation):
                    db.scalar(select(Lead.id))
                with pytest.raises(TransactionPolicyViolation):
                    with service_savepoint(db):
                        pytest.fail("Failed recovery allowed another savepoint")
        assert_r4a_context_clean(db)
        if phase == "event":
            event.remove(connection, "rollback_savepoint", fail)
    assert value(policy_engine) == "New"
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["tx@example.invalid"]


@pytest.mark.parametrize("error_type", [RuntimeError, BaseException])
def test_r5a_actual_release_failure_remains_fatal(policy_engine, error_type):
    original = error_type("Synthetic physical release failure")
    materialized = []
    with Session(policy_engine, autoflush=False) as db:
        def release(connection, name, context):
            assert _permit.get().operation is Operation.SAVEPOINT_RELEASE
            assert not db.new and not db.dirty and not db.deleted
            assert connection.scalar(select(Lead.status).where(Lead.id == 1)) == "Lost"
            materialized.append(True)
            raise original

        event.listen(policy_engine, "release_savepoint", release)
        with pytest.raises(TransactionAborted):
            with tx(db):
                with pytest.raises(error_type) as caught:
                    with service_savepoint(db):
                        db.get(Lead, 1).status = "Lost"
                assert caught.value is original and materialized == [True]
                assert current_root(db).broken and current_root(db).failed
                assert _permit.get() is None and _flushing.get() is None
                with pytest.raises(TransactionPolicyViolation):
                    db.scalar(select(Lead.id))
        assert_r4a_context_clean(db)
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("failure", ["ddl", "exception", "baseexception"])
def test_r5a_governed_preflush_callback_failure(policy_engine, failure):
    from sqlalchemy import DDL

    original = BaseException("Synthetic callback interruption") if failure == "baseexception" else RuntimeError("Synthetic callback failure")
    seen, commits = [], []

    def attack(mapper, connection, target):
        assert _permit.get() is None
        seen.append(True)
        if failure == "ddl":
            connection.execute(DDL("COMMIT"))
        raise original

    event.listen(Lead, "before_insert", attack)
    event.listen(policy_engine, "commit", lambda connection: commits.append(True))
    try:
        with Session(policy_engine, autoflush=False) as db:
            with pytest.raises(TransactionPolicyViolation if failure == "ddl" else type(original)) as caught:
                with tx(db):
                    change(db)
                    root = current_root(db)
                    with service_savepoint(db):
                        db.add(r5a_lead("callback@example.invalid"))
            if failure == "ddl":
                assert root.broken and root.failed
            else:
                assert caught.value is original
            assert_r4a_context_clean(db)
    finally:
        event.remove(Lead, "before_insert", attack)
    assert seen == [True] and commits == []
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("attack", ["select", "update", "commit", "rollback", "savepoint"])
def test_r5a_release_callback_does_not_broaden_control_permit(policy_engine, attack):
    observed = []
    with Session(policy_engine, autoflush=False) as db:
        def reenter(connection, name, context):
            assert _permit.get().operation is Operation.SAVEPOINT_RELEASE
            observed.append(True)
            operations = {
                "select": lambda: connection.scalar(select(Lead.id)),
                "update": lambda: connection.execute(update(Lead).where(Lead.id == 1).values(notes="Existing typed SQL behavior")),
                "commit": connection.commit,
                "rollback": connection.rollback,
                "savepoint": connection.begin_nested,
            }
            operations[attack]()

        event.listen(policy_engine, "release_savepoint", reenter)

        def operation():
            with tx(db):
                with service_savepoint(db):
                    db.add(r5a_lead("released@example.invalid"))

        if attack in {"select", "update"}:
            operation()
        else:
            with pytest.raises(TransactionPolicyViolation):
                operation()
        assert observed == [True]
        assert_r4a_context_clean(db)
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == (["released@example.invalid", "tx@example.invalid"] if attack in {"select", "update"} else ["tx@example.invalid"])


def test_r5a_non_unique_integrity_conflict_is_recoverable(policy_engine):
    with Session(policy_engine, autoflush=False) as db, tx(db):
        with pytest.raises(IntegrityError):
            with service_savepoint(db):
                row = r5a_lead("not-null@example.invalid")
                row.company = None
                db.add(row)
        assert not current_root(db).broken and not current_root(db).failed
        assert _permit.get() is None and _flushing.get() is None
        with service_savepoint(db):
            db.add(r5a_lead("valid@example.invalid"))
    assert_r4a_context_clean(db)
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["tx@example.invalid", "valid@example.invalid"]


def test_r5a_nonconverging_flush_hook_is_bounded_and_savepoint_rolls_back(policy_engine):
    from sqlalchemy.orm.exc import FlushError

    created = []
    with Session(policy_engine, autoflush=False) as db, tx(db):
        def followup(db, context):
            assert _permit.get() is None
            created.append(True)
            db.add(r5a_lead(f"hook-{len(created)}@example.invalid"))

        event.listen(db, "after_flush_postexec", followup)
        try:
            with pytest.raises(FlushError):
                with service_savepoint(db):
                    db.add(r5a_lead("body@example.invalid"))
        finally:
            event.remove(db, "after_flush_postexec", followup)
        assert len(created) == 100
        assert not current_root(db).broken and not current_root(db).failed
        assert r5a_emails(db) == ["tx@example.invalid"]
        assert _permit.get() is None and _flushing.get() is None
    assert_r4a_context_clean(db)


def r6a_operation(db, operation):
    from sqlalchemy import insert

    if operation == "read":
        db.scalar(select(Lead.id))
    elif operation == "write":
        db.execute(insert(Lead).values(organization_id=1, company="Synthetic",
                   email="r6a@example.invalid", source="test"))
    elif operation == "orm":
        db.add(r5a_lead("r6a@example.invalid"))
        db.flush()
    elif operation == "connection":
        db.connection()
    elif operation == "savepoint":
        with service_savepoint(db):
            pytest.fail("Foreign ownership exposed a savepoint body")
    else:
        raise AssertionError(operation)


@pytest.mark.parametrize("external_state", ["idle", "begin", "nested", "autobegin"])
@pytest.mark.parametrize("operation", ["read", "write", "orm", "connection", "savepoint"])
def test_r6a_lazy_external_substitution_rejected_before_sql(policy_engine, external_state, operation):
    with policy_engine.connect() as external, Session(policy_engine) as db:
        if external_state == "begin":
            external.begin()
        elif external_state == "nested":
            external.begin_nested()
        elif external_state == "autobegin":
            external.execute(select(Lead.id)).all()
        foreign_transaction = external.get_transaction()
        executed = []

        def observe(*args):
            executed.append(True)

        event.listen(external, "before_cursor_execute", observe)
        with pytest.raises(TransactionAborted):
            with tx(db):
                root = current_root(db)
                assert root.authority.connection is None
                db.bind = external
                with pytest.raises(TransactionPolicyViolation):
                    r6a_operation(db, operation)
                assert root.broken and root.failed
                assert root.authority.connection is None and not root.physical
                # Restoring the Engine cannot revive a rejected root.
                db.bind = policy_engine
                with pytest.raises(TransactionPolicyViolation):
                    db.scalar(select(Lead.id))
                assert _permit.get() is None and _flushing.get() is None
        assert_r4a_context_clean(db)
        assert executed == []
        assert external.get_transaction() is foreign_transaction
        if foreign_transaction is not None:
            assert foreign_transaction.is_active
        event.remove(external, "before_cursor_execute", observe)
        external.rollback()
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["tx@example.invalid"]


@pytest.mark.parametrize("settlement", ["commit", "rollback"])
def test_r6a_external_owner_cannot_settle_successful_e02_work(policy_engine, settlement):
    with policy_engine.connect() as external, Session(policy_engine) as db:
        foreign = external.begin()
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                db.bind = external
                r6a_operation(db, "write")
        assert foreign.is_active
        assert_r4a_context_clean(db)
        with Session(policy_engine) as observer:
            assert r5a_emails(observer) == ["tx@example.invalid"]
        getattr(foreign, settlement)()
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["tx@example.invalid"]


@pytest.mark.parametrize("same_database", [False, True])
@pytest.mark.parametrize("operation", ["read", "write", "savepoint"])
def test_r6a_lazy_engine_substitution_cannot_transfer_authority(policy_engine, tmp_path, same_database, operation):
    url = policy_engine.url if same_database else "sqlite:///" + (tmp_path / "foreign.db").as_posix()
    other = create_engine(url)
    checkouts = []
    event.listen(other, "checkout", lambda *args: checkouts.append(True))
    try:
        with Session(policy_engine) as db:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    db.bind = other
                    r6a_operation(db, operation)
            assert_r4a_context_clean(db)
        assert checkouts == []  # No fallback or execution against the other DB.
        assert value(policy_engine) == "New"
    finally:
        other.dispose()


@pytest.mark.parametrize("after_write", [False, True])
@pytest.mark.parametrize("replacement", ["connection", "engine"])
def test_r6a_substitution_is_detected_at_successful_exit(policy_engine, after_write, replacement):
    other = create_engine(policy_engine.url)
    try:
        with policy_engine.connect() as external, Session(policy_engine) as db:
            foreign = external.begin()
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    if after_write:
                        change(db)
                    db.bind = external if replacement == "connection" else other
                    # No subsequent query: settlement itself must reject drift.
            assert_r4a_context_clean(db)
            assert foreign.is_active
            foreign.rollback()
        assert value(policy_engine) == "New"
    finally:
        other.dispose()


@pytest.mark.parametrize("route", ["execute", "connection_keyword", "connection_positional", "mapper", "table"])
def test_r6a_bind_overrides_cannot_bypass_first_acquisition(policy_engine, route):
    with policy_engine.connect() as external, Session(policy_engine) as db:
        foreign = external.begin()
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                if route == "execute":
                    db.execute(select(Lead.id), bind_arguments={"bind": external})
                elif route == "connection_keyword":
                    db.connection(bind_arguments={"bind": external})
                elif route == "connection_positional":
                    db.connection({"bind": external})
                else:
                    if route == "mapper":
                        db.bind_mapper(Lead, external)
                    else:
                        db.bind_table(Lead.__table__, external)
                    r6a_operation(db, "orm")
        assert_r4a_context_clean(db)
        assert foreign.is_active
        foreign.rollback()
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["tx@example.invalid"]


@pytest.mark.parametrize("external_state", ["idle", "begin", "nested", "autobegin"])
def test_r6a_initial_external_binding_remains_unsupported(policy_engine, external_state):
    with policy_engine.connect() as external:
        if external_state == "begin":
            external.begin()
        elif external_state == "nested":
            external.begin_nested()
        elif external_state == "autobegin":
            external.execute(select(Lead.id)).all()
        with Session(external) as db:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    pytest.fail("Initial external binding entered E02")
            assert_r4a_context_clean(db)
        external.rollback()


@pytest.mark.parametrize("replacement", ["connection", "root_transaction"])
def test_r6a_bound_identity_cannot_be_replaced(policy_engine, monkeypatch, replacement):
    with policy_engine.connect() as external, Session(policy_engine) as db:
        foreign = external.begin()
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)
                root = current_root(db)
                connection = db.connection()
                if replacement == "connection":
                    # Same Engine, different Connection must still be rejected.
                    root.bind(external)
                else:
                    # Keep the exact Connection while presenting a foreign root.
                    monkeypatch.setattr(connection, "get_transaction", lambda: foreign)
                    db.scalar(select(Lead.id))
        assert_r4a_context_clean(db)
        foreign.rollback()
    assert value(policy_engine) == "New"


def test_r6a_replaced_physical_root_cannot_reuse_authority(policy_engine):
    with Session(policy_engine) as db:
        replacement = None
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                change(db)
                root = current_root(db)
                connection = db.connection()
                previous = connection.get_transaction()
                # Fault injection beneath the public settlement guard: replace
                # the real SQLAlchemy transaction, retaining the Connection.
                with root.permit(Operation.ROOT_ROLLBACK, "connection_rollback"):
                    previous.rollback()
                replacement = connection.begin()
                assert replacement is not previous
                db.scalar(select(Lead.id))
        assert_r4a_context_clean(db)
        assert not replacement.is_active
    assert value(policy_engine) == "New"


@pytest.mark.parametrize("prior_read", [False, True])
@pytest.mark.parametrize("operation", ["empty", "read", "core", "orm", "savepoint"])
@pytest.mark.parametrize("outer_failure", [False, True])
def test_r6a_valid_acquisition_preserves_laziness_and_settlement(policy_engine, prior_read, operation, outer_failure):
    checkouts, begins = [], []
    original_get_bind = None

    def checkout(*args):
        checkouts.append(True)

    def executed(connection, cursor, statement, parameters, context, many):
        if statement == "BEGIN":
            begins.append(True)

    event.listen(policy_engine, "checkout", checkout)
    event.listen(policy_engine, "after_cursor_execute", executed)
    try:
        with Session(policy_engine) as db:
            original_get_bind = db.get_bind
            if prior_read:
                assert db.scalar(select(Lead.id)) == 1

            def operation_body():
                with tx(db):
                    root = current_root(db)
                    assert root.authority.engine is policy_engine
                    assert not root.physical and begins == []
                    if operation == "read":
                        db.scalar(select(Lead.id))
                    elif operation in {"core", "orm"}:
                        r6a_operation(db, "write" if operation == "core" else "orm")
                    elif operation == "savepoint":
                        with service_savepoint(db):
                            db.add(r5a_lead("r6a@example.invalid"))
                    if operation in {"empty", "read"}:
                        assert not root.physical and begins == []
                    else:
                        assert root.physical and len(begins) == 1
                    if operation == "empty" and not prior_read:
                        assert checkouts == [] and root.authority.connection is None
                    if outer_failure:
                        raise ValueError("Synthetic later E02 failure")

            if outer_failure:
                with pytest.raises(ValueError):
                    operation_body()
            else:
                operation_body()
            assert not db.in_transaction()
            assert db.get_bind == original_get_bind
            assert "get_bind" not in db.__dict__
            assert_r4a_context_clean(db)
    finally:
        event.remove(policy_engine, "checkout", checkout)
        event.remove(policy_engine, "after_cursor_execute", executed)
    with Session(policy_engine) as observer:
        expected = ["tx@example.invalid"]
        if not outer_failure and operation in {"core", "orm", "savepoint"}:
            expected.insert(0, "r6a@example.invalid")
        assert r5a_emails(observer) == expected


@pytest.mark.parametrize("prior_checkout", [False, True])
@pytest.mark.parametrize("external_active", [False, True])
@pytest.mark.parametrize("operation", ["read", "write"])
def test_r6a_actual_bind_rejects_foreign_settlement_provenance(policy_engine, prior_checkout, external_active, operation):
    with policy_engine.connect() as external, Session(policy_engine) as db:
        if external_active:
            external.begin()
        if prior_checkout:
            # A pre-E02 AUTOBEGIN alone does not prove Session ownership.
            Session.connection(db, bind_arguments={"bind": external})
        executed = []
        event.listen(external, "before_cursor_execute", lambda *args: executed.append(True))
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                # Exercise the actual after_begin acquisition fence beneath
                # the per-instance public method guard, on the same Engine.
                connection = Session.connection(db, bind_arguments={"bind": external})
                if operation == "read":
                    connection.execute(select(Lead.id))
                else:
                    r6a_operation(db, "write")
        assert executed == []
        assert_r4a_context_clean(db)
        external.rollback()
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["tx@example.invalid"]


@pytest.mark.parametrize("join_mode", ["conditional_savepoint", "rollback_only"])
def test_r6a_engine_checkout_cannot_join_an_existing_foreign_root(policy_engine, join_mode):
    connections = []

    def foreign_root(connection):
        connection.begin()
        connections.append(connection)

    event.listen(policy_engine, "engine_connect", foreign_root)
    try:
        with Session(policy_engine, join_transaction_mode=join_mode) as db:
            with pytest.raises(TransactionPolicyViolation):
                with tx(db):
                    r6a_operation(db, "write")
            assert_r4a_context_clean(db)
        assert len(connections) == 1 and connections[0].closed
    finally:
        event.remove(policy_engine, "engine_connect", foreign_root)
    with Session(policy_engine) as observer:
        assert r5a_emails(observer) == ["tx@example.invalid"]
