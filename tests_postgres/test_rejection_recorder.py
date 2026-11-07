"""Real PG rejection durability and independent-root/resource behavior."""

import pytest
import socket
import struct
import threading
import time
from sqlalchemy import create_engine, event

from tests.test_rejection_recorder import (
    cleanup_rejection_storage,
    recorder, record_denied, rejection,
    test_durable_rejection_after_business_rollback_exact_payload as exact_case,
    test_audit_failure_preserves_original_denial_and_business_rollback as failure_case,
    test_caught_nested_denial_records_once_after_rollback_only_root as nested_case,
    test_no_sql_denial_can_record_only_after_scope_exit as no_sql_case,
    test_poisoned_business_session_is_not_touched_by_fresh_recorder as poisoned_case,
    test_only_canonical_private_safe_rejection_input_is_accepted as input_case,
    test_root_permits_cannot_cross_and_ambient_authority_is_discarded as isolation_case,
    test_frozen_settlement_replay_is_not_retried_or_duplicated as replay_case,
    test_existing_read_autobegin_is_settled_before_recording as read_case,
)
from tests.test_lead_import_audit import seed_case, readback


@pytest.fixture(autouse=True)
def owned_recorder_pools(cleanup_rejection_storage):
    pass


@pytest.fixture
def rejection_engine(pg_database):
    connect_args = {
        "connect_timeout": 3, "options": "-c lock_timeout=5000 -c statement_timeout=8000",
    }
    engine = create_engine(pg_database["url"], connect_args=connect_args, pool_timeout=3)
    engine._test_rejection_connect_args = connect_args
    try:
        yield engine
    finally:
        engine.dispose()


def test_postgres_distinct_session_root_and_durable_rejection(rejection_engine, monkeypatch):
    exact_case(rejection_engine, monkeypatch, "USER")


@pytest.mark.parametrize("failure", ["append", "constraint", "commit", "close"])
def test_postgres_audit_failure_cannot_change_business_denial(rejection_engine, monkeypatch, failure):
    failure_case(rejection_engine, monkeypatch, failure)


def test_postgres_caught_nested_denial_persists_after_outer_rollback(rejection_engine):
    nested_case(rejection_engine)


def test_postgres_no_sql_denial(rejection_engine):
    no_sql_case(rejection_engine)


def test_postgres_failed_business_session_isolation(rejection_engine, monkeypatch):
    poisoned_case(rejection_engine, monkeypatch)


def test_postgres_tenant_rejection_excludes_foreign_target(rejection_engine):
    input_case(rejection_engine, "tenant")


@pytest.mark.parametrize("direction", ["ambient", "business_to_audit", "audit_to_business"])
def test_postgres_root_authority_cannot_cross(rejection_engine, monkeypatch, direction):
    isolation_case(rejection_engine, monkeypatch, direction)


def test_postgres_replay_cannot_duplicate_event(rejection_engine, monkeypatch):
    replay_case(rejection_engine, monkeypatch)


def test_postgres_authorization_read_autobegin(rejection_engine):
    read_case(rejection_engine)


def _timed_denial(engine, case, writer, monkeypatch, record_property, label, draft=None):
    original = writer.record_after_settlement
    measured = []
    def timed(record):
        start = time.monotonic()
        result = original(record)
        measured.append(time.monotonic() - start)
        return result
    with monkeypatch.context() as patch:
        patch.setattr(writer, "record_after_settlement", timed)
        result = record_denied(engine, case, writer, draft, work=False).result
    assert len(measured) == 1 and measured[0] <= 5.0  # No measurement allowance.
    record_property(label + "_seconds", measured[0])
    record_property(label + "_status", result.status)
    return result


def _disposition(engine, pids):
    assert pids
    with engine.connect() as observer:
        for pid in pids:
            row = observer.exec_driver_sql(
                "SELECT state, xact_start FROM pg_stat_activity WHERE pid = %s", (pid,)).one_or_none()
            assert row is None or (row[0] == "idle" and row[1] is None), row


