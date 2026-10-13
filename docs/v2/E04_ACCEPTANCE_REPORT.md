# E04 acceptance report

Date: 2026-10-12. Baseline main `9927177bb11403a0af54d4bd175eb0b6b2c3dbd4`. Local implementation pending review. [Matrix, authorization audit and trust contract](E04_ACTION_PERMISSION_MATRIX.md).

**Initial E04 review: BLOCKED by direct-service authorization bypass. E04-R remediation is implemented locally; renewed security review is required.** No deployment approval or authenticated machine-ingress claim.

## Exact scope

Production additions:

- backend/schemas/action_permission.py: action taxonomy, explicit immutable role mapping, separate frozen human/machine authority contexts, narrowing helper and stable decisions/reasons.
- backend/services/permission_evaluator.py: pure deterministic default-deny evaluator.
- backend/repositories/permission_repository.py: live scalar role lookup scoped to active User/Membership/Organization.
- backend/services/action_permission_service.py: resolves current human authority or explicit machine context, enforces permission, safe denial/logging.

Production edits:

- backend/services/lead_service.py: lead.create at principal command boundary.
- backend/services/lead_lifecycle_service.py: lead.lifecycle.change at principal command boundary.
- backend/services/lead_import_service.py: USER/session-bound principal confirm gate for lead.import and lead.create.
- backend/api/routes/import_routes.py: existing USER principal dependency for canonical confirm; preview unchanged.
- backend/api/routes/lead_routes.py: registered create/lifecycle callers use canonical authorized commands.
- backend/core/logger.py: allowlisted permission/result fields only.

Tests added: tests/test_action_permissions.py (including E04-R direct-call regressions). Tests changed: tests/test_execution_principals.py, tests/test_service_transactions.py, tests/test_lead_create_conflicts.py and tests_postgres/test_postgres_baseline.py. Test authority is operation-specific: creation fixtures get only lead.create, lifecycle fixtures only lead.lifecycle.change; browser import fixtures use actual active membership. Repository tests remain at repository layer. Auth/password/processing implementations and tests are unchanged. Documents created/updated: this report and docs/v2/E04_ACTION_PERMISSION_MATRIX.md. Masterplan/roadmap unchanged.

## Failed gate and remediation

Initial wrappers protected registered HTTP paths but retained public create_lead, update_status, update_lifecycle and confirm methods without authority. The final review correctly rejected that implementation despite passing tests. E04-R puts enforcement on canonical create_lead/update_lifecycle/confirm, removes the wrapper aliases and unused service update_status, and moves unchecked details to _create_lead_internal/_apply_lifecycle_change/_confirm. Import requires lead.import AND lead.create before any row mutation. Mandatory principal binding and default-deny context evaluation apply to direct callers as well as routes.

Private helpers are trusted process implementation details, not supported commands; they do not independently authorize, open a service transaction or commit. Python underscores are not access controls. Arbitrary backend code with a Session is outside this structural command boundary. See the matrix for the exact caller classification and migration inventory.

## E04-R validation (2026-10-13)

**STATUS: PASS for local remediation; renewed independent E04 security review remains required before the separate commit gate.**

- E04: **66 passed** (49 existing + 17 new direct-call regressions).
- E03: **42 passed**. E02: **22 passed**. Combined initial gate: **130 passed in 16.15s**.
- Expanded affected gate: **221 passed in 65.93s**. This selected set differs from the historical 221-test gate; counts alone do not imply identical coverage.
- Password change/concurrency: **23 passed**. Auth API: **13 passed**. Auth foundation: **3 passed**.
- Tenant Lead API: **30 passed**. Tenant attack matrix: **5 passed**.
- CSV API: **3 passed**; atomic batch/savepoint cases also pass in E02. Lead conflict checks: **2 passed**. Observability: **10 passed**.
- Full supported backend: **572 passed, 40 subtests passed in 122.67s**, no failures/skips. Existing naive-UTC deprecation warnings remain.
- pip check: no broken requirements. Existing installed-environment pip-audit: no known vulnerabilities (network-enabled retry after sandbox socket denial). No dependencies changed.
- Gitleaks **8.30.1**: all **17 E04 files**, repository configuration and full redaction, exit **0**. git diff --check and explicit feature-file trailing-whitespace checks pass. Syntax checks include the migrated PostgreSQL test module.
- PostgreSQL direct-call tests were updated but not executed; no local/staging PostgreSQL connection or migration was performed. All executed tests use disposable SQLite and mock providers with the existing CI network guard.
- Fresh E04-R baseline captured before remediation: every inventoried unrelated file retains identical bytes. Only the twelve listed remediation files changed. Operator login script metadata is unchanged; contents were never inspected or executed. leadforge.db SHA256 remains the expected value. Branch main, HEAD and empty index remain unchanged.

### Exact remediation files

Production: backend/services/lead_service.py; backend/services/lead_lifecycle_service.py; backend/services/lead_import_service.py; backend/api/routes/lead_routes.py; backend/api/routes/import_routes.py.

