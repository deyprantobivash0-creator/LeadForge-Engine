"""G0E single-attempt knowledge, deadlines and explicit reconciliation."""

from dataclasses import FrozenInstanceError, replace
import sqlite3
import time

import pytest
from sqlalchemy import insert

from backend.database.rejection_storage import Attempt, DeadlineSQLite, attempt_scope, active_attempt
from backend.models import Lead
from backend.schemas.execution_principal import ExecutionPrincipal
from tests.test_lead_import_audit import seed_case, readback
from tests.test_rejection_recorder import (
    cleanup_rejection_storage, rejection_engine, recorder, record_denied, rejection,
)


@pytest.fixture(autouse=True)
def owned_pools(cleanup_rejection_storage):
    pass


def test_budget_is_single_monotonic_value_and_cleanup_uses_remainder():
    clock = [10.0]
    state = Attempt(clock=lambda: clock[0])
    assert state.remaining() == 3.0
    clock[0] += 1.0
    assert state.remaining() == 2.0
    clock[0] = 12.9
    assert state.remaining() == pytest.approx(.1)
    clock[0] = 13.0
    with pytest.raises(TimeoutError): state.remaining()
    assert state.remaining(cleanup=True) == 1.0
    clock[0] = 14.0
    with pytest.raises(TimeoutError): state.remaining(cleanup=True)


def test_expired_budget_does_not_start_a_session(rejection_engine, monkeypatch):
    from sqlalchemy import event
    from backend.services import rejection_recorder as module
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    clock = [0.0]
    state = Attempt(clock=lambda: clock[0])
    clock[0] = 5.0
    monkeypatch.setattr(module, "Attempt", lambda: state)
    monkeypatch.setattr(writer, "_persist", lambda *_: pytest.fail("Expired stage started storage"))
    event.listen(writer._storage.audit_bind, "checkout", lambda *_: pytest.fail("Expired checkout"))
    event.listen(writer._storage.audit_bind, "before_cursor_execute", lambda *_: pytest.fail("Expired query"))
    result = record_denied(rejection_engine, case, writer, work=False).result
    assert result.status == "NOT_RECORDED"
    assert readback(rejection_engine, case) == ([], [])


def test_acknowledged_result_and_sealed_material_are_immutable(rejection_engine):
    case = seed_case(rejection_engine)
    draft = rejection(case)
    result = record_denied(rejection_engine, case, recorder(rejection_engine), draft).result
    assert result.status == "RECORDED" and result.receipt.event_id == draft.event_id
    assert result.settlement.draft is draft
    with pytest.raises(FrozenInstanceError): result.status = "NOT_RECORDED"
    with pytest.raises(FrozenInstanceError): result.settlement.draft = None
    assert all(not isinstance(v, (dict, sqlite3.Connection)) for v in vars(result.settlement).values())


@pytest.mark.parametrize("committed", [False, True])
def test_ambiguous_commit_and_explicit_reconciliation(rejection_engine, monkeypatch, committed):
    from backend.repositories.audit_repository import AuditRepository
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    commit = DeadlineSQLite.commit
    attempts = []
    append = AuditRepository.append
    def observed(repo, draft):
        attempts.append(draft.event_id)
        return append(repo, draft)
    def lost(self):
        state = active_attempt()
        if committed: commit(self)
        state.commit_started = True
        state.acknowledged = False
        raise sqlite3.OperationalError("Synthetic lost acknowledgment")
    monkeypatch.setattr(AuditRepository, "append", observed)
    with monkeypatch.context() as patch:
        patch.setattr(DeadlineSQLite, "commit", lost)
        result = record_denied(rejection_engine, case, writer).result
    assert result.status == "OUTCOME_UNKNOWN" and result.receipt is None
    assert attempts == [result.settlement.draft.event_id]
    assert len(readback(rejection_engine, case)[1]) == int(committed)
    reconciled = writer.reconcile_rejection(result.settlement, case["principal"])
    assert reconciled.status == ("RECORDED" if committed else "OUTCOME_UNKNOWN")
    if committed: assert reconciled.receipt.event_id == result.settlement.draft.event_id
    assert attempts == [result.settlement.draft.event_id]  # Read never appends.


@pytest.mark.parametrize("context", ["foreign", "none", "dict"])
def test_invalid_reconciliation_context_never_becomes_a_write(rejection_engine, monkeypatch, context):
    from backend.repositories.audit_repository import AuditRepository
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    result = record_denied(rejection_engine, case, writer).result
    tenant = (ExecutionPrincipal.for_user(case["ids"]["user"], case["ids"]["foreign_org"])
              if context == "foreign" else {} if context == "dict" else None)
    monkeypatch.setattr(AuditRepository, "append", lambda *_: pytest.fail("Reconciliation inserted"))
    monkeypatch.setattr(AuditRepository, "_get_matching_event", lambda *_: pytest.fail("Foreign lookup"))
    reconciled = writer.reconcile_rejection(result.settlement, tenant)
    assert reconciled.status == "OUTCOME_UNKNOWN" and reconciled.receipt is None
    assert reconciled.settlement is None