def test_r2_postgres_pool_exhaustion_and_recovery(rejection_engine, monkeypatch, record_property):
    from backend.database.rejection_storage import Attempt, attempt_scope
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    with attempt_scope(Attempt()), writer._storage.audit_bind.connect():
        result = _timed_denial(rejection_engine, case, writer, monkeypatch, record_property, "pool")
        assert result.status == "NOT_RECORDED"
        assert writer._storage.audit_bind.pool.checkedout() == 1
    assert writer._storage.audit_bind.pool.checkedout() == 0
    assert readback(rejection_engine, case) == ([], [])
    healthy = _timed_denial(rejection_engine, case, writer, monkeypatch, record_property, "pool_recovery")
    assert healthy.status == "RECORDED" and len(readback(rejection_engine, case)[1]) == 1


@pytest.mark.parametrize("partial_delay", [0, 1.0])
def test_r2_postgres_real_lock_shared_budget_and_recovery(
        rejection_engine, monkeypatch, record_property, partial_delay):
    from backend.repositories.audit_repository import AuditRepository
    case = seed_case(rejection_engine)
    writer = recorder(rejection_engine)
    # Prewarm outside the measured call so the partial-budget case tests a late
    # flush, not the deliberate minimum-connect-budget rejection.
    from backend.database.rejection_storage import Attempt, attempt_scope
    with attempt_scope(Attempt()), writer._storage.audit_bind.connect(): pass
    audit_pids = []
    with attempt_scope(Attempt()), writer._storage.audit_bind.connect() as probe:
        audit_pids.append(probe.exec_driver_sql("SELECT pg_backend_pid()").scalar())
    append = AuditRepository.append
    calls = []
    budgets = []
    def delayed(repo, draft):
        from backend.database.rejection_storage import active_attempt
        calls.append(draft.event_id)
        before = active_attempt().remaining()
        if partial_delay: time.sleep(partial_delay)  # Controlled test-only stage cost.
        budgets.append((before, active_attempt().remaining()))
        return append(repo, draft)
    monkeypatch.setattr(AuditRepository, "append", delayed)
    stop, seen = threading.Event(), threading.Event()
    evidence, failures = [], []
    with rejection_engine.connect() as blocker:
        blocker_pid = blocker.exec_driver_sql("SELECT pg_backend_pid()").scalar()
        blocker.exec_driver_sql("LOCK TABLE audit_events IN ACCESS EXCLUSIVE MODE")
        def observe():
            try:
                with rejection_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
                    while not stop.is_set():
                        rows = db.exec_driver_sql(
                            "SELECT pid, pg_blocking_pids(pid), wait_event_type FROM pg_stat_activity "
                            "WHERE datname = current_database() AND %s = ANY(pg_blocking_pids(pid))",
                            (blocker_pid,)).all()
                        if rows:
                            evidence.extend(rows);seen.set();return
                        stop.wait(.01)
            except BaseException as exc: failures.append(type(exc).__name__)
        monitor = threading.Thread(target=observe)
        monitor.start()
        started = time.monotonic()
        try:
            result = _timed_denial(rejection_engine, case, writer, monkeypatch, record_property, "lock")
            assert result.status == "NOT_RECORDED"
            assert seen.is_set() and not failures
            if partial_delay:
                assert budgets[0][1] <= budgets[0][0] - .9
            record_property("flush_remaining_seconds", budgets[0][1])
            assert evidence[0][0] != blocker_pid and blocker_pid in evidence[0][1]
            record_property("blocking_pids", str(evidence[0][1]))
            record_property("blocked_pid", evidence[0][0])
            _disposition(rejection_engine, audit_pids)
            assert writer._storage.audit_bind.pool.checkedout() == 0
            # Beyond the original production deadline, no deferred automatic insert.
            time.sleep(max(0.0, started + 5.1 - time.monotonic()))
            assert calls == [result.settlement.draft.event_id]
        finally:
            stop.set();monitor.join(2)
            assert not monitor.is_alive()
            blocker.rollback()
    assert readback(rejection_engine, case) == ([], [])
    healthy = _timed_denial(rejection_engine, case, writer, monkeypatch, record_property, "lock_recovery")
    assert healthy.status == "RECORDED" and len(readback(rejection_engine, case)[1]) == 1


