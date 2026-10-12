# E02 service-owned transactions

Date: 2026-10-12. Implementation baseline: `3875388f60ca58b698889b25a53620ba50f07afd` on main. Local implementation only; no commit/deployment authorization. No schema change or migration.

## Prior write-path inventory

The inventory covers registered customer routes, their service/repository callers, and quarantined/operator exceptions. Classifications describe the pre-E02 code, not a claim that all legacy paths should be rewritten.

| Write/read path | Prior owner and classification | E02 outcome |
|---|---|---|
| Credential authentication (`authenticate_user`) | GOOD: query/verification only; no hash assignment | Unchanged query semantics; login surrounds it with command boundary |
| Login/session issuance/hash upgrade | GOOD: conditional User UPDATE guards verified hash and holds write lock through session insert/commit; nested login/create_session redundantly rolled back | Shared service scope; login/create_session join one commit/rollback; guard SQL unchanged |
| Password change + other-session revocation | GOOD: service transaction, compare-and-swap credential and active-session predicate | Same SQL, hashing, session-preservation and error behavior; shared command context |
| Logout/session revocation | GOOD: service commit; assignment occurred outside try | Assignment and commit both inside shared context |
| Organization/membership writes | No registered mutation endpoint; organization list/authorization are GOOD queries | No new mutation path; authenticated membership resolution unchanged |
| Lead create | NEEDS_REFACTOR: repository commits/refreshes; service rolls back only IntegrityError | Repository add/flush; service handles all command failures and exact duplicate constraint classification |
| Lead status/lifecycle update | NEEDS_REFACTOR: repository commits; validation not inside operation rollback | Service scope encloses validation + tenant-scoped repository mutation |
| Analysis creation (`save_analysis`) | GOOD: caller-owned mutation step, tenant owner check and flush, no independent commit | Retained as a composable mutation step in processing completion |
| Processing claim/context | ACCEPTABLE_LEGACY: separate claim write and snapshot-read commits | One short claim + snapshot transaction; commit before provider; no read-only commit |
| Processing completion/history | GOOD: Lead projection + linked analysis commit together | Shared service scope, unchanged attempt fence and tenant predicates |
| Processing failure marker | HIGH_RISK: failure-write/commit could fail without rollback and hide original provider/persistence error | Separate short service transaction; secondary failure safely logged; original safe error preserved |
| CSV preview | GOOD: parse/query/sign, no domain mutation/commit | Unchanged |
| CSV confirmation | HIGH_RISK on SQLite legacy mode: logical service commit/savepoints, but first released savepoint could commit without real outer BEGIN; validation outside rollback scope | Whole command enclosed; explicit SQLite BEGIN before row savepoints; one outer commit and existing duplicate handling |
| Dashboard/reports/settings | GOOD: query-only services/routes; report-affecting writes are Lead lifecycle and linked analyses above | No query commits or new Settings mutations |
| Unregistered file-path importer | HIGH_RISK quarantined legacy: own Session; obsolete analysis call lacks tenant/Lead IDs; no final commit | Not activated/refactored; excluded from supported commands |
| Default-organization helper | ACCEPTABLE_LEGACY only as unused development helper; HIGH_RISK if used for customer commands: internal commit and implicit tenant | No active caller found; left unchanged, forbidden for customer commands |
| Bootstrap and historical migration scripts | ACCEPTABLE_LEGACY operator-owned units (`bootstrap_dev_user`, `backend/script/migrate_*`) | Not executed or changed; not customer services |

## Contract and session lifecycle

`backend/database/session.py` creates the canonical engine and SessionLocal factory (`autoflush=False`, `autocommit=False`; default expire-on-commit). `get_db` creates one request Session, yields it and closes it in finally. It never commits in dependency teardown and does not catch/hide the request failure. Closing releases/rolls back remaining query transactions; it is not successful command persistence. The dependency itself is unchanged and tested.

Services receive the existing SQLAlchemy Session directly. There is no new UnitOfWork object, factory, framework or thread/global session. Non-HTTP callers create/close their own Session and call the same services. A Session must not be shared across concurrent threads/tasks; scopes compose sequentially on the same injected Session.

`backend/database/transactions.py:service_transaction` is the minimal shared context manager. The outer service/use case owns the command transaction, commits once on success, and rolls back on validation, repository, commit or unexpected failure (including BaseException cleanup). It adopts SQLAlchemy's autobegun transaction from authorization/query work instead of calling `Session.begin()` on an already active Session. Use a fresh operation Session with no unrelated pending mutations. Do not mix the scope with independently owned `Session.begin`, direct commit/rollback, or close inside it.