def test_same_identity_replay_never_inserts_second_event(rejection_engine):
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    first = record_denied(rejection_engine, case, writer).result
    replay = writer.record_after_settlement(first.settlement)
    assert replay.status == "RECORDED" and replay.attempt_status is None
    assert writer.reconcile_rejection(first.settlement, case["principal"]).status == "RECORDED"
    assert len(readback(rejection_engine, case)[1]) == 1


def test_reconciliation_rejects_same_uuid_different_canonical_evidence(rejection_engine, monkeypatch):
    from datetime import timedelta
    from uuid import UUID
    from backend.services import audit_event_builder as builder
    from backend.services.application_audit import validate_rejection
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    first = record_denied(rejection_engine, case, writer).result.settlement.draft
    with monkeypatch.context() as patch:
        patch.setattr(builder, "uuid4", lambda: UUID(first.event_id))
        other = builder.AuditEventBuilder.permission_denied(first.principal, action=first.action,
            authorization=first.receipts, organization_id=first.principal.organization_id,
            occurred_at=first.occurred_at + timedelta(seconds=1))
    assert other.event_id == first.event_id
    validate_rejection(other)  # Valid seal: rejection must reach stored-content comparison.
    collision = record_denied(rejection_engine, case, writer, other).result
    assert collision.status == "OUTCOME_UNKNOWN"
    result = writer.reconcile_rejection(collision.settlement, case["principal"])
    assert result.status == "OUTCOME_UNKNOWN" and result.receipt is None
    assert len(readback(rejection_engine, case)[1]) == 1


def test_sqlite_busy_failure_returns_within_a35_and_pool_recovers(rejection_engine, record_property):
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    with rejection_engine.connect() as blocker:
        blocker.exec_driver_sql("BEGIN")
        blocker.execute(insert(Lead).values(organization_id=case["ids"]["org"],
            company="Lock fixture", email="lock@example.com", source="test"))
        started = time.monotonic()
        result = record_denied(rejection_engine, case, writer, work=False).result
        duration = time.monotonic() - started
        record_property("sqlite_busy_total_seconds", duration)
        assert duration <= 5.0
        assert result.status == "NOT_RECORDED"
        blocker.rollback()
    assert writer._storage.audit_bind.pool.checkedout() == 0
    assert readback(rejection_engine, case) == ([], [])
    assert record_denied(rejection_engine, case, writer, work=False).result.status == "RECORDED"


def test_r2_late_driver_wait_only_receives_remaining_budget(monkeypatch):
    from types import SimpleNamespace
    from backend.database import rejection_storage as module
    clock = [0.0]
    state = Attempt(clock=lambda: clock[0])
    observed = []
    def wait(gen, fd, **kwargs):
        observed.append(kwargs["timeout"])
    monkeypatch.setattr(module.waiting, "wait", wait)
    driver = SimpleNamespace(pgconn=SimpleNamespace(socket=0), close=lambda: None)
    with attempt_scope(state):
        clock[0] = 1.75
        module.DeadlineConnection.wait(driver, iter(()))
        clock[0] = 2.5
        module.DeadlineConnection.wait(driver, iter(()))
    assert observed == [1.25, .5]


def test_r2_sqlite_busy_at_commit_is_known_rollback(rejection_engine, monkeypatch, record_property):
    from backend.repositories.audit_repository import AuditRepository
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    append = AuditRepository.append
    flushed = []
    def observe(repo, draft):
        receipt = append(repo, draft)
        flushed.append(receipt.event_id)
        return receipt
    monkeypatch.setattr(AuditRepository, "append", observe)
    with rejection_engine.connect() as reader:
        reader.exec_driver_sql("BEGIN")
        reader.exec_driver_sql("SELECT count(*) FROM audit_events").scalar()
        started = time.monotonic()
        result = record_denied(rejection_engine, case, writer, work=False).result
        elapsed = time.monotonic() - started
        record_property("sqlite_commit_busy_seconds", elapsed)
        assert elapsed <= 5.0 and len(flushed) == 1  # Flush succeeded; COMMIT was blocked.
        assert result.status == "NOT_RECORDED"
        reader.rollback()
    assert readback(rejection_engine, case) == ([], [])
    assert writer._storage.audit_bind.pool.checkedout() == 0
    assert record_denied(rejection_engine, case, writer, work=False).result.status == "RECORDED"