class _CommitProxy:
    """Test-only plaintext PG message relay; deterministic COMMIT fault.

    'committed' forwards COMMIT but withholds its response. 'absent' suppresses
    COMMIT before the server. All sockets/threads are closed/joined in close().
    This is never application recorder infrastructure.
    """
    def __init__(self, url, mode="pass"):
        self.target = (url.host, url.port)
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.url = url.set(host="127.0.0.1", port=self.listener.getsockname()[1]).update_query_dict({"sslmode": "disable"})
        self.mode = mode
        self.stop = threading.Event()
        self.faulted = threading.Event()
        self.lock = threading.Lock()
        self.sockets, self.workers = [], []
        self.acceptor = None

    def _receive(self, conn, size):
        value = b""
        while len(value) < size and not self.stop.is_set():
            try: data = conn.recv(size - len(value))
            except socket.timeout: continue
            except OSError: return None
            if not data: return None
            value += data
        return value if len(value) == size else None

    def start(self):
        self.listener.listen()
        self.listener.settimeout(.1)
        self.acceptor = threading.Thread(target=self._accept)
        self.acceptor.start()
        return self

    def _accept(self):
        while not self.stop.is_set():
            try: client, _ = self.listener.accept()
            except socket.timeout: continue
            except OSError: return
            client.settimeout(.1)
            worker = threading.Thread(target=self._serve, args=(client,))
            with self.lock:
                self.sockets.append(client);self.workers.append(worker)
            worker.start()

    def _serve(self, client):
        backend, relay = None, None
        hold_reply = threading.Event()
        try:
            backend = socket.create_connection(self.target, timeout=2)
            backend.settimeout(.1)
            with self.lock: self.sockets.append(backend)
            length = self._receive(client, 4)
            if length is None: return
            payload = self._receive(client, struct.unpack("!I", length)[0] - 4)
            if payload is None: return
            backend.sendall(length + payload)  # Startup or cancellation packet.
            def server_replies():
                while not self.stop.is_set():
                    try: data = backend.recv(65536)
                    except socket.timeout: continue
                    except OSError: return
                    if not data: return
                    if not hold_reply.is_set():
                        try: client.sendall(data)
                        except OSError: return
            relay = threading.Thread(target=server_replies)
            relay.start()
            while not self.stop.is_set():
                tag = self._receive(client, 1)
                if tag is None: return
                length = self._receive(client, 4)
                if length is None: return
                payload = self._receive(client, struct.unpack("!I", length)[0] - 4)
                if payload is None: return
                is_commit = tag == b"Q" and payload.rstrip(b"\x00").strip().upper() == b"COMMIT"
                if is_commit and self.mode != "pass":
                    hold_reply.set();self.faulted.set()
                    if self.mode == "absent": continue
                backend.sendall(tag + length + payload)
                if tag == b"X": return
        except OSError:
            pass  # Expected controlled disconnect; never print protocol/auth data.
        finally:
            for conn in (backend, client):
                if conn is not None:
                    try: conn.shutdown(socket.SHUT_RDWR)
                    except OSError: pass
                    conn.close()
            if relay is not None:
                relay.join(2)
                assert not relay.is_alive()

    def close(self):
        self.stop.set();self.listener.close()
        if self.acceptor is not None:
            self.acceptor.join(2);assert not self.acceptor.is_alive()
        with self.lock: sockets, workers = list(self.sockets), list(self.workers)
        for conn in sockets:
            try: conn.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            conn.close()
        for worker in workers:
            worker.join(3);assert not worker.is_alive()


def _proxy_source(engine, proxy):
    options = dict(engine._test_rejection_connect_args)
    source = create_engine(proxy.url, connect_args=options)
    source._test_rejection_connect_args = options
    return source


def test_r2_postgres_connection_refusal_and_recovery(rejection_engine, monkeypatch, record_property):
    case = seed_case(rejection_engine)
    proxy = _CommitProxy(rejection_engine.url)  # Bound, deliberately not listening.
    source = _proxy_source(rejection_engine, proxy)
    writer = recorder(source)
    try:
        result = _timed_denial(source, case, writer, monkeypatch, record_property, "connect_refusal")
        assert result.status == "NOT_RECORDED" and readback(rejection_engine, case) == ([], [])
        assert writer._storage.audit_bind.pool.checkedout() == 0
        proxy.start()
        healthy = _timed_denial(source, case, writer, monkeypatch, record_property, "connect_recovery")
        assert healthy.status == "RECORDED" and len(readback(rejection_engine, case)[1]) == 1
    finally:
        writer.close();source.dispose();proxy.close()


