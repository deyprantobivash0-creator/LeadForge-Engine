# ADR-002: Governed command transactions

Date: 2026-10-15. Status: local implementation candidate; independent review required.

## Context

E02's logical scope marker cannot establish physical SQLite ownership. A raw
outermost savepoint can resemble a normal transaction, and RELEASE can commit
before E02 exits. Raw COMMIT can similarly bypass root rollback. P1 remains a
separate unpublished acquisition candidate and is not adopted by this increment.

## Decision

Use typed immutable root identity plus mutable lifecycle state in transaction
infrastructure. The internal registry is keyed by the injected Session;
Session.info never supplies authority. Bind SessionTransaction, Connection,
RootTransaction, DBAPI connection, dialect and execution thread. A fresh nonce
is minted per root. Context-local, operation-specific permits consume ordered
stages and are cleared on exit; they never span the application body.

Guard public Session/Connection settlement methods for the scope lifetime and
restore their exact prior instance definitions afterward. This small per-instance
boundary avoids changing the global Session factory or introducing a proxy.
Events independently fence native settlement and cursor execution. A guarded
flush context permits SQLAlchemy's exception-path recovery, preserving expected
row conflicts; application rollback APIs remain guarded even inside ORM hooks.
Raw DBAPI/native transaction-object manipulation is unsupported and statically
prohibited, not sandboxed against hostile Python.

SQLite remains physically lazy. Reads do not reserve its writer. Before typed
DML, explicit physical-root requests or approved savepoints, infrastructure emits
deferred BEGIN and records provenance. Unknown existing physical transactions
are rejected. No global BEGIN IMMEDIATE and no implicit transaction restart.
PostgreSQL retains native psycopg transactions; autocommit is rejected.

Opaque SQL is rejected during governed execution, rather than parsed for
transaction keywords. Bound SQLAlchemy expressions and schema-default text are
preserved. Only exact infrastructure BEGIN/savepoint operations receive narrow
single-use execution stages. Readiness's two literal queries remain outside E02.

CSV uses service_savepoint: establish a real root, flush before creating the
savepoint, create under a permit, consume it before yielding, then release or
roll back only that savepoint. Business duplicate classification remains in CSV.

Policy violations permanently break the unit, including caught violations.
Native Connection event failures require invalidation/discard because SQLAlchemy
may already have deactivated its logical root. Ordinary caught nested failures
retain existing rollback-only/provisional-work semantics.

## Alternatives

Documentation/static rules alone do not prevent runtime escapes. Events alone
cannot distinguish caller methods from ORM recovery at every boundary. A marker
alone cannot stop settlement. A broad Session wrapper/factory migration is
unnecessary. Eager physical roots alter pre-write authentication reads and
SQLite contention. Global BEGIN IMMEDIATE reserves the writer too early.

## Consequences and limits

Application settlement, raw DBAPI access, unapproved savepoints, replacement
engines/Sessions and opaque runtime SQL are architecture violations. Operator,
migration and fixture code are classified separately; quarantined helpers must
not become runtime callers. This is not whole-Python analysis or hostile-code
isolation. Commit transport failure remains ambiguous; no automatic retry or
exactly-once effect guarantee is introduced.

TX is published and CI-verified independently before P1 adaptation/review.
Lifecycle/import/denial auditing and schema changes are outside this increment.