def test_exhausted_recorder_pool_does_not_wait_or_change_business_pool(rejection_engine):
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    original_timeout = rejection_engine.pool.timeout()
    with attempt_scope(Attempt()), writer._storage.audit_bind.connect():
        started = time.monotonic()
        result = record_denied(rejection_engine, case, writer, work=False).result
        assert time.monotonic() - started <= 5.0
        assert result.status == "NOT_RECORDED"
        assert writer._storage.audit_bind.pool.checkedout() == 1
    assert writer._storage.audit_bind.pool.checkedout() == 0
    assert rejection_engine.pool.timeout() == original_timeout
    assert record_denied(rejection_engine, case, writer, work=False).result.status == "RECORDED"


def test_r1_sqlite_uri_read_only_and_type_conversion_are_preserved(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from sqlalchemy.exc import OperationalError
    from backend.database.rejection_storage import create_rejection_storage
    path = tmp_path / "canonical uri.db"
    with sqlite3.connect(path) as setup:
        setup.execute("CREATE TABLE marker (value INTEGER)")
        setup.execute("INSERT INTO marker VALUES (17)")
    monkeypatch.setitem(sqlite3.converters, "R1CONFIG", lambda value: int(value) + 1)
    url = URL.create("sqlite", database=path.as_uri(),
                     query={"mode": "ro", "cache": "shared", "uri": "true"})
    options = {"check_same_thread": False, "detect_types": sqlite3.PARSE_COLNAMES,
               "timeout": .015, "cached_statements": 37}
    before = dict(options)
    source = create_engine(url, connect_args=options)
    try:
        paired = create_rejection_storage(source, canonical_connect_args=options)
        assert paired.audit_bind.url == source.url == url
        for engine, scope in ((source, None), (paired.audit_bind, Attempt())):
            from contextlib import nullcontext
            with attempt_scope(scope) if scope else nullcontext():
                with engine.connect() as db:
                    assert db.exec_driver_sql('SELECT value AS "value [R1CONFIG]" FROM marker').scalar() == 18
                    with pytest.raises(OperationalError):
                        db.exec_driver_sql("INSERT INTO marker VALUES (19)")
        assert options == before
    finally:
        source.dispose()


def test_r1_shared_memory_uri_resolves_to_the_same_database():
    from uuid import uuid4
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from backend.database.rejection_storage import create_rejection_storage
    url = URL.create("sqlite", database="file:r1-" + uuid4().hex,
                     query={"mode": "memory", "cache": "shared", "uri": "true"})
    source = create_engine(url)
    try:
        paired = create_rejection_storage(source, canonical_connect_args={})
        with source.connect() as canonical:
            canonical.exec_driver_sql("CREATE TABLE marker (value INTEGER)")
            canonical.exec_driver_sql("INSERT INTO marker VALUES (23)")
            canonical.commit()
            with attempt_scope(Attempt()), paired.audit_bind.connect() as audit:
                assert audit.exec_driver_sql("SELECT value FROM marker").scalar() == 23
    finally:
        source.dispose()


@pytest.mark.parametrize("timeout", [0, .003, .05, 5])
def test_r1_sqlite_connect_args_merge_and_pool_immutability(tmp_path, monkeypatch, timeout):
    from sqlalchemy import create_engine
    from backend.database import rejection_storage as module
    options = {"timeout": timeout, "check_same_thread": False,
               "detect_types": sqlite3.PARSE_DECLTYPES, "cached_statements": 19,
               "isolation_level": "DEFERRED"}
    source = create_engine("sqlite:///" + (tmp_path / "parity.db").as_posix(),
                           connect_args=options, pool_timeout=11)
    original = dict(options)
    original_pool, original_url = source.pool, source.url
    args, expected = source.dialect.create_connect_args(source.url)
    expected.update(options)
    captured = []
    connect = sqlite3.connect
    def observed(*positional, **kwargs):
        captured.append((positional, dict(kwargs)))
        return connect(*positional, **kwargs)
    monkeypatch.setattr(module.sqlite3, "connect", observed)
    try:
        paired = module.create_rejection_storage(source, canonical_connect_args=options)
        assert source.pool is original_pool and source.url is original_url
        assert source.pool.timeout() == 11 and source.pool.checkedout() == 0
        with attempt_scope(Attempt()), paired.audit_bind.connect() as db:
            busy = db.exec_driver_sql("PRAGMA busy_timeout").scalar()
            assert busy <= timeout * 1000 and busy <= 50
        actual_args, actual = captured[0]
        assert actual_args == tuple(args)
        assert actual == {**expected, "timeout": 0, "factory": module.DeadlineSQLite}
        assert options == original
        assert source.pool.timeout() == 11 and source.pool.checkedout() == 0
    finally:
        source.dispose()


@pytest.mark.parametrize("with_hostaddr", [False, True])
@pytest.mark.parametrize("timeout", [0, 1, 8])
def test_r1_postgres_config_and_hostaddr_survive_timeout_overlay(monkeypatch, with_hostaddr, timeout):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    import psycopg
    from backend.database import rejection_storage as module
    query = {"sslmode": "require", "application_name": "url-name",
             "target_session_attrs": "read-write", "options": "-c lock_timeout=700"}
    if with_hostaddr: query["hostaddr"] = "192.0.2.10"
    url = URL.create("postgresql+psycopg", username="synthetic", password="synthetic p@ss:word/ %",
                     host="logical.invalid", port=55439, database="synthetic_db", query=query)
    options = {"connect_timeout": timeout, "sslmode": "verify-full",
               "application_name": "config-name", "sslrootcert": "synthetic-ca",
               "client_encoding": "UTF8", "options": "-c search_path=public -c statement_timeout=500"}
    original = dict(options)
    source = create_engine(url, connect_args=options, pool_timeout=13)
    pool = source.pool
    captured = {}
    class BeforeNetwork(Exception):
        pass
    def canonical_connect(*args, **kwargs):
        captured["canonical"] = (args, kwargs)
        raise BeforeNetwork
    def audit_connect(cls, *args, **kwargs):
        captured["audit"] = (args, kwargs)
        raise BeforeNetwork
    monkeypatch.setattr(psycopg, "connect", canonical_connect)
    monkeypatch.setattr(module.DeadlineConnection, "connect", classmethod(audit_connect))
    try:
        paired = module.create_rejection_storage(source, canonical_connect_args=options)
        with pytest.raises(BeforeNetwork): source.connect()
        with attempt_scope(Attempt()), pytest.raises(BeforeNetwork): paired.audit_bind.connect()
        base_args, base = captured["canonical"]
        audit_args, audit = captured["audit"]
        assert audit_args == base_args
        assert audit == {**base, "connect_timeout": min(timeout, 2) if timeout else 2}
        assert audit["host"] == "logical.invalid" and audit["port"] == 55439
        assert audit["password"] == url.password
        assert audit.get("hostaddr") == ("192.0.2.10" if with_hostaddr else None)
        assert ("hostaddr" in audit) == with_hostaddr  # No DNS-derived insertion.
        assert options == original and source.url is url and source.pool is pool
        assert source.pool.timeout() == 13 and source.pool.checkedout() == 0
    finally:
        source.dispose()


def test_r1_application_owner_mapping_is_used_without_engine_mutation(monkeypatch):
    from backend.database import session as canonical, rejection_storage as module
    original = dict(canonical.connect_args)
    pool, url = canonical.engine.pool, canonical.engine.url
    paired = module.create_rejection_storage(canonical.engine)
    assert paired.business_bind is canonical.engine and paired.audit_bind.url == url
    assert canonical.connect_args == original
    assert canonical.engine.pool is pool and canonical.engine.url is url
    from sqlalchemy import create_engine
    other = create_engine("sqlite:///unused-r1.db")
    try:
        with pytest.raises(ValueError, match="original canonical connect_args"):
            module.create_rejection_storage(other)
    finally:
        other.dispose()  # No connect/file creation.


@pytest.mark.parametrize("configured,expected", [
    (("250ms", "50ms"), ("250", "50")),
    (("1s", "0"), ("1000", "3000")),
    (("1min", "5s"), ("3000", "3000")),
])
def test_r1_pg_session_timeout_overlay_never_extends_canonical_limit(configured, expected):
    from types import SimpleNamespace
    from backend.database.rejection_storage import RejectionStorage
    class SettingsRead:
        def one(self): return configured
    class Database:
        def __init__(self): self.calls = []
        def execute(self, statement):
            self.calls.append(statement)
            return SettingsRead()
    db = Database()
    paired = RejectionStorage(None, SimpleNamespace(dialect=SimpleNamespace(name="postgresql")), None)
    with attempt_scope(Attempt(clock=lambda: 0.0)):
        paired.configure(db)
    params = db.calls[1].compile().params
    assert expected[0] in params.values() and expected[1] in params.values()


def _canonical_endpoint_connection(engine, host, address, port=55439):
    """Controlled live SQLAlchemy/Psycopg connection, without opening a socket."""
    from types import SimpleNamespace
    from unittest.mock import Mock
    import psycopg
    from sqlalchemy.engine import Connection
    connection = Mock(spec=Connection)
    connection.engine, connection.closed, connection.invalidated = engine, False, False
    native = Mock(spec=psycopg.Connection)
    native.closed = False
    native.info = SimpleNamespace(host=host, hostaddr=address, port=port)
    connection.connection.driver_connection = native
    return connection


@pytest.mark.parametrize("configured", [False, True])
def test_r3_trusted_endpoint_preserves_hostname_tls_and_original_configuration(monkeypatch, configured):
    import socket
    import psycopg
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from backend.database.rejection_storage import create_rejection_storage
    query = {"application_name": "endpoint-test"}
    if configured: query["hostaddr"] = "192.0.2.10"
    source = create_engine(URL.create("postgresql+psycopg", host="secure-db.example.test",
                           port=55439, database="synthetic", query=query))
    args = {"sslmode": "verify-full", "sslrootcert": "synthetic-ca", "connect_timeout": 8}
    before, pool, url = dict(args), source.pool, source.url
    canonical = _canonical_endpoint_connection(source, "secure-db.example.test", "192.0.2.11")
    captured = []
    class BeforeNetwork(Exception): pass
    def connect(cls, *positional, **options):
        captured.append((positional, options))
        raise BeforeNetwork
    monkeypatch.setattr(psycopg.Connection, "connect", classmethod(connect))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: pytest.fail("Recorder DNS"))
    try:
        paired = create_rejection_storage(source, canonical_connect_args=args,
                                           canonical_connections=(canonical,))
        # The endpoint is a scalar snapshot, not a retained live connection.
        canonical.closed = True
        with attempt_scope(Attempt()), pytest.raises(BeforeNetwork): paired.audit_bind.connect()
        actual = captured[0][1]
        assert actual["host"] == "secure-db.example.test"
        assert actual["hostaddr"] == ("192.0.2.10" if configured else "192.0.2.11")
        assert actual["port"] == 55439 and actual["sslmode"] == "verify-full"
        assert actual["sslrootcert"] == "synthetic-ca" and actual["application_name"] == "endpoint-test"
        assert args == before and source.pool is pool and source.url is url
        assert source.pool.checkedout() == 0
    finally: source.dispose()