@pytest.mark.parametrize("committed", [False, True])
def test_r2_postgres_stalled_commit_reconciliation_and_explicit_replay(
        rejection_engine, monkeypatch, record_property, committed):
    from backend.repositories.audit_repository import AuditRepository
    from backend.schemas.execution_principal import ExecutionPrincipal
    case = seed_case(rejection_engine)
    proxy = _CommitProxy(rejection_engine.url, "committed" if committed else "absent").start()
    source = _proxy_source(rejection_engine, proxy)
    writer = recorder(source)
    append = AuditRepository.append
    attempts = []
    def observed(repo, draft):
        attempts.append(draft.event_id)
        return append(repo, draft)
    monkeypatch.setattr(AuditRepository, "append", observed)
    try:
        result = _timed_denial(source, case, writer, monkeypatch, record_property, "lost_commit_ack")
        assert proxy.faulted.is_set() and result.status == "OUTCOME_UNKNOWN"
        draft = result.settlement.draft
        assert attempts == [draft.event_id]
        assert writer._storage.audit_bind.pool.checkedout() == 0
        leads, rows = readback(rejection_engine, case)
        assert leads == [] and len(rows) == int(committed)
        proxy.mode = "pass"
        wrong = ExecutionPrincipal.for_user(case["ids"]["user"], case["ids"]["foreign_org"])
        foreign = writer.reconcile_rejection(result.settlement, wrong)
        assert foreign.status == "OUTCOME_UNKNOWN" and foreign.receipt is None
        found = writer.reconcile_rejection(result.settlement, case["principal"])
        assert found.status == ("RECORDED" if committed else "OUTCOME_UNKNOWN")
        assert attempts == [draft.event_id]  # Explicit read never inserts.
        if committed: assert found.receipt.event_id == draft.event_id
        # Caller-controlled same-event replay only; no new draft or UUID.
        replay = writer.record_after_settlement(result.settlement)
        assert replay.status == ("RECORDED" if committed else "OUTCOME_UNKNOWN")
        assert replay.attempt_status == (None if committed else "RECORDED")
        leads, rows = readback(rejection_engine, case)
        assert leads == [] and len(rows) == 1 and rows[0].event_id == draft.event_id
        assert attempts == ([draft.event_id] if committed else [draft.event_id, draft.event_id])
        assert writer.reconcile_rejection(result.settlement, case["principal"]).status == "RECORDED"
    finally:
        writer.close();source.dispose();proxy.close()


def test_r2_postgres_valid_sealed_content_collision_is_rejected(rejection_engine, monkeypatch):
    from tests.test_rejection_deadline import test_reconciliation_rejects_same_uuid_different_canonical_evidence
    test_reconciliation_rejects_same_uuid_different_canonical_evidence(rejection_engine, monkeypatch)


def test_r2_hostname_resolution_is_inside_total_call_budget(rejection_engine, monkeypatch, record_property):
    """A socket timeout must not hide an earlier unbounded synchronous resolver.

    No real DNS request or DB connection is made through the faulty endpoint.
    R2 reached this controlled resolver boundary; R3 must reject it first.
    """
    case = seed_case(rejection_engine)
    source = create_engine(rejection_engine.url.set(host="r2-resolver.invalid"),
                           connect_args=dict(rejection_engine._test_rejection_connect_args))
    source._test_rejection_connect_args = dict(rejection_engine._test_rejection_connect_args)
    writer = recorder(source)
    original = writer.record_after_settlement
    durations, resolved = [], []
    def delayed_resolution(host, *args, **kwargs):
        resolved.append(host)
        time.sleep(5.2)  # Controlled synchronous resolver stall, not a random outage.
        raise socket.gaierror(socket.EAI_AGAIN, "Synthetic resolver unavailable")
    def measured(record):
        started = time.monotonic()
        result = original(record)
        durations.append(time.monotonic() - started)
        return result
    monkeypatch.setattr(socket, "getaddrinfo", delayed_resolution)
    monkeypatch.setattr(writer, "record_after_settlement", measured)
    try:
        result = record_denied(source, case, writer, work=False).result
        record_property("resolver_failure_seconds", durations[0])
        record_property("resolver_failure_status", result.status)
        assert resolved == []  # Same stalled resolver is now unreachable.
        assert result.status == "NOT_RECORDED" and writer._storage.audit_bind.pool.checkedout() == 0
        assert readback(rejection_engine, case) == ([], [])
        assert durations[0] <= 5.0  # A35 applies before connect_timeout can start.
    finally:
        writer.close();source.dispose()