Tests: tests/test_action_permissions.py; tests/test_execution_principals.py; tests/test_service_transactions.py; tests/test_lead_create_conflicts.py; tests_postgres/test_postgres_baseline.py.

Documentation: docs/v2/E04_ACTION_PERMISSION_MATRIX.md; docs/v2/E04_ACCEPTANCE_REPORT.md.

New regression cases: test_canonical_direct_commands_fail_closed (9 cases), test_obsolete_public_mutation_aliases_are_unavailable (3), test_old_integer_only_command_signatures_cannot_mutate (1), test_direct_import_requires_both_permissions_before_any_row (3), test_private_mutation_helpers_join_the_owning_transaction (1). Existing direct human and all four machine-type tests now exercise the canonical names; stale membership, capability narrowing, cross-tenant resource and nested denial rollback tests remain.

### Final command-boundary review

Direct public creation without authority: NO supported bypass. Direct lifecycle/status mutation without authority: NO; old status alias removed. Import without both permissions: NO. Route access to unchecked helpers: NO. Independent helper commit: NO. Current scalar membership lookup remains authoritative for humans; explicit immutable scope remains mandatory for machines, including SYSTEM. Permission enforcement precedes business mutation within the owning E02 scope. Tenant predicates, conflict classification, lifecycle validation and import signature/savepoints are preserved. Processing/read adoption remains debt.

No E05/E10/E11, ActionIntent, migration, Temporal dependency, staging PostgreSQL access, Render operation, staging, commit, push or deployment. No unrelated work was discarded or modified.

## Historical pre-remediation results

All tests use the existing isolated pytest configuration, disposable SQLite and mock AI, with LEADFORGE_CI=1 and no dotenv opt-in. Commands use `.venv-ci/Scripts/python.exe -B -m pytest -p scripts.ci_pytest -q -p no:cacheprovider ... --tb=short`.

- Initial E04 tests: **49 passed in 4.82s**.
- Initial affected E03/E02/import/tenant tests: **97 passed in 23.73s**.
- Expanded focused suite: **221 passed in 59.44s**, including 49 E04, 42 E03 and 22 E02 tests plus auth/password concurrency, tenant, import, processing and logging regressions.
- Full backend: **555 passed, 40 subtests passed in 114.41s**, no failures/skips. The count increases from E03's 506 by 49 new E04 tests. Existing naive-UTC deprecations remain.
- pip check passed; existing pip-audit installed-environment audit found no known vulnerabilities. No dependencies were changed.
- Gitleaks 8.30.1 with repository config/full redaction passed against E04 files; git diff --check and new-file whitespace checks passed.
- Only six existing tracked files were intentionally edited; seven E04 files were added. Unrelated changes retain their original status and diff statistics, and no edit command targeted them. A turn interruption discarded the in-memory initial hash inventory, so a fresh full-file hash comparison is not claimed. HEAD and empty index remain unchanged. The operator login script's metadata matches the established values; its contents were not inspected and it was not executed.

Tests cover all role/action cells; known-role narrowed scope denial; unknown role/action denial; each machine type with/without required capability; target tenant and full principal/run binding; immutable typed capabilities and raw JSON rejection; deterministic decisions; two-hop delegation narrowing/escalation rejection; live human membership and stale ORM revocation; USER context spoofing; non-HTTP protected machine commands; lifecycle capability denial; no mutation/outer partial commit on denial; repository foreign-resource filtering; header/payload role/capability injection; CSV alternate creation path denial. Existing E03 principal, E02 transaction, auth/password concurrency, tenant and observability regressions remain required.

## Self-review

Existing owner/admin/member behavior is preserved for current workspace actions; no known role was arbitrarily restricted or given nonexistent management powers. SYSTEM has no special grant. Role/capability strings are not client-trusted input. USER authority comes from live database predicates, not a supplied context; machine contexts bind the complete principal and a finite typed frozenset. Unknown/unmapped/missing authority denies. Permission checks are inside protected command services, not only HTTP. Repository tenant predicates and E02 transaction ownership remain unchanged.

CSV confirmation was included because it creates Leads through another registered route. Read paths and provider processing were assessed and left on their existing membership boundaries, with explicit migration debt. Unchecked public legacy mutation commands have been removed; only private implementation helpers and low-level repositories remain within the trusted process boundary. Machine root assignment is trusted internal code, not public transport authentication or a persistent/revocable grant store.

No contextual policy, approval, LLM authorization, role redesign, E05 audit ledger, E10 policy engine, E11 logic, ActionIntent, usage/outbox/run table or Temporal code was added. No migration required or created. No staging PostgreSQL access/mutation, Render operation, commit, push or deployment. Unrelated work and the temporary login script remain preserved.

leadforge.db retains established SHA256 `217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a`. No local PostgreSQL or external AI provider was used; environment-secret contents were not read.

E04-R remediation complete locally. Awaiting renewed E04 security review.