@pytest.mark.parametrize("fault", ["foreign", "closed", "invalidated", "native_closed", "arbitrary"])
def test_r3_endpoint_provenance_rejects_untrusted_or_unavailable_connections(fault):
    from sqlalchemy import create_engine
    from backend.database.rejection_storage import create_rejection_storage
    source = create_engine("postgresql+psycopg://canonical.example.test:55439/synthetic")
    other = create_engine("postgresql+psycopg://other.example.test:55439/synthetic")
    canonical = _canonical_endpoint_connection(source, "canonical.example.test", "192.0.2.10")
    if fault == "foreign": canonical.engine = other
    elif fault == "closed": canonical.closed = True
    elif fault == "invalidated": canonical.invalidated = True
    elif fault == "native_closed": canonical.connection.driver_connection.closed = True
    else: canonical = {"hostaddr": "192.0.2.10"}
    try:
        with pytest.raises(ValueError, match="canonical"):
            create_rejection_storage(source, canonical_connect_args={}, canonical_connections=(canonical,))
        assert source.pool.checkedout() == other.pool.checkedout() == 0
    finally: source.dispose();other.dispose()


@pytest.mark.parametrize("configured", [False, True])
def test_r3_multihost_preserves_corresponding_order_and_ports(monkeypatch, configured):
    import psycopg
    from sqlalchemy import create_engine
    from backend.database.rejection_storage import create_rejection_storage
    options = {"host": "one.example.test,two.example.test", "port": "55439,55440",
               "sslmode": "verify-full"}
    if configured: options["hostaddr"] = "192.0.2.10,192.0.2.11"
    before = dict(options)
    source = create_engine("postgresql+psycopg:///synthetic", connect_args=options)
    canonical = (_canonical_endpoint_connection(source, "two.example.test", "192.0.2.11", 55440),
                 _canonical_endpoint_connection(source, "one.example.test", "192.0.2.10"))
    captured = []
    class BeforeNetwork(Exception): pass
    def connect(cls, *args, **kwargs): captured.append(kwargs);raise BeforeNetwork
    monkeypatch.setattr(psycopg.Connection, "connect", classmethod(connect))
    try:
        paired = create_rejection_storage(source, canonical_connect_args=options, canonical_connections=canonical)
        with attempt_scope(Attempt()), pytest.raises(BeforeNetwork): paired.audit_bind.connect()
        assert captured[0]["host"] == before["host"]
        assert captured[0]["port"] == before["port"]
        assert captured[0]["hostaddr"] == "192.0.2.10,192.0.2.11"
        assert captured[0]["sslmode"] == "verify-full" and options == before
    finally: source.dispose()