def test_r3_active_canonical_endpoint_connects_without_dns(rejection_engine, monkeypatch, record_property):
    from ipaddress import ip_address
    from sqlalchemy.orm import sessionmaker
    from backend.services.rejection_recorder import RejectionRecorder
    case = seed_case(rejection_engine)
    # Resolve/connect once in canonical initialization, OUTSIDE recorder calls.
    source = create_engine(rejection_engine.url.set(host="localhost"),
                           connect_args=dict(rejection_engine._test_rejection_connect_args))
    try:
        with source.connect() as canonical:
            native = canonical.connection.driver_connection
            address = str(ip_address(native.info.hostaddr))
            canonical_identity = canonical.exec_driver_sql(
                "SELECT current_database(), inet_server_addr()::text, inet_server_port()").one()
            writer = RejectionRecorder(sessionmaker(bind=source, autoflush=False),
                canonical_connect_args=rejection_engine._test_rejection_connect_args,
                canonical_connections=(canonical,))
        monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: pytest.fail("Recorder DNS"))
        # Cold recorder pool: the measured call itself must connect without DNS.
        result = _timed_denial(source, case, writer, monkeypatch, record_property, "resolved_endpoint")
        assert result.status == "RECORDED" and len(readback(rejection_engine, case)[1]) == 1
        from backend.database.rejection_storage import Attempt, attempt_scope
        with attempt_scope(Attempt()), writer._storage.audit_bind.connect() as audit:
            info = audit.connection.driver_connection.info
            assert info.host == "localhost" and info.hostaddr == address
            assert audit.exec_driver_sql(
                "SELECT current_database(), inet_server_addr()::text, inet_server_port()").one() == canonical_identity
        assert writer._storage.audit_bind.pool.checkedout() == 0
        record_property("canonical_hostaddr_numeric", True)
    finally:
        if "writer" in locals(): writer.close()
        source.dispose()


def test_r3_stale_numeric_hostaddr_never_falls_back_to_dns(rejection_engine, monkeypatch, record_property):
    case = seed_case(rejection_engine)
    # A bound but non-listening loopback endpoint is deterministically stale.
    with socket.socket() as stale:
        stale.bind(("127.0.0.1", 0))
        source = create_engine(rejection_engine.url.set(host="stale.example.test", port=stale.getsockname()[1]),
                               connect_args={**rejection_engine._test_rejection_connect_args, "hostaddr": "127.0.0.1"})
        source._test_rejection_connect_args = {**rejection_engine._test_rejection_connect_args, "hostaddr": "127.0.0.1"}
        writer = recorder(source)
        monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: pytest.fail("Stale endpoint DNS fallback"))
        try:
            result = _timed_denial(source, case, writer, monkeypatch, record_property, "stale_hostaddr")
            assert result.status == "NOT_RECORDED" and readback(rejection_engine, case) == ([], [])
            assert writer._storage.audit_bind.pool.checkedout() == 0
        finally: writer.close();source.dispose()


def _g0i_pg_failed_replay(writer, record, fault, monkeypatch):
    from backend.database.rejection_storage import Attempt, attempt_scope, DeadlineConnection
    from backend.repositories.audit_repository import AuditRepository
    from backend.services import rejection_recorder as module
    import psycopg
    calls = []
    with monkeypatch.context() as patch:
        patch.setattr(AuditRepository, "_get_matching_event", lambda *_: pytest.fail("Implicit replay reconciliation"))
        if fault == "pool":
            with attempt_scope(Attempt()), writer._storage.audit_bind.connect():
                result = writer.record_after_settlement(record)
                assert writer._storage.audit_bind.pool.checkedout() == 1
                return result, calls
        if fault == "connection":
            writer._storage.audit_bind.dispose()
            def unavailable(cls, *args, **kwargs):
                calls.append(1)
                raise psycopg.OperationalError("Synthetic driver connection acquisition failure")
            patch.setattr(DeadlineConnection, "connect", classmethod(unavailable))
        else:
            state = Attempt(clock=lambda: 0.0)
            state.clock = lambda: 5.0
            patch.setattr(module, "Attempt", lambda: state)
            patch.setattr(writer, "_persist", lambda *_: pytest.fail("Expired replay touched DB"))
        return writer.record_after_settlement(record), calls