Repositories query, add/update and flush where identity/constraints require it. They never commit or silently roll back. Flush is persistence inside the current transaction, not a business commit. Existing organization predicates, unique keys and foreign keys remain unchanged. No repository or registered route contains commit/rollback after E02.

Routes continue to parse HTTP input, resolve authenticated membership/CSRF, call services, translate errors, and set headers/cookies. No route rewrite was needed. ORM expiration may cause response reads after commit; those reads do not authorize another write. A lost response after commit is still possible: this epic does not add command idempotency or exactly-once acknowledgment.

## Nested commands and queries

An outer application use case wraps `with service_transaction(db)` and calls command services with the same Session. Nested scopes join that transaction; they do not create savepoints, commit or roll back independently. An escaping nested failure marks the outer scope rollback-only. Even if caught by the caller, outer exit raises TransactionAborted and rolls back instead of committing partial work. Fresh commands may run after successful rollback. No private Session is opened by these mutation services.

```python
with service_transaction(db):
    lead = LeadService(db).create_lead(company, email, source, organization_id)
    LeadLifecycleService(db).update_status(lead.id, organization_id, "Contacted")
    # Future approved domain/audit/outbox writes could share this transaction.
```

AnalysisService.save_analysis is an explicit caller-owned mutation step; its existing callers/tests own the surrounding transaction. It validates and flushes but does not imply successful durable completion alone. CSV row savepoints are a justified local exception: exact duplicate races can roll back one insert and continue the batch; unexpected errors roll back the whole outer command. They are not nested service commits. sqlite3's legacy transaction mode requires explicit BEGIN before the first row savepoint; PostgreSQL already supplies a real outer transaction.

Query methods (Lead reads/follow-ups, auth resolution/CSRF verification, membership authorization, import preview, intelligence, analytics, Settings/readiness) perform no commits or intentional mutations. With canonical autoflush disabled they do not flush pending writes. Do not invoke query-only service code expecting it to persist a command.

## Processing exception to one transaction per command

AI/provider IO must not hold a business DB transaction. LeadProcessingService.process therefore remains a standalone multi-phase operation, and rejects being called inside an active service transaction before doing any work:

1. Tenant-scoped conditional claim and scalar input snapshot, one commit.
2. Bounded provider reasoning outside a DB transaction.
3. Attempt-fenced completion + linked analysis/history, one atomic commit.
4. On ordinary failure, roll back the failing phase and attempt a separately committed fenced failure marker.

It is intentionally not one transaction across provider IO. A completion failure leaves neither a new analysis nor a completed score; a committed failure marker may remain. A failure-marker error is logged safely and does not replace the original ProcessingFailure classification. If persistence stays unavailable, the previously committed processing lease remains until existing reclaim behavior; no sweeper/worker/outbox is introduced. Hard death or cancellation during provider IO can likewise leave the claim; durable recovery remains later scope. Snapshot and claim are now captured in the same short phase, removing the former read-only commit.

## Failure semantics and logging

The helper emits content-free `transaction.command.failed`, `transaction.rollback.failed` and `transaction.invalidate.failed` events using the existing allowlisted logger. Only exception type and bounded stack file/function/line metadata are included, never exception message, arguments, SQL parameters, password, token, cookie or database credential. Processing emits a separate safe failure-persistence event. Existing HTTP generic failure handling remains unchanged.

If rollback itself fails, log it and attempt Session invalidation without masking the original exception. Discard that operation Session after such a failure; connection invalidation is cleanup, not proof the session is suitable for further business work. A commit transport failure can have an ambiguous durable outcome; rollback cannot prove a remote commit never happened. Future idempotent command/outbox work must address that ambiguity.

Existing service diagnostic completion events can occur for nested commands before the outer commit. They are operational logs, not durable audit evidence; future E05 records must be written inside the command transaction rather than infer commit from logs.

## Future compatibility and remaining debt

The service scope can include future business mutation, audit row, reservation and outbox event in one DB transaction without a repository committing early. This is a structural seam only: no E03+ principal, audit, usage, event, action or Temporal code/table/dependency was added.

No schema/model/API response change, migration, dependency change or frontend change is required. The unused implicit-tenant development helper and incompatible unregistered importer remain quarantined debt. Operator scripts retain their own transaction lifetimes. Actual PostgreSQL concurrency/transport behavior requires separately available disposable PostgreSQL verification; SQLite tests are not a substitute for a new live PostgreSQL run. See the [acceptance report](E02_ACCEPTANCE_REPORT.md) for exact executed checks and limits.