@pytest.mark.parametrize("options", [
    {"host": "unresolved.example.test"},
    {"host": "one.example.test,two.example.test", "hostaddr": "192.0.2.10,"},
    {"host": "one.example.test,two.example.test", "hostaddr": "192.0.2.10"},
    {"host": "one.example.test", "hostaddr": "not-numeric.example.test"},
    {"host": "one.example.test", "hostaddr": "192.0.2.10", "port": "1,2"},
    {"host": "@abstract-socket"},  # Installed Psycopg would otherwise resolve it.
])
def test_r3_unavailable_or_incomplete_endpoint_fails_before_driver_dns(monkeypatch, options):
    import socket
    import psycopg
    from backend.database.rejection_storage import DeadlineConnection, RejectionDeadlineExceeded
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: pytest.fail("Recorder DNS"))
    monkeypatch.setattr(psycopg.Connection, "connect", lambda *_a, **_k: pytest.fail("Unready endpoint connected"))
    with attempt_scope(Attempt()), pytest.raises(RejectionDeadlineExceeded, match="pre-resolved"):
        DeadlineConnection.connect(**options)


@pytest.mark.parametrize("host", ["/var/run/postgresql", "C:/canonical-socket"])
def test_r3_explicit_socket_keeps_canonical_behavior_without_hostaddr(monkeypatch, host):
    import socket
    import psycopg
    from psycopg._conninfo_attempts import conninfo_attempts
    from sqlalchemy import create_engine
    from backend.database.rejection_storage import create_rejection_storage
    source = create_engine("postgresql+psycopg:///synthetic")
    captured = []
    class BeforeNetwork(Exception): pass
    def connect(cls, *args, **kwargs): captured.append(kwargs);raise BeforeNetwork
    monkeypatch.setattr(psycopg.Connection, "connect", classmethod(connect))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: pytest.fail("Socket DNS"))
    try:
        paired = create_rejection_storage(source, canonical_connect_args={"host": host})
        with attempt_scope(Attempt()), pytest.raises(BeforeNetwork): paired.audit_bind.connect()
        assert captured[0]["host"] == host and "hostaddr" not in captured[0]
        assert conninfo_attempts({"host": host}) == [{"host": host}]
    finally: source.dispose()


