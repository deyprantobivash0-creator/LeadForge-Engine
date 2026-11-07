"""Recorder-only storage ownership; never changes the business Engine or E02.

The canonical owner supplies the Engine and its original connect_args. Calls
use one deadline and a separate
one-slot, non-waiting pool. No retry, cancellation thread or socket manipulation.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from collections.abc import Mapping
import math
from ipaddress import ip_address
import re
import sqlite3
from time import monotonic

import psycopg
from psycopg import waiting
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool


# Work gets 3s; cleanup gets the remaining 1s; 1s is left below A35 for
# scheduling/return overhead. Neither a driver nor cleanup restarts the clock.
CALL_SECONDS = 4.0
CLEANUP_SECONDS = 1.0
_attempt = ContextVar("rejection_storage_deadline", default=None)


class RejectionDeadlineExceeded(TimeoutError):
    """Content-free recorder deadline; not proof of transaction rollback."""


@dataclass
class Attempt:
    clock: object = monotonic
    deadline: float = field(init=False)
    cleaning: bool = False
    commit_started: bool = False
    acknowledged: bool = False
    uncertain: bool = False
    commit_rejected: bool = False
    known_rollback: bool = False
    receipt: object = None

    def __post_init__(self):
        self.deadline = self.clock() + CALL_SECONDS

    def remaining(self, *, cleanup=False):
        limit = self.deadline if cleanup or self.cleaning else self.deadline - CLEANUP_SECONDS
        value = limit - self.clock()
        if value <= 0:
            raise RejectionDeadlineExceeded("Rejection recorder deadline exceeded.")
        return value


def active_attempt():
    state = _attempt.get()
    if state is None:
        raise RejectionDeadlineExceeded("Recorder storage requires an invocation deadline.")
    state.remaining()
    return state


@contextmanager
def attempt_scope(state):
    token = _attempt.set(state)
    try:
        yield
    finally:
        _attempt.reset(token)


class DeadlineConnection(psycopg.Connection):
    @classmethod
    def connect(cls, conninfo="", *, autocommit=False, prepare_threshold=5,
                context=None, row_factory=None, cursor_factory=None, **kwargs):
        # This guard runs BEFORE Psycopg's conninfo_attempts resolves names.
        params = psycopg.conninfo.conninfo_to_dict(conninfo, **kwargs)
        if not _pg_endpoints_ready(params):
            raise RejectionDeadlineExceeded("Trusted pre-resolved recorder endpoint unavailable.")
        return super().connect(conninfo, autocommit=autocommit,
                               prepare_threshold=prepare_threshold, context=context,
                               row_factory=row_factory, cursor_factory=cursor_factory, **kwargs)

    @classmethod
    def _connect_gen(cls, conninfo=""):
        # Psycopg may try multiple configured endpoints. Each attempt must fit
        # the SAME remaining work allowance; a later host gets no fresh budget.
        if active_attempt().remaining() < 2.1:
            raise RejectionDeadlineExceeded("Insufficient connection budget.")
        return (yield from super()._connect_gen(conninfo))

    def wait(self, gen, interval=0.05, timeout=None):
        try:
            state = active_attempt()
            remaining = state.remaining()
            if timeout is not None:
                remaining = min(remaining, timeout)
            # Direct supported driver wait avoids Connection.wait's Ctrl-C
            # fallback, which allocates two independent five-second waits.
            return waiting.wait(gen, self.pgconn.socket, interval=min(interval, remaining),
                                timeout=remaining)
        except (psycopg.errors._WaitTimeout, RejectionDeadlineExceeded):
            state = _attempt.get()
            try:
                if state is not None and self.pgconn.transaction_status == psycopg.pq.TransactionStatus.ACTIVE:
                    state.cleaning = True
                    # Cancellation dispatch and response draining consume ONLY
                    # the remainder of this invocation's cleanup allowance.
                    self.cancel_safe(timeout=state.remaining(cleanup=True))
                    try:
                        remaining = state.remaining(cleanup=True)
                        waiting.wait(gen, self.pgconn.socket, interval=min(.05, remaining),
                                     timeout=remaining)
                    except psycopg.Error:
                        pass  # Includes the expected server QueryCanceled reply.
            except Exception:
                pass  # No unbounded attempt to prove an uncertain COMMIT.
            finally:
                self.close()
            raise
        except BaseException:
            # Never return an ACTIVE/uncertain connection as healthy. Closing
            # our DBAPI connection is local disposition, not rollback proof.
            self.close()
            raise

    def commit(self):
        state = active_attempt()
        state.commit_started = True
        super().commit()
        state.acknowledged = True

    def rollback(self):
        state = _attempt.get()
        if state is None:
            raise RejectionDeadlineExceeded("No recorder cleanup deadline.")
        previous = state.cleaning
        state.cleaning = True
        try:
            return super().rollback()
        finally:
            state.cleaning = previous


class DeadlineCursor(sqlite3.Cursor):
    def execute(self, sql, parameters=()):
        self.connection.arm()
        return super().execute(sql, parameters)

    def executemany(self, sql, parameters):
        self.connection.arm()
        return super().executemany(sql, parameters)


class DeadlineSQLite(sqlite3.Connection):
    def arm(self):
        remaining = active_attempt().remaining()
        # Fail lock conflicts promptly; no recursive busy/retry loop. Recompute
        # from the shared budget on every statement, including late flushes.
        milliseconds = max(0, min(self._recorder_busy_ms, math.floor(remaining * 1000)))
        super().execute("PRAGMA busy_timeout=" + str(milliseconds))
        self.set_progress_handler(_sqlite_expired, 100)

    def cursor(self, factory=DeadlineCursor):
        return super().cursor(factory)

    def commit(self):
        self.arm()
        state = active_attempt()
        state.commit_started = True
        try:
            super().commit()
        except sqlite3.Error as exc:
            code = getattr(exc, "sqlite_errorcode", None)
            if (isinstance(code, int) and code & 255 in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
                    and self.in_transaction):
                # SQLite explicitly retained this transaction: COMMIT did not
                # complete. Only subsequent successful rollback proves absence.
                state.commit_rejected = True
            raise
        state.acknowledged = True

    def rollback(self):
        state = _attempt.get()
        if state is None:
            raise RejectionDeadlineExceeded("No recorder cleanup deadline.")
        state.remaining(cleanup=True)
        self.set_progress_handler(None, 0)
        result = super().rollback()
        if state.commit_rejected:
            state.known_rollback = True
        return result


def _sqlite_expired():
    try:
        active_attempt().remaining()
        return 0
    except RejectionDeadlineExceeded:
        return 1


@dataclass(frozen=True)
class RejectionStorage:
    business_bind: object
    audit_bind: object
    factory: object

    def configure(self, db):
        remaining = active_attempt().remaining()
        if self.audit_bind.dialect.name == "postgresql":
            # Preserve stricter canonical/session limits, including options
            # supplied through connect_args. Zero means disabled, not 0ms.
            current = db.execute(select(func.current_setting("statement_timeout"),
                                        func.current_setting("lock_timeout"))).one()
            ms = math.floor(active_attempt().remaining() * 1000)
            if ms < 1:
                raise RejectionDeadlineExceeded("No statement budget remains.")
            limits = [_narrow_pg_timeout(value, ms) for value in current]
            db.execute(select(func.set_config("statement_timeout", str(limits[0]), True),
                              func.set_config("lock_timeout", str(limits[1]), True)))


def _narrow_pg_timeout(value, remaining_ms):
    match = re.fullmatch(r"(\d+)(ms|s|min|h|d)?", value)
    if match is None:
        raise ValueError("Unsupported PostgreSQL timeout representation.")
    units = {None: 1, "ms": 1, "s": 1000, "min": 60000, "h": 3600000, "d": 86400000}
    configured = int(match[1]) * units[match[2]]
    return min(configured, remaining_ms) if configured else remaining_ms


def _numeric_address(value):
    try:
        ip_address(value)
        return True
    except ValueError:
        return False


def _socket_host(value):
    # Match this Psycopg version's no-resolver path, not just libpq's wider
    # syntax. Abstract '@' sockets would enter Python DNS and fail closed.
    return value.startswith("/") or (len(value) > 2 and value[1:3] in {":/", ":\\"})


def _pg_endpoints_ready(params):
    hosts = str(params.get("host", "")).split(",")
    addresses = str(params.get("hostaddr", "")).split(",")
    count = max(len(hosts), len(addresses))
    if len(hosts) not in {1, count} or len(addresses) not in {1, count}:
        return False
    if len(hosts) == 1 and count > 1 and hosts[0]:
        return False
    if len(addresses) == 1 and count > 1 and addresses[0]:
        return False
    hosts = hosts if len(hosts) == count else [""] * count
    addresses = addresses if len(addresses) == count else [""] * count
    ports = str(params.get("port", "")).split(",")
    if len(ports) not in {1, count}:
        return False
    return all(_numeric_address(address) if address else
               (_numeric_address(host) or _socket_host(host))
               for host, address in zip(hosts, addresses))


def _resolved_pg_options(business_bind, options, canonical_connections):
    """Snapshot existing canonical connections; never connect, query or resolve.

    Configured hostaddr wins. Missing hostname addresses require a live
    canonical connection for EACH corresponding endpoint. Partial snapshots
    never collapse/reorder multi-host configuration: the call fails closed.
    Refresh by constructing a new adapter from later canonical connections,
    outside all recorder calls. No automatic DNS refresh/fallback exists.
    """
    snapshots = []
    for connection in tuple(canonical_connections):
        if (not isinstance(connection, Connection) or connection.engine is not business_bind
                or connection.closed or connection.invalidated):
            raise ValueError("Live canonical database connection required.")
        if connection.connection.driver_connection.closed:
            raise ValueError("Live canonical Psycopg connection required.")
        info = connection.connection.driver_connection.info
        snapshots.append((info.host, info.hostaddr, str(info.port)))
    if _pg_endpoints_ready(options):
        return options
    hosts = str(options.get("host", "")).split(",")
    addresses = str(options.get("hostaddr", "")).split(",")
    ports = str(options.get("port", "")).split(",")
    if len(addresses) == 1 and not addresses[0]:
        addresses *= len(hosts)
    if len(addresses) != len(hosts) or len(ports) not in {1, len(hosts)}:
        return options  # Invalid/incomplete configuration fails before DNS.
    resolved = list(addresses)
    effective_hosts = list(hosts)
    effective_ports = ports * len(hosts) if len(ports) == 1 else list(ports)
    for index, (host, address) in enumerate(zip(hosts, addresses)):
        if address or _numeric_address(host) or _socket_host(host):
            continue
        matches = [(h, a, p) for h, a, p in snapshots
                   if (h == host or (not host and len(hosts) == 1))
                   and (not effective_ports[index] or p == effective_ports[index])]
        if not matches:
            return options
        h, a, p = matches[0]
        if not (_numeric_address(a) or _socket_host(h)):
            return options
        resolved[index] = a
        if not host:
            effective_hosts[index] = h
        if not effective_ports[index]:
            effective_ports[index] = p
    result = {**options, "host": ",".join(effective_hosts)}
    if any(resolved):
        result["hostaddr"] = ",".join(resolved)
    if not options.get("port"):
        result["port"] = ",".join(effective_ports)
    return result


def create_rejection_storage(business_bind, *, canonical_connect_args=None, canonical_connections=()):
    """Same dialect arguments + original connect_args + narrow timeout overlay.

    Construction/endpoint refresh belongs outside a recorder invocation.
    An Engine URL cannot recover arbitrary create_engine(connect_args=...).
    For the application Engine, read that existing canonical owner's mapping.
    Other trusted owners/tests must pass the mapping they used at construction;
    an empty mapping is explicit, never guessed. No private creator inspection.
    """
    if _attempt.get() is not None:
        raise ValueError("Recorder storage must be initialized outside recorder calls.")
    if canonical_connect_args is None:
        from backend.database.session import engine, connect_args
        if business_bind is not engine:
            raise ValueError("The original canonical connect_args mapping is required.")
        canonical_connect_args = connect_args
    if not isinstance(canonical_connect_args, Mapping):
        raise ValueError("Canonical connect_args must be a mapping.")
    url = business_bind.url
    dialect = business_bind.dialect.name
    args, base_options = business_bind.dialect.create_connect_args(url)
    args = tuple(args)
    options = {**base_options, **dict(canonical_connect_args)}
    if dialect == "sqlite":
        if not url.database or url.database == ":memory:":
            raise ValueError("Independent rejection storage requires file-backed SQLite.")
        if options.get("factory", sqlite3.Connection) is not sqlite3.Connection:
            raise ValueError("Custom SQLite factories require a reviewed deadline adapter.")
        # Keep URI filename/flags exactly as the canonical dialect generated
        # them; never rebuild from url.database or drop mode/cache options.
        busy_ms = max(0, math.floor(min(float(options.get("timeout", 5)), .05) * 1000))
        options = {**options, "factory": DeadlineSQLite, "timeout": 0}

        def connect():
            active_attempt()
            db = sqlite3.connect(*args, **options)
            db._recorder_busy_ms = busy_ms
            db.execute("PRAGMA foreign_keys=ON")
            return db

    elif dialect == "postgresql" and business_bind.dialect.driver == "psycopg":
        if not psycopg.capabilities.has_cancel_safe():
            raise ValueError("Rejection deadlines require bounded driver cancellation support.")
        options = _resolved_pg_options(business_bind, options, canonical_connections)
        configured_timeout = int(options.get("connect_timeout", 0))
        options = {**options, "connect_timeout": min(configured_timeout, 2)
                   if configured_timeout > 0 else 2}

        def connect():
            remaining = active_attempt().remaining()
            # libpq rounds connection timeouts and has a minimum of 2 seconds.
            # Never start that path when it cannot fit in the remaining work.
            if remaining < 2.1:
                raise RejectionDeadlineExceeded("Insufficient connection budget.")
            # The driver guard rejects any unresolved host before DNS. These
            # options were frozen at construction, not refreshed in this call.
            return DeadlineConnection.connect(*args, **options)

    else:
        raise ValueError("Unsupported rejection storage driver.")
    engine = create_engine(url, creator=connect, poolclass=QueuePool, pool_size=1,
                           max_overflow=0, pool_timeout=0, pool_pre_ping=False)
    return RejectionStorage(business_bind, engine,
                            sessionmaker(bind=engine, autoflush=False, autocommit=False))
