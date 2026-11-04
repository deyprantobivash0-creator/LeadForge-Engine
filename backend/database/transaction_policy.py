"""Govern one injected Session; this is not a sandbox for hostile Python.

Raw DBAPI and native transaction-object manipulation are unsupported application
APIs. Public Session/Connection settlement is guarded before SQLAlchemy changes
its logical state; events also fence transaction control at the driver boundary.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from enum import Enum, auto
import sys
from threading import get_ident
from weakref import WeakKeyDictionary

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import FlushError
from sqlalchemy.schema import ExecutableDDLElement
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.expression import SavepointClause, ReleaseSavepointClause, RollbackToSavepointClause


class TransactionPolicyViolation(InvalidRequestError):
    """The operation Session must be discarded after a policy violation."""


def _restricted_sql_commands(sql):
    """Classify transaction/schema commands, not wrapper types or literal contents.

    This is a bounded lexical fence, not a SQL parser. Ambiguous quoting/comments
    fail closed. Business values should use SQLAlchemy's bound parameters.
    """
    commands, words = [], []

    def finish():
        if words:
            head = words[0]
            if head in {"BEGIN", "COMMIT", "END", "ROLLBACK", "ABORT", "SAVEPOINT", "RELEASE",
                        "CREATE", "ALTER", "DROP", "TRUNCATE", "COMMENT", "GRANT", "REVOKE"}:
                commands.append("ROLLBACK TO" if head == "ROLLBACK" and "TO" in words[1:3] else head)
            elif head in {"START", "PREPARE"} and words[1:2] == ["TRANSACTION"]:
                commands.append(head + " TRANSACTION")
            elif head == "SET" and {"TRANSACTION", "AUTOCOMMIT"}.intersection(words[1:]):
                commands.append("SET TRANSACTION")
        words.clear()

    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch.isspace() or ch == "\ufeff":
            i += 1
        elif sql.startswith("--", i):
            i += 2
            while i < len(sql) and sql[i] not in "\r\n":
                i += 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            if end < 0 or "/*" in sql[i + 2:end]:
                return None  # Nested comments have dialect-dependent semantics.
            i = end + 2
        elif ch in "'\"`[" or ch == "$":
            if ch == "$":
                end = sql.find("$", i + 1)
                tag = sql[i + 1:end] if end >= 0 else None
                if tag is None or (tag and not (tag.isidentifier() and tag.isascii())):
                    if len(words) < 5:
                        words.append("<value>")
                    i += 1
                    continue
                quote = sql[i:end + 1]
                end = sql.find(quote, end + 1)
                if end < 0:
                    return None
                i = end + len(quote)
            else:
                quote = "]" if ch == "[" else ch
                i += 1
                while i < len(sql):
                    if sql[i] == "\\" and ch == "'":
                        return None  # Standard and escape-string modes differ.
                    if sql[i] == quote:
                        i += 1
                        if i >= len(sql) or sql[i] != quote:
                            break
                    i += 1
                else:
                    return None
            if len(words) < 5:
                words.append("<quoted>")
        elif ch == ";":
            finish()
            i += 1
        elif ch.isalpha() or ch == "_":
            end = i + 1
            while end < len(sql) and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            if len(words) < 5:
                words.append(sql[i:end].upper())
            i = end
        else:
            if len(words) < 5:
                words.append(ch)
            i += 1
    finish()
    return tuple(commands)


class Operation(Enum):
    ROOT_COMMIT = auto()
    ROOT_ROLLBACK = auto()
    PHYSICAL_BEGIN = auto()
    SAVEPOINT_CREATE = auto()
    SAVEPOINT_RELEASE = auto()
    SAVEPOINT_ROLLBACK = auto()
    CLEANUP = auto()


@dataclass(frozen=True)
class RootAuthority:
    nonce: object
    session: Session
    engine: object
    session_transaction: object
    connection: object
    connection_transaction: object
    driver: object
    dialect: str
    owner_thread: int


@dataclass
class _Permit:
    authority: RootAuthority
    operation: Operation
    remaining: list[str]
    recovered: bool = False


_permit: ContextVar[_Permit | None] = ContextVar("leadforge_transaction_permit", default=None)
_flushing: ContextVar[object | None] = ContextVar("leadforge_transaction_flush", default=None)
_roots: WeakKeyDictionary = WeakKeyDictionary()
_MISSING = object()


def current_root(db):
    # Session.info is deliberately not an authority source.
    return _roots.get(db)


@dataclass
class GovernedRoot:
    db: Session
    authority: RootAuthority | None = None
    failed: bool = False
    broken: bool = False
    physical: bool = False
    finished: bool = False
    listeners: list = field(default_factory=list)
    methods: list = field(default_factory=list)
    connection_callbacks: list = field(default_factory=list)
    permit_scopes: list = field(default_factory=list)

    def violate(self):
        self.broken = True
        self.failed = True
        raise TransactionPolicyViolation("Transaction ownership policy rejected an operation.")

    def check(self):
        a = self.authority
        if (self.broken or self.finished or a is None or get_ident() != a.owner_thread
                or current_root(self.db) is not self):
            self.violate()
        if self.db.get_bind() is not a.engine:
            self.violate()
        c = a.connection
        if c is None:
            transaction = self.db.get_transaction()
            if a.session_transaction is None and transaction is not None:
                if transaction.origin.name != "AUTOBEGIN":
                    self.violate()
                self.authority = replace(a, session_transaction=transaction)
            elif transaction is not a.session_transaction:
                self.violate()
            return
        if (self.db.get_transaction() is not a.session_transaction or c.closed or c.invalidated
                or c.get_transaction() is not a.connection_transaction
                or c.connection.driver_connection is not a.driver):
            self.violate()
        if a.dialect == "sqlite":
            if a.driver.in_transaction != self.physical:
                self.violate()
        elif a.driver.autocommit:
            self.violate()

    @contextmanager
    def permit(self, operation, *stages):
        depth = len(self.permit_scopes)
        self.open_permit(operation, *stages)
        try:
            yield
        finally:
            self.clear_permits(depth)

    def open_permit(self, operation, *stages):
        if self.finished or _permit.get() is not None:
            self.violate()
        p = _Permit(self.authority, operation, list(stages))
        token = _permit.set(p)
        self.permit_scopes.append((p, token))

    def clear_permits(self, depth=0):
        # Each set has one owner, even when a callback returns before SQL runs.
        # A scope already unwound by root teardown is safe to close again.
        while len(self.permit_scopes) > depth:
            p, token = self.permit_scopes[-1]
            p.remaining.clear()
            _permit.reset(token)
            self.permit_scopes.pop()

    def consume(self, stage, operations):
        p = _permit.get()
        if (self.finished or self.authority is None or get_ident() != self.authority.owner_thread
                or current_root(self.db) is not self or p is None
                or p.authority.nonce is not self.authority.nonce
                or p.authority.session is not self.db
                or p.authority.connection is not self.authority.connection
                or p.operation not in operations
                or not p.remaining or p.remaining.pop(0) != stage):
            self.violate()

    def listen(self, target, name, callback):
        event.listen(target, name, callback)
        self.listeners.append((target, name, callback))

    def guard_method(self, target, name, operations, stage):
        original = getattr(target, name)
        stored = target.__dict__.get(name, _MISSING)

        def guarded(*args, **kwargs):
            self.consume(stage, operations)
            return original(*args, **kwargs)

        setattr(target, name, guarded)
        self.methods.append((target, name, stored, guarded))

    def start(self):
        if current_root(self.db) is not None:
            self.violate()
        existing = self.db.get_transaction()
        if existing is not None and existing.origin.name != "AUTOBEGIN":
            self.violate()
        engine = self.db.get_bind()
        if isinstance(engine, Connection):
            self.violate()  # Externally owned Connection transactions cannot be adopted.
        self.authority = RootAuthority(object(), self.db, engine, existing, None, None, None, None, get_ident())
        _roots[self.db] = self

        original_get_bind = self.db.get_bind
        stored = self.db.__dict__.get("get_bind", _MISSING)

        def get_bind(*args, **kwargs):
            # Resolve mapper/clause/explicit overrides too. Only Session-owned
            # acquisition from the entry Engine may establish root authority;
            # a caller's Connection is unsupported even before it has begun.
            resolved = original_get_bind(*args, **kwargs)
            if resolved is not self.authority.engine:
                self.violate()
            return resolved

        self.db.get_bind = get_bind
        self.methods.append((self.db, "get_bind", stored, get_bind))

        def before_commit(db):
            self.check()
            self.consume("session_commit", {Operation.ROOT_COMMIT, Operation.SAVEPOINT_RELEASE})

        def cursor(conn, _cursor, statement, _parameters, context, _many):
            self.check()
            compiled = context.compiled if context else None
            sql_object = compiled.statement if compiled is not None else None
            commands = _restricted_sql_commands(statement)
            if commands is None or isinstance(sql_object, ExecutableDDLElement):
                self.violate()
            p = _permit.get()
            # Classify every emitted statement, including custom compiled SQL.
            # Only a matching infrastructure operation gets a single-use stage.
            if commands and p is not None and p.authority.nonce is self.authority.nonce and p.remaining:
                if (p.operation == Operation.PHYSICAL_BEGIN and commands == ("BEGIN",)
                        and statement == "BEGIN"):
                    self.consume("begin_sql", {Operation.PHYSICAL_BEGIN})
                    return
                expected = {
                    Operation.SAVEPOINT_CREATE: SavepointClause,
                    Operation.SAVEPOINT_RELEASE: ReleaseSavepointClause,
                    Operation.SAVEPOINT_ROLLBACK: RollbackToSavepointClause,
                }.get(p.operation)
                command = {Operation.SAVEPOINT_CREATE: "SAVEPOINT",
                           Operation.SAVEPOINT_RELEASE: "RELEASE",
                           Operation.SAVEPOINT_ROLLBACK: "ROLLBACK TO"}.get(p.operation)
                if (expected is not None and commands == (command,)
                        and type(sql_object) is expected
                        and p.remaining[0] == "savepoint_sql"):
                    self.consume("savepoint_sql", {p.operation})
                    return
            if (commands or compiled is None or isinstance(sql_object, TextClause)
                    or (p is not None and p.operation == Operation.SAVEPOINT_ROLLBACK)):
                self.violate()
            if getattr(compiled.statement, "is_dml", False):
                self.ensure_physical()

        def commit(conn):
            self.check()
            self.consume("connection_commit", {Operation.ROOT_COMMIT})

        def rollback(conn):
            p = _permit.get()
            if p is not None and p.authority.nonce is self.authority.nonce:
                self.consume("connection_rollback", {Operation.ROOT_ROLLBACK, Operation.CLEANUP})
                return
            # SQLAlchemy itself rolls back a failed ORM flush. Public caller
            # APIs are separately guarded, even when called from an ORM hook.
            if (getattr(_flushing.get(), "nonce", None) is self.authority.nonce
                    and sys.exc_info()[1] is not None):
                self.failed = True
                return
            self.violate()

        def savepoint(conn, name):
            self.check()
            self.consume("savepoint_create", {Operation.SAVEPOINT_CREATE})

        def release(conn, name, context):
            self.check()
            self.consume("savepoint_release", {Operation.SAVEPOINT_RELEASE})

        def rollback_savepoint(conn, name, context):
            p = _permit.get()
            if p is not None and p.authority.nonce is self.authority.nonce:
                self.consume("savepoint_rollback", {Operation.SAVEPOINT_ROLLBACK})
                return
            if (getattr(_flushing.get(), "nonce", None) is self.authority.nonce
                    and sys.exc_info()[1] is not None):
                # The enclosing guarded flush owns this callback's token. Its
                # finally resets even an unconsumed or interrupted recovery.
                self.open_permit(Operation.SAVEPOINT_ROLLBACK, "savepoint_sql")
                return
            self.violate()

        def before_flush(db, _context, _instances):
            self.check()

        def recovery_complete(db, _previous_transaction):
            p = _permit.get()
            if (p is not None and p.authority.nonce is self.authority.nonce
                    and p.operation == Operation.SAVEPOINT_ROLLBACK and not p.remaining):
                # SQLAlchemy emits this only after rollback and logical cleanup
                # succeed; consuming cursor permission alone proves neither.
                p.recovered = True

        def query(execute_state):
            self.check()

        def after_begin(db, transaction, connection):
            if self.authority.connection is None:
                self.bind(connection)
            elif connection is not self.authority.connection:
                self.violate()

        def execution_options(conn, options):
            if {"isolation_level", "autocommit"}.intersection(options):
                self.violate()

        self.listen(self.db, "before_commit", before_commit)
        self.listen(self.db, "before_flush", before_flush)
        self.listen(self.db, "after_soft_rollback", recovery_complete)
        self.listen(self.db, "do_orm_execute", query)
        self.listen(self.db, "after_begin", after_begin)
        self.connection_callbacks = [("before_cursor_execute", cursor), ("commit", commit), ("rollback", rollback),
                         ("savepoint", savepoint), ("release_savepoint", release),
                         ("rollback_savepoint", rollback_savepoint),
                         ("set_connection_execution_options", execution_options)]
        self.guard_method(self.db, "commit", {Operation.ROOT_COMMIT}, "session_commit_api")
        self.guard_method(self.db, "rollback", {Operation.ROOT_ROLLBACK, Operation.CLEANUP}, "session_rollback_api")
        self.guard_method(self.db, "close", {Operation.CLEANUP}, "session_close_api")
        self.guard_method(self.db, "begin_nested", {Operation.SAVEPOINT_CREATE}, "session_savepoint_api")
        original_flush = self.db.flush
        stored = self.db.__dict__.get("flush", _MISSING)

        def flush(*args, **kwargs):
            self.check()
            p = _permit.get()
            if (p is not None and p.operation == Operation.SAVEPOINT_RELEASE
                    and (self.db.new or self.db.dirty or self.db.deleted)):
                self.violate()
            depth = len(self.permit_scopes)
            token = _flushing.set(self.authority)
            try:
                return original_flush(*args, **kwargs)
            finally:
                try:
                    for p, _token in self.permit_scopes[depth:]:
                        if p.operation == Operation.SAVEPOINT_ROLLBACK and not p.recovered:
                            self.broken = True
                            self.failed = True
                    self.clear_permits(depth)
                finally:
                    _flushing.reset(token)

        self.db.flush = flush
        self.methods.append((self.db, "flush", stored, flush))
        for name in ("get", "connection"):
            original = getattr(self.db, name)
            stored = self.db.__dict__.get(name, _MISSING)

            def checked(*args, _original=original, _name=name, **kwargs):
                self.check()
                if _name == "connection":
                    # Session.connection's explicit bind argument bypasses
                    # SQLAlchemy's own get_bind call; validate it before checkout.
                    bind_arguments = kwargs.get("bind_arguments", args[0] if args else None)
                    if bind_arguments:
                        self.db.get_bind(**bind_arguments)
                return _original(*args, **kwargs)

            setattr(self.db, name, checked)
            self.methods.append((self.db, name, stored, checked))
        if existing is not None:
            # An already checked-out authorization-read Connection does not
            # re-emit after_begin. Adopt and instrument that exact Connection.
            connection = self.db.connection()
            if self.authority.connection is None:
                self.bind(connection)

    def bind(self, connection):
        self.check()
        a = self.authority
        if connection.engine is not a.engine:
            self.violate()
        if a.connection is not None:
            if connection is not a.connection:
                self.violate()
            return
        # after_begin runs after SQLAlchemy has either created or joined a
        # transaction. Its settlement bookkeeping distinguishes Session-owned
        # checkout/commit from a caller Connection or a rollback-only join.
        # Inspect, never mutate, that provenance before accepting the root.
        ownership = a.session_transaction._connections.get(connection)
        if (ownership is None or ownership[0] is not connection
                or ownership[1] is not connection.get_transaction()
                or ownership[2:] != (True, True)):
            self.violate()
        driver = connection.connection.driver_connection
        dialect = connection.dialect.name
        if (connection.in_nested_transaction() or self.db.in_nested_transaction()
                or dialect not in {"sqlite", "postgresql"}):
            self.violate()
        if dialect == "sqlite":
            if (driver.in_transaction or driver.isolation_level is None
                    or getattr(driver, "autocommit", None) is True):
                self.violate()
        elif driver.autocommit:
            self.violate()
        self.authority = replace(a, session_transaction=self.db.get_transaction(), connection=connection,
                                 connection_transaction=connection.get_transaction(), driver=driver, dialect=dialect)
        for name, callback in self.connection_callbacks:
            self.listen(connection, name, callback)
        self.guard_method(connection, "commit", {Operation.ROOT_COMMIT}, "connection_commit_api")
        self.guard_method(connection, "rollback", {Operation.ROOT_ROLLBACK, Operation.CLEANUP}, "connection_rollback_api")
        self.guard_method(connection, "begin_nested", {Operation.SAVEPOINT_CREATE}, "connection_savepoint_api")

    def ensure_physical(self):
        self.check()
        if self.authority.connection is None:
            self.db.connection()
            self.check()
        a = self.authority
        if a.dialect == "sqlite" and not self.physical:
            with self.permit(Operation.PHYSICAL_BEGIN, "begin_sql"):
                a.connection.exec_driver_sql("BEGIN")
            self.physical = True
            self.check()

    def commit(self):
        self.check()
        self.db.flush()
        with self.permit(Operation.ROOT_COMMIT, "session_commit_api", "session_commit", "connection_commit"):
            self.db.commit()

    def remove(self):
        # Local finally blocks normally finish first. Revoke any outstanding
        # scope owned by this root before destroying its registry authority;
        # never reset another root's enclosing permit.
        self.clear_permits()
        for target, name, callback in reversed(self.listeners):
            event.remove(target, name, callback)
        self.listeners.clear()
        for target, name, stored, guard in reversed(self.methods):
            if target.__dict__.get(name) is guard:
                if stored is _MISSING:
                    delattr(target, name)
                else:
                    setattr(target, name, stored)
        self.methods.clear()
        _roots.pop(self.db, None)
        self.finished = True

    def rollback(self):
        # Remove guards before fatal invalidation: SQLAlchemy may already have
        # deactivated its root after an event rejected settlement.
        if self.broken:
            c = self.authority.connection if self.authority else None
            self.remove()
            if c is not None and not c.closed:
                c.invalidate()
            self.db.invalidate()
            return
        with self.permit(Operation.ROOT_ROLLBACK, "session_rollback_api", "connection_rollback"):
            self.db.rollback()


def require_governed_physical_root(db):
    root = current_root(db)
    if root is None:
        raise TransactionPolicyViolation("Caller-owned governed transaction required.")
    root.ensure_physical()


@contextmanager
def service_savepoint(db):
    root = current_root(db)
    if root is None:
        raise TransactionPolicyViolation("Caller-owned governed transaction required.")
    root.ensure_physical()
    db.flush()  # Pre-savepoint flush recovery must not inherit a create permit.
    try:
        with root.permit(Operation.SAVEPOINT_CREATE, "session_savepoint_api", "connection_savepoint_api",
                         "savepoint_create", "savepoint_sql"):
            nested = db.begin_nested()
            db.connection()  # Materialize the savepoint before exposing its body.
    except BaseException:
        # Without an established savepoint, row-level recovery is not safe.
        root.broken = True
        root.failed = True
        raise
    try:
        yield
        # Business materialization belongs to the body/recovery phase. Drain
        # callback-created work too, using public Session state and the same
        # bounded flush policy as SQLAlchemy commit preparation.
        for _ in range(100):
            db.flush()
            if not (db.new or db.dirty or db.deleted):
                break
        else:
            raise FlushError("Savepoint business flush did not converge.")
    except BaseException:
        try:
            with root.permit(Operation.SAVEPOINT_ROLLBACK, "savepoint_rollback", "savepoint_sql"):
                nested.rollback()
        except BaseException:
            root.broken = True
            root.failed = True
        raise
    else:
        try:
            with root.permit(Operation.SAVEPOINT_RELEASE, "session_commit", "savepoint_release", "savepoint_sql"):
                nested.commit()
        except BaseException:
            root.broken = True
            root.failed = True
            raise