def test_r3_later_native_connection_attempt_cannot_restart_budget(monkeypatch):
    import psycopg
    from backend.database.rejection_storage import DeadlineConnection, RejectionDeadlineExceeded
    calls = []
    def native(cls, conninfo):
        calls.append(conninfo)
        yield "native-attempt"
    monkeypatch.setattr(psycopg.Connection, "_connect_gen", classmethod(native))
    clock = [0.0]
    with attempt_scope(Attempt(clock=lambda: clock[0])):
        first = DeadlineConnection._connect_gen("first")
        assert next(first) == "native-attempt"
        first.close()
        clock[0] = 2.0
        with pytest.raises(RejectionDeadlineExceeded): next(DeadlineConnection._connect_gen("second"))
    assert calls == ["first"]


def test_r3_endpoint_initialization_cannot_run_inside_recorder_attempt(rejection_engine):
    from backend.database.rejection_storage import create_rejection_storage
    with attempt_scope(Attempt()), pytest.raises(ValueError, match="outside recorder calls"):
        create_rejection_storage(rejection_engine, canonical_connect_args={})


def _g0i_unknown(engine, monkeypatch, committed):
    case = seed_case(engine)
    writer = recorder(engine)
    commit = DeadlineSQLite.commit
    def lost(connection):
        state = active_attempt()
        if committed: commit(connection)
        state.commit_started, state.acknowledged = True, False
        raise sqlite3.OperationalError("Synthetic unacknowledged COMMIT")
    with monkeypatch.context() as patch:
        patch.setattr(DeadlineSQLite, "commit", lost)
        result = record_denied(engine, case, writer, work=False).result
    assert result.status == result.attempt_status == "OUTCOME_UNKNOWN"
    assert len(readback(engine, case)[1]) == int(committed)
    return case, writer, result


def _g0i_failed_replay(writer, record, fault, monkeypatch):
    from backend.services import rejection_recorder as module
    from backend.repositories.audit_repository import AuditRepository
    with monkeypatch.context() as patch:
        patch.setattr(AuditRepository, "_get_matching_event", lambda *_: pytest.fail("Implicit reconciliation"))
        if fault == "pool":
            with attempt_scope(Attempt()), writer._storage.audit_bind.connect():
                return writer.record_after_settlement(record)
        if fault == "connection":
            writer._storage.audit_bind.dispose()
            def unavailable(*_): raise sqlite3.OperationalError("Synthetic connection unavailable")
            patch.setattr(writer._storage.audit_bind.pool, "_invoke_creator", unavailable)
        else:
            state = Attempt(clock=lambda: 0.0)
            state.clock = lambda: 5.0
            patch.setattr(module, "Attempt", lambda: state)
            patch.setattr(writer, "_persist", lambda *_: pytest.fail("Expired replay touched storage"))
        return writer.record_after_settlement(record)


@pytest.mark.parametrize("committed", [False, True])
@pytest.mark.parametrize("fault", ["pool", "connection", "expired"])
def test_g0i_unknown_event_survives_later_attempt_failure(rejection_engine, monkeypatch, committed, fault):
    case, writer, first = _g0i_unknown(rejection_engine, monkeypatch, committed)
    started = time.monotonic()
    result = _g0i_failed_replay(writer, first.settlement, fault, monkeypatch)
    assert time.monotonic() - started <= 5.0
    assert result.attempt_status == "NOT_RECORDED"  # THIS invocation did not persist.
    assert result.status == "OUTCOME_UNKNOWN"  # The logical EVENT is unresolved.
    assert result.settlement is first.settlement and result.settlement.draft is first.settlement.draft
    assert result.receipt is None and writer._storage.audit_bind.pool.checkedout() == 0
    assert len(readback(rejection_engine, case)[1]) == int(committed)
    found = writer.reconcile_rejection(first.settlement, case["principal"])
    assert found.status == ("RECORDED" if committed else "OUTCOME_UNKNOWN")
    assert len(readback(rejection_engine, case)[1]) == int(committed)


