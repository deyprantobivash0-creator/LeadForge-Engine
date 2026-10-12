# E02 acceptance report

Date: 2026-10-12. Baseline main `3875388f60ca58b698889b25a53620ba50f07afd`. Local review candidate; no commit, push or deployment. Architecture and transaction inventory: [service-owned transactions](E02_SERVICE_OWNED_TRANSACTIONS.md).

**STATUS: PASS for local E02 implementation and the supported backend suite.** Live disposable PostgreSQL verification remains unperformed; this is not deployment approval.

## Change boundary

Production files:

- `backend/database/transactions.py` (new): joined service scopes, one outer commit/rollback, rollback-only nested failures, safe cleanup logging.
- `backend/repositories/lead_repository.py`: three internal commits/refreshes replaced by flushes; tenant predicates unchanged.
- `backend/services/lead_service.py`: service command owns validation, create and commit/rollback; exact duplicate-race classification retained.
- `backend/services/lead_lifecycle_service.py`: service scopes enclose validation and mutation.
- `backend/services/authentication_service.py`: existing commands use joined scopes; issuance/password SQL guards unchanged; nested login/session issuance commits once.
- `backend/services/lead_import_service.py`: confirmation scope covers validation and entire batch; real SQLite outer transaction precedes savepoints.
- `backend/services/lead_processing_service.py`: short phased scopes, atomic claim/snapshot and completion/history; failure-marker errors cannot mask original error; rejects nesting across provider IO.

Tests added: `tests/test_service_transactions.py`. Existing test files unchanged. Documentation added: this report and `docs/v2/E02_SERVICE_OWNED_TRANSACTIONS.md`. No roadmap/masterplan edit.

## Verification evidence

Commands use `.venv-ci/Scripts/python.exe -B -m pytest -p scripts.ci_pytest -q -p no:cacheprovider ... --tb=short` with `LEADFORGE_CI=1`. The supported test conftest selects only disposable SQLite/mock AI and removes dotenv opt-in before application imports. No application is imported against leadforge.db.

- Existing focused regressions: **95 passed in 47.21s** (Lead create conflicts, tenant Leads, workspace, auth, password change, CSV imports, Lead Brain).
- New transaction tests: **22 passed in 5.98s**. A first run had one fixture-only failure because the new fixture used SQLAlchemy's default autoflush rather than canonical `autoflush=False`; aligning it with SessionLocal resolved the failure. No production query behavior was changed to accommodate the test.
- Full backend suite: **464 passed, 40 subtests passed in 110.25s**; no failures/skips. The 2,841 warnings are existing naive-UTC deprecations, not failed checks.
- Dependency consistency: `python -m pip check` passed, no broken requirements.
- Secret scan: existing Gitleaks 8.30.1, repository config, full redaction, limited to the ten E02 files; no leaks found.
- `git diff --check` passes; new files checked separately for trailing whitespace. The Git LF/CRLF notice refers to pre-existing `docs/RENDER_STAGING.md`, not a failed diff check.
- Pre-existing file SHA256 inventory matches outside the six intentionally edited production files. `leadforge.db` is unchanged. `_temporary_staging_login.py` metadata is unchanged; it was neither inspected nor executed. HEAD remains the baseline; the index is empty. No unrelated file content was changed.

New tests prove success commit count, all three repository methods' absence of commit/rollback, nested create/lifecycle atomicity, rollback on validation/database/unexpected errors, rollback-only caught nested failure, commit failure cleanup, rollback failure preserving the original exception with safe logs, tenant mismatch denial, query-only behavior, CSV batch success and rollback after an early released savepoint, nested CSV/later failure, dependency close/error propagation, auth nested login ownership, processing completion/history rollback, secondary failure-marker errors and standalone processing guard. An AST assertion rejects repository/route commit or rollback calls.

Existing auth regressions cover generic invalid credentials, password-change current-session preservation, other-session revocation, account isolation, stale-password issuance rejection, stale legacy hash-upgrade rejection and guarded issuance commit failure. Deterministic race tests pause login after verification, commit a password change on another Session, then resume issuance. The same conditional UPDATE and compare-and-swap SQL remains untouched.

## Self-review and limits

No repository commits/rollbacks or registered route commits/rollbacks remain. No dependency teardown commit was introduced. Duplicate errors are still classified only by the exact tenant/email uniqueness violation. Tenant predicates and auth concurrency guards were inspected unchanged. No query-only commit was added. No separate UoW/session framework was introduced. Rollback failures and failure-marker persistence failures are safely observable; original exceptions are preserved. Processing's multiple phase commits are deliberate to avoid holding a transaction during provider IO, not accidental nested commits.

The default-organization helper retains its unused development-only commit; bootstrap/historical migration scripts retain operator-owned transactions. None was called by this epic. Legacy importer remains unregistered/incompatible and was not activated. PostgreSQL concurrency was not executed: no Docker/PostgreSQL command was available on PATH; no service, credential or infrastructure was created. Existing SQLite race tests passed, but there is no new live PostgreSQL claim.

Migration required: **NO**. No Temporal/Redis/Celery dependency, E03+ table or service, frontend change, staging DB access, Render mutation, commit, push or deployment. The only intended changes are the seven production files, one new test file and two new documentation files listed above. Unrelated pre-existing work must remain outside this scope.