@pytest.mark.parametrize("committed", [False, True])
@pytest.mark.parametrize("fault", ["pool", "connection", "expired"])
def test_g0i_pg_unknown_replay_failure_preserves_event_knowledge(
        rejection_engine, monkeypatch, record_property, committed, fault):
    """Permanent G0H regression, including actual absent/committed variants."""
    case = seed_case(rejection_engine)
    proxy = _CommitProxy(rejection_engine.url, "committed" if committed else "absent").start()
    source = _proxy_source(rejection_engine, proxy)
    writer = recorder(source)
    inserts = []
    def executed(_connection, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("INSERT INTO AUDIT_EVENTS"):
            inserts.append(1)
    event.listen(writer._storage.audit_bind, "before_cursor_execute", executed)
    try:
        first = _timed_denial(source, case, writer, monkeypatch, record_property, "initial_unknown")
        assert first.status == first.attempt_status == "OUTCOME_UNKNOWN" and proxy.faulted.is_set()
        draft = first.settlement.draft
        assert len(readback(rejection_engine, case)[1]) == int(committed)
        assert inserts == [1]
        proxy.mode = "pass"
        started = time.monotonic()
        replay, calls = _g0i_pg_failed_replay(writer, first.settlement, fault, monkeypatch)
        elapsed = time.monotonic() - started
        record_property("replay_failure_seconds", elapsed)
        record_property("event_status", replay.status)
        record_property("attempt_status", replay.attempt_status)
        assert elapsed <= 5.0
        assert replay.status == "OUTCOME_UNKNOWN" and replay.attempt_status == "NOT_RECORDED"
        assert replay.settlement is first.settlement and replay.settlement.draft is draft
        assert calls == ([1] if fault == "connection" else [])
        assert writer._storage.audit_bind.pool.checkedout() == 0 and inserts == [1]
        leads, rows = readback(rejection_engine, case)
        assert leads == [] and len(rows) == int(committed)
        if committed: assert rows[0].event_id == draft.event_id
        found = writer.reconcile_rejection(first.settlement, case["principal"])
        assert found.status == ("RECORDED" if committed else "OUTCOME_UNKNOWN")
        assert inserts == [1] and len(readback(rejection_engine, case)[1]) == int(committed)
        if committed: assert found.receipt.event_id == draft.event_id
    finally:
        writer.close();source.dispose();proxy.close()


@pytest.mark.parametrize("origin", ["commit", "reconciliation"])
@pytest.mark.parametrize("fault", ["pool", "connection", "expired"])
def test_g0i_pg_recorded_knowledge_is_absorbing(
        rejection_engine, monkeypatch, record_property, origin, fault):
    case = seed_case(rejection_engine)
    proxy = _CommitProxy(rejection_engine.url, "committed" if origin == "reconciliation" else "pass").start()
    source = _proxy_source(rejection_engine, proxy)
    writer = recorder(source)
    try:
        first = _timed_denial(source, case, writer, monkeypatch, record_property, "recorded_origin")
        proxy.mode = "pass"
        known = (writer.reconcile_rejection(first.settlement, case["principal"])
                 if origin == "reconciliation" else first)
        assert known.status == "RECORDED"
        with monkeypatch.context() as patch:
            patch.setattr(writer, "_persist", lambda *_: pytest.fail("Known event retried DB"))
            started = time.monotonic()
            later, calls = _g0i_pg_failed_replay(writer, first.settlement, fault, patch)
            elapsed = time.monotonic() - started
        record_property("recorded_replay_seconds", elapsed)
        assert elapsed <= 5.0 and calls == []
        assert later.status == "RECORDED" and later.attempt_status is None
        assert later.receipt == known.receipt
        leads, rows = readback(rejection_engine, case)
        assert leads == [] and len(rows) == 1 and rows[0].event_id == first.settlement.draft.event_id
        assert writer._storage.audit_bind.pool.checkedout() == 0
    finally:
        writer.close();source.dispose();proxy.close()