@pytest.mark.parametrize("origin", ["commit", "reconciliation"])
@pytest.mark.parametrize("fault", ["pool", "connection", "expired"])
def test_g0i_recorded_is_absorbing_without_new_io(rejection_engine, monkeypatch, origin, fault):
    if origin == "reconciliation":
        case, writer, first = _g0i_unknown(rejection_engine, monkeypatch, True)
        confirmed = writer.reconcile_rejection(first.settlement, case["principal"])
    else:
        case = seed_case(rejection_engine)
        writer = recorder(rejection_engine)
        first = confirmed = record_denied(rejection_engine, case, writer, work=False).result
    assert confirmed.status == "RECORDED"
    monkeypatch.setattr(writer, "_persist", lambda *_: pytest.fail("Known durability retried storage"))
    result = _g0i_failed_replay(writer, first.settlement, fault, monkeypatch)
    assert result.status == "RECORDED" and result.receipt == confirmed.receipt
    assert result.attempt_status is None
    assert len(readback(rejection_engine, case)[1]) == 1


def test_g0i_replay_ack_does_not_implicitly_resolve_unknown(rejection_engine, monkeypatch):
    from backend.repositories.audit_repository import AuditRepository
    case, writer, first = _g0i_unknown(rejection_engine, monkeypatch, False)
    with monkeypatch.context() as patch:
        patch.setattr(AuditRepository, "_get_matching_event", lambda *_: pytest.fail("Replay performed SELECT reconciliation"))
        replay = writer.record_after_settlement(first.settlement)
    assert replay.attempt_status == "RECORDED"  # ACK for this explicit attempt.
    assert replay.status == "OUTCOME_UNKNOWN" and replay.receipt is None
    rows = readback(rejection_engine, case)[1]
    assert len(rows) == 1 and rows[0].event_id == first.settlement.draft.event_id
    assert writer.reconcile_rejection(first.settlement, case["principal"]).status == "RECORDED"


@pytest.mark.parametrize("next_outcome", ["not_recorded", "unknown", "recorded"])
def test_g0i_fresh_nonpersistence_can_progress(rejection_engine, monkeypatch, next_outcome):
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    with attempt_scope(Attempt()), writer._storage.audit_bind.connect():
        first = record_denied(rejection_engine, case, writer, work=False).result
    assert first.status == first.attempt_status == "NOT_RECORDED"
    if next_outcome == "not_recorded":
        later = _g0i_failed_replay(writer, first.settlement, "pool", monkeypatch)
        assert later.status == later.attempt_status == "NOT_RECORDED"
        assert readback(rejection_engine, case) == ([], [])
        return
    if next_outcome == "unknown":
        commit = DeadlineSQLite.commit
        def lost(connection):
            commit(connection)
            active_attempt().acknowledged = False
            raise sqlite3.OperationalError("Synthetic lost ACK")
        with monkeypatch.context() as patch:
            patch.setattr(DeadlineSQLite, "commit", lost)
            later = writer.record_after_settlement(first.settlement)
        assert later.status == "OUTCOME_UNKNOWN"
    else:
        assert writer.record_after_settlement(first.settlement).status == "RECORDED"
    assert len(readback(rejection_engine, case)[1]) == 1


@pytest.mark.parametrize("prior", ["unknown", "recorded"])
def test_g0i_tenant_identity_and_wrong_tenant_privacy(rejection_engine, monkeypatch, prior):
    from backend.services import audit_event_builder as builder
    from uuid import UUID
    case, writer, first = _g0i_unknown(rejection_engine, monkeypatch, prior == "recorded")
    if prior == "recorded": writer.reconcile_rejection(first.settlement, case["principal"])
    foreign = ExecutionPrincipal.for_user(case["ids"]["user"], case["ids"]["foreign_org"])
    hidden = writer.reconcile_rejection(first.settlement, foreign)
    assert hidden.status == "OUTCOME_UNKNOWN" and hidden.receipt is hidden.settlement is None
    foreign_case = {**case, "principal": foreign}
    with monkeypatch.context() as patch:
        patch.setattr(builder, "uuid4", lambda: UUID(first.settlement.draft.event_id))
        foreign_draft = rejection(foreign_case)
    with attempt_scope(Attempt()), writer._storage.audit_bind.connect():
        other = record_denied(rejection_engine, foreign_case, writer, foreign_draft, work=False).result
    assert other.status == other.attempt_status == "NOT_RECORDED"
    assert other.settlement._knowledge is not first.settlement._knowledge
    assert writer.record_after_settlement(first.settlement).status == ("RECORDED" if prior == "recorded" else "OUTCOME_UNKNOWN")


def test_g0i_same_uuid_different_sealed_content_cannot_adopt_known_receipt(rejection_engine, monkeypatch):
    from datetime import timedelta
    from uuid import UUID
    from backend.services import audit_event_builder as builder
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    first = record_denied(rejection_engine, case, writer, work=False).result
    draft = first.settlement.draft
    with monkeypatch.context() as patch:
        patch.setattr(builder, "uuid4", lambda: UUID(draft.event_id))
        different = builder.AuditEventBuilder.permission_denied(draft.principal, action=draft.action,
            authorization=draft.receipts, organization_id=draft.principal.organization_id,
            occurred_at=draft.occurred_at + timedelta(seconds=1))
    collision = record_denied(rejection_engine, case, writer, different, work=False).result
    assert collision.status == "OUTCOME_UNKNOWN" and collision.receipt is None
    assert collision.settlement._knowledge is not first.settlement._knowledge
    assert writer.reconcile_rejection(collision.settlement, case["principal"]).status == "OUTCOME_UNKNOWN"
    assert writer.record_after_settlement(first.settlement).status == "RECORDED"
    assert len(readback(rejection_engine, case)[1]) == 1


def test_g0i_live_draft_aliases_keep_same_event_evidence(rejection_engine, monkeypatch):
    import gc
    case, writer, first = _g0i_unknown(rejection_engine, monkeypatch, False)
    draft = first.settlement.draft
    knowledge = first.settlement._knowledge
    del first
    gc.collect()
    # A new valid settlement for identical sealed content must share knowledge.
    alias = replace(draft)
    with attempt_scope(Attempt()), writer._storage.audit_bind.connect():
        later = record_denied(rejection_engine, case, writer, alias, work=False).result
    assert later.settlement._knowledge is knowledge
    assert later.status == "OUTCOME_UNKNOWN" and later.attempt_status == "NOT_RECORDED"
    assert readback(rejection_engine, case) == ([], [])


def test_g0i_knowledge_is_handle_lifetime_and_not_cross_recorder_authority(rejection_engine, monkeypatch):
    import gc
    from weakref import ref
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    draft = rejection(case)
    knowledge = writer._new_event_knowledge(draft)
    weak = ref(knowledge)
    del knowledge
    assert weak() is not None  # A retained sealed draft preserves evidence.
    del draft
    gc.collect()
    assert weak() is None and len(writer._event_knowledge) == len(writer._draft_knowledge) == 0
    first = record_denied(rejection_engine, case, writer, work=False).result
    other = recorder(rejection_engine)
    monkeypatch.setattr(other, "_persist", lambda *_: pytest.fail("Foreign owner touched storage"))
    rejected = other.record_after_settlement(first.settlement)
    assert rejected.status == "NOT_RECORDED" and rejected.settlement is rejected.receipt is None
    tampered = replace(first.settlement, _knowledge=object())
    assert writer.record_after_settlement(tampered).settlement is None
    assert writer.record_after_settlement(first.settlement).status == "RECORDED"


def test_g0i_same_event_contention_never_waits_or_retries(rejection_engine, monkeypatch):
    case, writer, first = _g0i_unknown(rejection_engine, monkeypatch, True)
    cell = first.settlement._knowledge
    cell.operation.acquire()
    try:
        monkeypatch.setattr(writer, "_persist", lambda *_: pytest.fail("Overlapping event performed I/O"))
        started = time.monotonic()
        result = writer.record_after_settlement(first.settlement)
        assert time.monotonic() - started < 1.0
        assert result.status == "OUTCOME_UNKNOWN" and result.attempt_status is None
    finally: cell.operation.release()


@pytest.mark.parametrize("prior", ["fresh", "unknown"])
def test_g0i_settlement_binding_contention_is_fail_fast(rejection_engine, monkeypatch, prior):
    if prior == "unknown":
        case, writer, first = _g0i_unknown(rejection_engine, monkeypatch, False)
        draft = first.settlement.draft
    else:
        case = seed_case(rejection_engine)
        writer = recorder(rejection_engine)
        draft = rejection(case)
    writer._knowledge_mint_lock.acquire()
    try:
        started = time.monotonic()
        operation = record_denied(rejection_engine, case, writer, draft, work=False)
        assert time.monotonic() - started < 1.0
        assert operation.result is operation.receipt is None
        assert readback(rejection_engine, case) == ([], [])
    finally: writer._knowledge_mint_lock.release()
    if prior == "unknown":
        assert _g0i_failed_replay(writer, first.settlement, "expired", monkeypatch).status == "OUTCOME_UNKNOWN"
