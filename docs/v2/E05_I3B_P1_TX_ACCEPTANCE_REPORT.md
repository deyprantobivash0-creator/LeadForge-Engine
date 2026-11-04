# E05-I3B-P1-TX local acceptance

Date: 2026-10-15. Published parent: 64aa67919be55e7ecd61d2af37390828bee8bcdf.
Status: R5A recoverable implicit-savepoint-flush repair PASS locally; TX remains
unpublished and requires a completely fresh R6 publication review. This is not
publication approval.

Sections A-AA retain pre-R1 implementation evidence. The R1, R2A, R3A, R4A and R5A addenda
record subsequent independent-review blockers, repairs and superseding local results.

## Boundary

Production delta: database/transactions.py, new database/transaction_policy.py,
and CSV transaction plumbing in services/lead_import_service.py only. No schema,
authorization, I3A business semantics, provider or frontend change. P1's three
protected local files are untouched. No lifecycle/import/denial audit adoption.

The authority is registry-backed, not caller-supplied Session.info. Permits bind
the immutable root identity and consume operation stages. SQLite physical roots
are lazy; approved savepoints cannot become outermost transactions. Public
Session/Connection settlement gates complement pre-driver events. Automatic ORM
flush recovery is distinct from application settlement. Fatal violations require
discard; ordinary rollback-only behavior remains. Native/raw DBAPI access is an
unsupported internal escape, explicitly demonstrated by a negative control.

## Verification boundary

Standalone acceptance uses the published baseline plus ONLY TX files in a
temporary snapshot. Frozen unpublished P1 tests deliberately construct unknown
physical roots/unapproved savepoints and are not TX-baseline acceptance tests.
No P1 test is edited or represented as compatible with the new policy. Future
P1 adaptation must retain safe-state and stale-snapshot coverage under governance.

## A. Baseline

Branch main; HEAD and origin/main both 64aa67919be55e7ecd61d2af37390828bee8bcdf;
index empty; sole Alembic head 5d59e6268f43. Database SHA256:
217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a.
The initial inventory records 491 nonprivate files and operator metadata only.

## B-D. Root authority and permits

RootAuthority is immutable and binds a fresh object nonce, Session, root
SessionTransaction, Connection, RootTransaction, driver reference, dialect and
owner thread as execution becomes bound. GovernedRoot holds mutable lifecycle,
rollback-only, policy-broken and physical-state evidence. The private registry
is per Session; Session.info cannot mint or substitute authority. Binding is
lazy, including preservation of no-database-access audit validation failures.

Operation stages cover root commit/rollback, physical BEGIN, savepoint create,
release and rollback. Permits are private ContextVar values, matched against
root nonce, Session, Connection and thread, consumed in sequence and cleared.
They cannot be reused after consumption or root exit. Logical nested scopes
join state without settlement permission. Public method gates are restored to
their original per-instance definitions; listeners are removed deterministically.

## E-H. Physical provenance and fencing

SQLite typed DML first emits infrastructure-authorized deferred BEGIN when
physical state is absent. Reads/empty scopes do not establish physical roots
or reserve writers. Unknown physical state and explicit autocommit fail closed.
PostgreSQL retains native psycopg roots and no SQLite BEGIN. External Connection
ownership and replacement/invalidation cannot silently acquire authority.

Public Session/Connection settlement gates run before logical settlement.
Native commit/rollback/savepoint events and pre-cursor fencing add prevention.
Connection-event violations discard/invalidate the affected unit because its
logical/physical state may differ. Opaque SQL is denied wholesale inside E02,
including comments, case/quoted names and multi-statement smuggling. Savepoint
permits accept only the corresponding exported SQLAlchemy expression class;
they do not authorize reentrant raw COMMIT from another event callback.

## I-J. Trust and failure boundary

Direct DBAPI and native transaction-object manipulation are unsupported runtime
access patterns, not a hostile-Python sandbox. A negative control demonstrates
that driver.commit can make data durable despite a subsequent outer failure.
Static policy prohibits those accesses in application modules. Policy-broken
roots permanently reject further queries, flushes, nesting and savepoints;
caught violations never restore commit capability. Ordinary rollback-only
business failures retain E02 provisional-work behavior. Automatic SQLAlchemy
exception-path ORM flush recovery remains possible without granting caller
Session/Connection rollback authority. Original errors survive cleanup failure.
Commit transport ambiguity remains unresolved; no automatic effect retry.

## K-L. Savepoints and CSV

service_savepoint requires active governance and establishes/verifies a physical
root before managed nesting. A pre-savepoint flush occurs before create permits.
The create permit is consumed before the body; release/rollback permits exist
only for their infrastructure calls. Cleanup failure breaks/discards the root.
CSV no longer inspects the DBAPI, emits BEGIN or directly calls begin_nested.
Preview binding, row evaluation, duplicate classification/counts, invalid rows,
later-row success after expected conflicts and whole-batch failure semantics
remain in LeadImportService. No import audit adoption occurs.

## M. Static policy

The deterministic AST inventory reports path, line, rule ID and symbol. It
handles imported aliases and direct method aliases, transaction calls/objects,
raw connection/cursor access, mode mutation, replacement factories, internal
authority imports and quarantined helper activation. Infrastructure exceptions
are exact path/function pairs. Readiness factory and two literal query
exceptions are limited to migration_heads; model server defaults have exact
literal/declaration exceptions. Operators, migrations and tests are separate
boundaries. This is deliberately not whole-Python semantic analysis.

## N-O. I3A and future P1

I3A production files and semantics are unchanged. Existing create/audit failure,
nested settlement and role-evidence tests remain acceptance gates. An initial
full run found two I2 no-database-access validation regressions; lazy binding
fixed them without changing any I2 file/test. Both targeted regressions pass.
require_governed_physical_root(db) is the Lead-independent future acquisition
seam; P1 retains tenant predicates, refresh, row/writer ownership and its own
safe snapshot sequencing. None of the protected P1 files is adapted here.

## P-Q. Adversarial evidence and negative controls

61 policy cases and 20 architecture cases pass. Coverage includes direct and
native settlement, caught-violation continuation, opaque statements through two
APIs, unknown roots, external/replaced/inactivated Connections, readonly and
empty roots, permit reuse/expiry/cross-Session use, savepoint recovery/failure,
reentrant raw COMMIT, root/Session binding, repeated-root cleanup and SQLite
autocommit. Expected database state is checked by independent observers.
Negative controls demonstrate outermost-savepoint premature durability and
direct DBAPI bypass outside governance; approved-savepoint rollback is the
positive counterpart. Standalone tests do not reference the P1 API.

## R. Required answers

| Q | Answer |
|---|---|
| 1 | RootAuthority, GovernedRoot, Operation and internal _Permit. |
| 2 | Private per-Session registry; context-local operation permits. |
| 3 | NO: Session.info is not an authority source. |
| 4 | ROOT_COMMIT, ROOT_ROLLBACK, PHYSICAL_BEGIN, SAVEPOINT_CREATE/RELEASE/ROLLBACK; cleanup classification. |
| 5 | YES: root nonce, Session, Connection and thread. |
| 6 | NO: consumed/expired permits reject reuse. |
| 7 | NO: cross-Session authority is rejected. |
| 8 | NO: logical nested scopes cannot settle. |
| 9 | Deferred BEGIN before first typed DML, approved savepoint or physical-root request. |
| 10 | NO: no eager physical root. |
| 11 | NO: read-only roots do not reserve the writer. |
| 12 | YES: first write establishes governed root first. |
| 13 | NO: unknown SQLite physical roots are rejected. |
| 14 | YES: raw outermost SAVEPOINT is denied. |
| 15 | NO: caller Session.commit cannot settle during E02. |
| 16 | NO: caller Session.rollback cannot settle during E02. |
| 17 | NO: caller Connection.commit cannot settle. |
| 18 | NO: caller Connection.rollback cannot settle. |
| 19 | NO: raw COMMIT cannot execute. |
| 20 | NO: raw ROLLBACK cannot execute. |
| 21 | NO: raw SAVEPOINT/RELEASE cannot execute. |
| 22 | YES: direct DBAPI commit technically bypasses SQLAlchemy fencing. |
| 23 | YES: explicitly outside supported runtime contract. |
| 24 | YES: raw DBAPI runtime access is statically prohibited. |
| 25 | YES: approved savepoints require a real governed root first. |
| 26 | NO: approved release cannot commit SQLite root. |
| 27 | YES: outer rollback removes released savepoint work. |
| 28 | NO: catching a policy violation cannot restore health. |
| 29 | NO: policy-broken roots reject further business execution. |
| 30 | YES: ordinary rollback-only behavior remains. |
| 31 | YES: safe autobegun reads remain supported. |
| 32 | YES: earlier flushed work remains part of the same root. |
| 33 | YES: CSV's raw BEGIN/DBAPI plumbing was removed. |
| 34 | YES: CSV row semantics remain. |
| 35 | YES: I3A atomicity remains. |
| 36 | YES: protected P1 files untouched. |
| 37 | YES: require_governed_physical_root has no Lead coupling. |
| 38 | YES: PostgreSQL avoids SQLite BEGIN mechanics. |
| 39 | YES: 10 new PG tests; 99 standalone total collected. |
| 40 | LOCAL POSTGRES EXECUTION: NOT RUN; no local command available. |
| 41 | NO schema change. |
| 42 | NO migration. |
| 43 | NO E03 source change. |
| 44 | NO E04 source change. |
| 45 | NO I2 source change. |
| 46 | NO I3A production change. |
| 47 | NO lifecycle audit. |
| 48 | YES: narrow classified AST exceptions. |
| 49 | YES: raw DBAPI negative control demonstrates the boundary. |
| 50 | YES: local invariants, complete standalone backend and preservation gates pass; independent publication review and later exact-SHA PostgreSQL CI remain required. |

## S-U. Execution results

Expanded focused selection: 350 passed, 2,226 existing UTC deprecation warnings.
After lazy binding, 104 targeted cases passed, including both I2 regressions,
E02 and then-current TX tests. Final policy/architecture selection: 81 passed,
121 UTC warnings. No skips. Final complete standalone backend: 1,174 passed,
zero skipped, 3,437 UTC deprecation warnings in 157.77 seconds. All seven final
Python candidate files match the tested snapshot byte-for-byte. The snapshot
contains the published repository implementation, with Git checkout line-ending
normalization, and no unpublished P1 code.

Count reconciliation: published backend baseline 1,093; new TX policy 61 and
architecture 20 give expected standalone collection 1,174. Historical worktree
1,168 included 15 unpublished P1 cases and 60 unrelated untracked Render cases;
its 40 unittest subtests belong to untracked Render diagnostics. Those are not
part of the user-approved published-baseline-plus-TX snapshot. No test is edited
or skipped to change its security assertion.

PG collection: published baseline 89 plus 10 TX = 99. The frozen unpublished P1
PG file adds five only in the current worktree. No local PG execution is claimed;
exact-SHA PostgreSQL CI runtime is mandatory at a later publication gate.

## V-W. Quality and documentation

Dependency consistency and installed-environment vulnerability audit passed;
no dependencies were installed. Final seven-file compile, tracked/new-file
whitespace and exact-ten-file redacted Gitleaks checks pass. ADR-002 and the E02 contract
amendment describe the implemented boundary. Historical E02 acceptance remains
unchanged. No runtime/deployment guarantee is claimed from a local PASS.

## X. Exact TX delta

1. backend/database/transactions.py
2. backend/database/transaction_policy.py (new)
3. backend/services/lead_import_service.py
4. tests/test_transaction_policy.py (new)
5. tests/test_transaction_architecture.py (new)
6. tests_postgres/test_transaction_policy.py (new)
7. tests_postgres/test_postgres_baseline.py (typed PID query only)
8. docs/v2/adr/ADR-002-TRANSACTION-GOVERNANCE.md (new)
9. docs/v2/E02_SERVICE_OWNED_TRANSACTIONS.md
10. docs/v2/E05_I3B_P1_TX_ACCEPTANCE_REPORT.md (new)

Existing tests/test_service_transactions.py required no changes.

## Y-AA. Preservation, Git and operations

Final inventory: four existing files intentionally modified; six TX files new.
All other 487 nonprivate baseline files are byte-identical, including all three
protected P1 files. Their hashes match the task's expected values. Database hash,
HEAD, origin/main and Alembic head match section A; index remains empty. Operator
metadata is unchanged; its contents were never inspected or executed. No source
file outside the three authorized production paths is changed by TX.

No stage, commit, push, migration, staging database access, Render operation,
deployment, dependency installation or Temporal operation occurred. No P1
adaptation, lifecycle audit, import audit, denial audit, I3B/I3C/I4/I5 or E06+
implementation was started.

Final `git status --short` (unrelated pre-existing work remains present):

```text
 M Dockerfile
 M backend/database/transactions.py
 M backend/repositories/lead_repository.py
 M backend/services/lead_import_service.py
 M deploy/render/provision.py
 M docs/CONFIGURATION.md
 M docs/RENDER_STAGING.md
 M docs/STEP_5F_VERIFICATION.md
 M docs/v2/E02_SERVICE_OWNED_TRANSACTIONS.md
 M tests_postgres/test_postgres_baseline.py
?? _temporary_staging_login.py
?? backend/database/transaction_policy.py
?? deploy/render/database_identity.py
?? deploy/render/preflight.py
?? docs/STEP_5H_B_REMOTE_VERIFICATION.md
?? docs/STEP_5H_B_SCHEMA_READINESS_DIAGNOSIS.md
?? docs/STEP_5H_B_VERIFICATION.md
?? docs/v2/E05_I3B_P1_TX_ACCEPTANCE_REPORT.md
?? docs/v2/adr/ADR-002-TRANSACTION-GOVERNANCE.md
?? package-lock.json
?? package.json
?? tests/test_lead_lifecycle_locking.py
?? tests/test_render_database_identity.py
?? tests/test_render_preflight_diagnostics.py
?? tests/test_transaction_architecture.py
?? tests/test_transaction_policy.py
?? tests_postgres/test_lead_lifecycle_locking.py
?? tests_postgres/test_transaction_policy.py
```

## R1: savepoint creation failure (2026-10-15)

### A-C. Baseline, reproduction and cause

All ten supplied pre-R1 candidate hashes and all three protected P1 hashes
matched before editing. Branch/HEAD/origin/index, database hash and Alembic head
matched section A. The R1 inventory contains 497 nonprivate files; operator
metadata only was recorded. Environment-file contents were not read.

Independent TX-R review stopped on a confirmed creation-failure defect. Before
repair, R1 reproduced the same SQLAlchemy savepoint-event failure using the
actual candidate and disposable SQLite. The original exception escaped and the
body was not entered, but root.broken and root.failed were both false. The create
permit was cleared. Session/root Connection/physical SQLite transactions remained
active; Session nesting was true while Connection nesting was false.

A caught failure allowed a nested E02 body and a typed Connection UPDATE to run.
ORM query, Session.execute and flush attempts instead encountered later policy
rejection while trying to materialize the orphaned logical nesting. Normal outer
exit also eventually rejected settlement. These later rejections did not meet
the immediate fail-closed contract; the root had incorrectly remained healthy.
Independent observers after forced cleanup saw original data.

Pre-R1 service_savepoint lines 372-375 created/materialized the nested transaction
before its body exception-handling region. Thus Python object creation or
physical SAVEPOINT failure had no mechanism-failure state transition.

### D-G. Repair, flow, state and permits

Only transaction_policy.py production code changed. Creation under the narrow
create permit, Session.begin_nested and db.connection materialization are now
inside try/except BaseException. Failure sets the same broken=True, failed=True
state used by existing savepoint mechanism-failure handlers, then bare re-raises
the original exception. Calling violate() here would replace that exception.
The existing permit context clears its stages and restores the ContextVar in
finally before the creation error escapes. No new error taxonomy or authority
mechanism was added. Physical-root validation and pre-savepoint flush ordering
remain unchanged; application-body recovery starts only after successful create.

Post-fix event-level reproduction: broken=True, failed=True, no active permit or
flush context, body not entered, original exception identity preserved. Logical
and physical transactions can still be active until E02 discards the failed unit;
that state does not authorize continuation. Typed Session and Connection reads,
Connection writes and flush all raised TransactionPolicyViolation. Normal outer
exit raised TransactionAborted, removed root authority and left original data.

### H-M. Regression evidence

Twenty new cases in tests/test_transaction_policy.py cover:

- Eight combinations of Python object/event-level materialization failure,
  ordinary/BaseException escape and no-prior-write/prior-flushed-work roots.
  They check original identity, body tripwire, broken/failed state, permit/flush
  ContextVars, ORM/Session/Connection query rejection, Connection write and flush
  rejection, nested E02 and second-savepoint denial, caller commit denial,
  normal outer abort, listener/method removal and independent-observer state.
- Two fresh empty-Session/root cases, one for each creation phase.
- Two uncaught event-level creation failures with injected invalidation failure,
  proving original ordinary/BaseException escapes survive cleanup noise.
- One real nested LeadService create plus audit append/flush followed by caught
  creation failure: both provisional Lead and audit disappear on outer abort.
- One caught RELEASE failure that still permanently breaks the root.
- Six creation-event reentrancy attacks: raw COMMIT, ROLLBACK, RELEASE, SAVEPOINT,
  Session.commit and Connection.rollback; create permits authorize none of them.

The existing successful savepoint, released-work outer rollback, recoverable
duplicate/body exception, rollback-cleanup failure, and reentrant-release tests
remain unchanged and pass. No prior test function/assertion was weakened.

Negative control: two new event-materialization regressions ran against the
unchanged pre-R1 production module in a temporary snapshot. Both failed at
root.broken=False. The production repair was applied only after this evidence;
the fixed candidate passes the same assertions. The control never disabled the
fix in the worktree.

### N. R1 required answers

| Q | Answer |
|---|---|
| 1 | Pre-R1 service_savepoint lines 372-375 were before the protected body region. |
| 2 | YES: independently reproduced before editing production. |
| 3 | Catch BaseException around creation/materialization, mark broken+failed, re-raise. |
| 4 | YES: both creation phases are protected. |
| 5 | YES: broken=True. |
| 6 | YES: failed=True, matching existing mechanism-failure state. |
| 7 | YES: create permit and flush ContextVar clear. |
| 8 | NO: body tripwire remains false. |
| 9 | NO: post-failure ORM query rejects. |
| 10 | NO: SQL writes/flush reject. |
| 11 | NO: nested E02 rejects before body. |
| 12 | NO: a second savepoint rejects before body. |
| 13 | NO: caller commit rejects and normal outer exit aborts. |
| 14 | YES: prior flushed work rolls back. |
| 15 | YES: independent observers see original data. |
| 16 | YES: original object identity survives, including cleanup failure. |
| 17 | YES: existing success/released-work rollback tests pass. |
| 18 | YES: valid-savepoint duplicate/body failures still recover. |
| 19 | YES: caught release failure remains fatal. |
| 20 | YES: existing rollback-cleanup regression passes. |
| 21 | NO: all six creation reentrancy attacks reject. |
| 22 | NO transactions.py change in R1. |
| 23 | NO LeadImportService change in R1. |
| 24 | NO P1 change. |
| 25 | NO lifecycle audit. |
| 26 | NO schema change/migration. |
| 27 | YES: 1,194 backend cases pass, zero skips. |
| 28 | YES: 10 TX / 99 total PostgreSQL cases collect. |
| 29 | NO staging/deployment. |
| 30 | YES: ready for a fresh independent review, not approved for publication. |

### O-R. Fresh execution and quality

The user-approved standalone boundary remains published baseline plus exactly
the ten TX files in a temporary git-archive snapshot. Frozen local P1 and
unrelated unpublished files were not overlaid. All seven final Python candidate
files match the tested snapshot byte-for-byte. Tests use disposable SQLite and
mock AI, Python -B, no pytest cache, scripts.ci_pytest and no-skips enforcement.

| Gate | Result |
|---|---|
| Policy file, then two added empty-root cases | 79 + 2 passed; 158 + 4 UTC warnings |
| Architecture / existing E02 | 20 + 22 passed; 102 warnings |
| CSV API / I3A create-audit | 3 + 26 passed; 240 warnings |
| Auth/password/session/processing/tenant/E03/E04 | 224 passed; 1,869 warnings |
| Final complete backend | 1,194 passed, 0 skipped, 0 failures/errors; 3,478 warnings; 165.05 seconds |
| PostgreSQL collection | 10 TX cases; 99 total; unchanged |
| Local PostgreSQL runtime | NOT RUN: no available local commands or disposable URL |
| Compile / whitespace | Modified Python compiles; candidate whitespace and git diff --check pass |
| Gitleaks | Exact ten-file candidate, repository configuration, full redaction; no findings |
| pip check / installed dependency audit | No broken requirements / no known vulnerabilities; no installation |

The final backend JUnit records all 81 policy cases, including the two late-added
empty-root cases. Count reconciliation: pre-R1 1,174 + 20 new cases = 1,194;
equivalently published 1,093 + policy 81 + architecture 20. No relevant skip or
subtest count is used to conceal a failure. PostgreSQL collection is not runtime
verification; exact-SHA PostgreSQL CI remains a later publication requirement.

### S-X. Documentation, exact delta and preservation

R1 changes exactly three existing candidate paths: transaction_policy.py,
tests/test_transaction_policy.py and this acceptance report. There is no eleventh
publication path. ADR-002/E02 contract and architecture are unchanged. This
addendum supersedes pre-R1 readiness and test-count claims; the independent TX-R
review must restart from the beginning because it stopped at the first defect.

Seven protected TX paths retain these exact pre-R1 hashes:

| Path | SHA256 |
|---|---|
| backend/database/transactions.py | 2cf3ab5cc15bffe8a92354d39711c71f0262e7c74439567a9dbe13a7f5eb3d9a |
| backend/services/lead_import_service.py | d7ccdd04721602259d24095195a4dddcf5252fe4d485d73c41bb7e0da6d6c1d8 |
| docs/v2/E02_SERVICE_OWNED_TRANSACTIONS.md | 7d54e811d97fcac7a17e1687930ad98807d8723a939d402882fcb1bac3adedba |
| docs/v2/adr/ADR-002-TRANSACTION-GOVERNANCE.md | e4468bb62a9ad1d63fd488fe876a36e8810d3dc6d7026b3ec29726a22a456894 |
| tests/test_transaction_architecture.py | b6ff11edd1aad3f6d0bd58e9917699c4536d8a1c37d4fcc8c90bff066d6b0e43 |
| tests_postgres/test_postgres_baseline.py | 7f4e170b4cc213b2345c9a83acf005366185e80902ccdf7827ccbe5ee23de171 |
| tests_postgres/test_transaction_policy.py | ceaac9c1ac85a9ce5d2c968ad72cbc6192f0add4978d4dd220499e3fc86fa326 |

The other 494 nonprivate R1-baseline files are byte-identical, with no new files.
All three P1 hashes match their required values. Database hash, main/HEAD/origin,
empty index and Alembic head still match section A. Operator metadata is unchanged;
its contents were never inspected/executed. Final git status is identical to the
full status block above, which already listed these untracked candidate files.

No stage, commit, push, P1 adaptation, lifecycle/import/denial audit, schema change,
migration, staging DB, Render, deployment, dependency installation, I3B/I3C/I4/I5,
E06+ or Temporal work occurred. TX remains local/unpublished and is not closed.

## R2A: lexical relative-import enforcement (2026-10-15)

### A-C. Baseline, reproduction and root cause

All ten supplied current TX hashes and all three protected P1 hashes matched
before editing. Branch main, HEAD/origin, empty index, Alembic head and database
hash matched section A. The pre-R2A inventory contains 497 nonprivate files and
operator metadata only; environment-file contents were not read.

Fresh R2 review found that ImportFrom used node.module while ignoring node.level
and the scanned file's package. R2A independently reproduced the defect before
editing: relative organization/current_root imports from a backend/services file
returned no findings; equivalent absolute imports returned TX-QUARANTINE and
TX-AUTHORITY respectively. No quarantined module was imported or executed.

### D-G. Lexical resolution algorithm

Only tests/test_transaction_architecture.py changed for the repair. The scanner
normalizes backslashes to forward slashes and uses PurePosixPath for consistent
repository-relative comparisons and findings. module_and_package removes .py,
joins path components with dots, and represents package __init__.py as its parent
package. For ordinary modules the package excludes the filename; for __init__ it
is the module itself.

resolve_import_from leaves level=0 absolute imports unchanged. Level=1 starts
from the current package; level=N ascends N-1 parents before appending module.
When module is None it returns that package target, and the existing alias/name
checks evaluate any imported submodule. An excessive level or relative import
without a parent package returns a deterministic TX-IMPORT finding, never an
incorrect allowed target. It uses no filesystem discovery or target-module load.

Existing ImportFrom rules and alias tracking now receive the resolved absolute
target. Absolute ast.Import handling, infrastructure allowlists, quarantine
targets and all existing classification sets are unchanged. Parent-package
imports that were already allowed remain allowed; no new descendant-attribute
analysis or whole-Python semantic claim is introduced.

### H-K. Import regressions

Sixty added cases cover module/package derivation, levels 0/1/2/3 and excessive
levels, root/package initializers, module=None, Windows/POSIX paths, absolute and
relative organization/init_db/ingestion quarantine targets, historical script
targets, aliases, package-to-submodule imports, unchanged absolute Import syntax,
benign imports, public transaction APIs and alias-fed factory detection.

The ten locally defined policy symbols prohibited through that import surface
are Operation, RootAuthority, _Permit, _permit, _flushing, _roots, _MISSING,
current_root, GovernedRoot and service_savepoint. Each is tested in absolute,
relative and aliased-relative forms. The existing two allowed direct imports,
require_governed_physical_root and TransactionPolicyViolation, remain allowed.
Whole transaction_policy/transactions module imports remain prohibited as before.

Import/loading tripwires and an unconditional raise in synthetic analyzed source
prove the scanner does not execute that source or import target modules. New
quarantine and private-authority regressions also fail against the saved old
scanner, proving they detect the original bypass. Ninety independent comparisons
against importlib.util.resolve_name agree, without loading any target module.

### L-M. Actual scans, acceptance boundary and determinism

The user explicitly confirmed R2A acceptance should use the previously approved
published-baseline-plus-TX snapshot, with unchanged frozen P1 findings reported
separately. No P1 exclusion or exception was added to scanner code.

| Source tree | Files scanned after existing classifications | Findings |
|---|---|---|
| Published baseline + exactly ten TX files | 142 | 0 |
| Complete current worktree, before and after repair | 143 | Same 3 protected-P1 findings |

The current-worktree findings are backend/repositories/lead_repository.py line 80
TX-CONTROL connection; line 83 TX-CONTROL connection; line 83 TX-RAW
driver_connection. They predate R2A, are unchanged, and belong to the unadapted,
unpublished P1 candidate. Relative resolution reveals no new runtime violations.
The extra scanned worktree file is ignored backend/logs/__init__.py. Neither
tree's findings are hidden or represented as a clean full-worktree result.

Findings retain sorted, deduplicated (path, line, rule, target) tuples. Equivalent
absolute/relative imports and Windows/POSIX source paths produce identical policy
results. The original runtime scan, synthetic checks and bound-SQL test functions
are unchanged. All six existing policy classification constants are unchanged.

### N. R2A required answers

| Q | Answer |
|---|---|
| 1 | ImportFrom ignored level/package and compared an unresolved node.module. |
| 2 | YES: relative misses and absolute detections reproduced before editing. |
| 3 | Normalize separators, strip .py, join components; __init__ maps to package. |
| 4 | 0 absolute; 1 current package; N ascends N-1 parents. |
| 5 | YES. |
| 6 | YES. |
| 7 | YES: module=None retains the resolved package for imported-name checks. |
| 8 | YES: deterministic TX-IMPORT, without crashing or loading code. |
| 9 | YES. |
| 10 | YES. |
| 11 | YES. |
| 12 | YES. |
| 13 | YES. |
| 14 | YES: absolute checks and classification constants unchanged. |
| 15 | YES: benign/public relative imports remain allowed. |
| 16 | NO: whole transaction_policy module import remains prohibited. |
| 17 | NO: organization submodule import remains quarantined. |
| 18 | NO: lexical AST/path analysis only; execution/loading tripwires pass. |
| 19 | YES: sorted deterministic findings. |
| 20 | YES: Windows/POSIX paths and package initializers tested. |
| 21 | No new approved-runtime violation: 142 files / 0 findings; the explicitly excluded frozen P1 retains 3 reported findings in the 143-file worktree scan. |
| 22 | NO production file changed. |
| 23 | NO runtime transaction behavior changed. |
| 24 | NO P1 change. |
| 25 | NO lifecycle audit. |
| 26 | YES: 1,254 complete standalone backend tests pass, zero skips. |
| 27 | YES: 10 TX / 99 total PG cases collect. |
| 28 | NO migration/staging/deployment. |
| 29 | NO publication approval. |
| 30 | YES: local repair gates pass under the user-confirmed acceptance boundary; a fresh full independent TX review is still required. |

### O-R. Fresh verification

| Gate | Result |
|---|---|
| Architecture file | 80 passed (20 original + 60 new), 0 skips, 0.35 seconds |
| Policy + existing E02 | 103 passed (81 + 22), 0 skips, 264 UTC warnings, 27.90 seconds |
| Complete backend | 1,254 passed, 0 skipped, 0 failures/errors, 3,478 UTC warnings, 167.84 seconds |
| PG collection | 10 TX / 99 total; unchanged; runtime NOT RUN locally |
| Quality | Changed test compiles; git diff --check and candidate whitespace pass |
| Gitleaks | Exact ten-file candidate, repository config, full redaction; no findings |
| Dependencies | pip check passes; installed dependency audit reports no known vulnerabilities; no installation |

Count reconciliation: R1 1,194 + 60 scanner cases = 1,254. New static cases add no
database warnings, so 3,478 warnings is unchanged. Tests use the user-confirmed
temporary published-baseline-plus-TX snapshot, Python -B, no pytest cache,
scripts.ci_pytest and no-skips enforcement. All seven candidate Python files
match the tested snapshot byte-for-byte. No relevant skip or historical result
substitutes for a fresh run. PostgreSQL runtime/exact-SHA CI remains future scope.

### S-X. Evidence update, exact delta and preservation

R2A changes exactly tests/test_transaction_architecture.py and this acceptance
report. No new repository file or eleventh publication path was introduced. No
production code, R1 behavior, ADR-002, E02 runtime contract or PostgreSQL tests
changed. All eight protected non-R2A TX paths retain their supplied hashes.

The other 495 inventoried nonprivate files are byte-identical. All three P1 hashes
match their required values. HEAD/origin remain the published parent, index is
empty, Alembic/database identity matches section A, and operator metadata is
unchanged. Its contents were not inspected/executed. Final Git status remains
identical to the complete block above; pre-existing unrelated work is preserved.

No production behavior change, stage, commit, push, P1 adaptation, lifecycle/
import/denial audit, migration, staging DB, Render, deployment, dependency install,
I3B/I3C/I4/I5, E06+ or Temporal work occurred. TX remains local/unpublished; the
repaired candidate needs a fresh full independent review from the beginning.

## R3A: compiled-executable transaction and DDL fence (2026-10-15)

### A-C. Baseline, fresh reproduction and root cause

All ten supplied pre-R3A TX hashes and all three P1 hashes matched before edits.
Main, HEAD/origin 64aa67919be55e7ecd61d2af37390828bee8bcdf, empty index, sole
Alembic head 5d59e6268f43 and the section-A database hash matched. The baseline
inventory contains 497 nonprivate files; operator contents and dotenv were not read.

Fresh R3 found a material blocker, independently reproduced again for R3A before
production edits: typed provisional UPDATE followed by Session.execute(DDL("COMMIT"))
reached the driver, and an independent observer saw changed after outer failure.
The equivalent text("COMMIT") control was denied and the observer saw original.
The pre-fix scanner returned zero findings for the DDL constructor source.

| State immediately after attempt, before cleanup | Pre-fix DDL | Text control | Repaired DDL |
|---|---|---|---|
| root.broken / root.failed | false / false | true / true | true / true |
| Session active / in_transaction | true / true | true / true | true / true |
| Connection closed / invalidated | false / false | false / false | false / false |
| Connection in_transaction / root active | true / true | true / true | true / true |
| DBAPI in_transaction | false | true | true |
| COMMIT reached driver | yes | no | no |
| Observer after root exit | changed | original | original |

The cursor fence previously rejected only uncompiled SQL and TextClause. DDL
produced context.compiled.statement of public type sqlalchemy.sql.ddl.DDL, so it
passed that condition despite emitting the same COMMIT. Logical SQLAlchemy state
remained active after physical durability, making later rollback ineffective.

### D-F. Representation-independent runtime repair and DDL policy

Only backend/database/transaction_policy.py changes production behavior. Every
governed before_cursor_execute now classifies the actual emitted SQL, including
custom compiled executables, before any driver execution. A single lexical helper,
_restricted_sql_commands, identifies transaction and schema command heads across
semicolon-separated statements, skipping ordinary quoted literals/identifiers,
dollar-quoted literals and comments. It handles case, whitespace, CR/LF comments
and trailing semicolons. Unclosed/ambiguous quoting and nested block comments fail
closed; single-quoted backslash escapes are rejected because dialect modes differ.
This is a conservative lexical fence, not a general SQL parser or Python sandbox.
There was no existing SQL lexer/classifier to reuse; no dependency was added.

Transaction forms include BEGIN, START TRANSACTION, COMMIT/END, ROLLBACK/ABORT,
SAVEPOINT, RELEASE, ROLLBACK TO, PREPARE TRANSACTION and SET transaction/autocommit
controls. Schema command heads are denied too, so a custom compiler cannot emit
CREATE/ALTER/DROP/TRUNCATE/COMMENT/GRANT/REVOKE as an alternative DDL wrapper.

Public ExecutableDDLElement provides a second blanket DDL boundary: DDL,
CreateTable/DropTable, CreateIndex/DropIndex and other subclasses are rejected
even when their emitted SQL is harmless SELECT. No type-name string matching or
SQLAlchemy private type is used. Existing opaque text/driver SQL restrictions
remain. This policy exists only on the governed Session's bound Connection;
ordinary disposable schema setup outside governance remains executable.

### G-J. Infrastructure, typed SQL, broken state and observer proof

Infrastructure controls require the matching command, operation, authority and
remaining permit stage. Deferred SQLite BEGIN still requires exact BEGIN SQL;
savepoint statements retain exact SQLAlchemy clause-class/stage checks and must
match SAVEPOINT, RELEASE or ROLLBACK TO respectively. No permit spans business
code, and no broad fence-disable scope was introduced.

Typed SELECT/functions/INSERT/UPDATE/DELETE, ORM reads/flush, lazy first physical
BEGIN, approved savepoint release and row-error rollback pass. DDL settlement
attempts set broken and failed before execution. Caught violations deny ORM and
typed queries, Connection queries/writes, flush, caller commit, nested E02 and
another savepoint. Normal outer exit aborts; forced outer failure preserves its
exception. In both cases the observer sees original, no COMMIT reaches the driver,
and the root authority is removed. Raw DBAPI remains outside this interception
contract; its existing negative-control regression is unchanged and passes.

### K-N. Static policy and prior repair regressions

TX-DDL flags constructor use at its source line, including direct/aliased DDL,
sqlalchemy.DDL, aliased namespaces, sqlalchemy.schema/sql.ddl imports and statement
assignment before execute. The known public executable DDL constructor inventory
contains 19 symbols, checked against installed SQLAlchemy 2.0.51's public schema
surface. Ordinary Table/Column/metadata/types and typed query constructors remain
allowed. This is obvious import/constructor analysis, not arbitrary Python taint
tracking. Findings remain sorted and deterministic on Windows/POSIX paths.

The new observer regressions fail against the saved old production policy. A new
DDL scanner regression fails against the saved old scanner, which returns no
finding. All existing scanner test functions, both relative-resolution helpers,
and all six old classification sets remain AST-identical. The private-symbol
inventory adds only the new helper (11 locally defined prohibited symbols now).
R1's original policy tests and R2A's original scanner cases all pass.

### O-P. Actual scans and approved acceptance boundary

| Tree | Runtime files scanned | Findings |
|---|---|---|
| Published baseline + exact ten TX files | 142 | 0 |
| Complete dirty worktree | 143 | Exactly the same three frozen P1 findings |

The findings are lead_repository.py:80 TX-CONTROL connection; :83 TX-CONTROL
connection; :83 TX-RAW driver_connection. Reversed traversal produces identical
sorted findings. No P1 exception, suppression, adaptation or new runtime DDL
usage was found. The extra dirty-worktree file remains backend/logs/__init__.py.

### Q. Required R3A answers

| Q | Answer |
|---|---|
| 1 | The fence checked uncompiled/TextClause representations, letting compiled DDL through. |
| 2 | YES: fresh pre-edit provisional durability and text control reproduced. |
| 3 | YES: emitted SQL classification is independent of originating statement type. |
| 4 | YES: every governed cursor execution is classified before the driver. |
| 5 | NO: DDL COMMIT is denied. |
| 6 | NO: DDL ROLLBACK is denied. |
| 7 | NO: DDL BEGIN is denied. |
| 8 | NO: DDL SAVEPOINT is denied. |
| 9 | NO: DDL RELEASE is denied. |
| 10 | NO: DDL ROLLBACK TO is denied. |
| 11 | NO: comments/case/whitespace do not bypass the fence. |
| 12 | NO: arbitrary public executable DDL is denied in governed runtime. |
| 13 | YES: authorized deferred BEGIN passes. |
| 14 | YES: approved savepoint release/recovery passes. |
| 15 | YES: typed SELECT/functions pass. |
| 16 | YES: typed INSERT/UPDATE/DELETE pass. |
| 17 | YES: ORM flush passes. |
| 18 | YES: root broken and failed. |
| 19 | NO: caught violation cannot resume business SQL. |
| 20 | YES: independent observer sees original. |
| 21 | YES: TextClause COMMIT remains denied. |
| 22 | YES: exec_driver_sql COMMIT remains denied. |
| 23 | YES: TX-DDL detects the runtime constructor source. |
| 24 | YES: obvious import/namespace aliases and constructor assignment covered. |
| 25 | YES: relevant public schema DDL constructors covered. |
| 26 | YES: normal typed SQLAlchemy imports/declarations remain allowed. |
| 27 | YES: original R2A cases pass and resolution helpers are unchanged. |
| 28 | YES: original R1 creation fail-closed tests pass. |
| 29 | 0 approved-snapshot findings. |
| 30 | YES: all three frozen P1 findings remain visible. |
| 31 | NO production file besides transaction_policy.py changed. |
| 32 | NO P1 change. |
| 33 | NO lifecycle/import/denial audit. |
| 34 | NO application schema change or operational migration/staging/deployment. |
| 35 | YES: 1,442 full backend cases pass, zero skips. |
| 36 | YES: 10 TX / 99 total PostgreSQL cases collect. |
| 37 | NO: TX is not publication-approved. |
| 38 | YES: ready for completely fresh R4 review after local gates; not publication approval. |

### R-U. Fresh final verification

| Gate | Final result |
|---|---|
| Policy / architecture / E02 | 232 + 117 + 22 = 371 passed; 0 skips; 539 warnings; 63.80 seconds |
| CSV/security + I3A | 49 passed; 0 skips; 240 warnings; 10.33 seconds |
| Auth/password/session, processing, Lead API, tenant attacks | 102 passed; 0 skips; 1,693 warnings; 54.34 seconds |
| Full backend | 1,442 collected/passed; 0 failed/errors/skips; 3,753 warnings; 203.56 seconds |
| PostgreSQL collection | 10 TX / 99 total, unchanged; both collection commands exit 0 |
| PostgreSQL runtime | NOT RUN locally: no disposable configuration or local docker/postgres/pg_ctl tool |
| Quality | git diff --check, all ten-file whitespace checks, seven Python compilations pass |
| Gitleaks | Exact ten-file candidate with repository config/full redaction: 0 findings |
| Dependencies | pip check passes; installed dependency audit: no known vulnerabilities; no install |

Counts reconcile exactly: 1,254 + 151 policy cases + 37 architecture cases = 1,442.
The 37 architecture additions include one private-helper parameter case. No
existing tests were removed or skipped. The final snapshot uses published HEAD
plus exactly the ten TX candidates, not dirty P1. Tests use Python -B, mock AI,
scripts.ci_pytest, no pytest cache and mandatory no-skips enforcement. All seven
candidate Python files match the tested snapshot byte-for-byte. PostgreSQL runtime
and exact-SHA CI remain pending a future publication review; collection is not
runtime proof. Existing migration regressions use disposable test databases only.

### V-AA. Evidence update, exact delta and preservation

R3A modifies exactly transaction_policy.py, test_transaction_policy.py,
test_transaction_architecture.py and this acceptance report. No eleventh TX
publication path is introduced. ADR-002/E02 contract and all six other TX files
retain their supplied hashes. The three changed Python SHA256 values are:

| File | SHA256 |
|---|---|
| backend/database/transaction_policy.py | b27501fb2c13fd0164bc10a02b7b83c238d62b95fad531630ed5526148bbd91a |
| tests/test_transaction_policy.py | a5941f5984334dfe02de333332b7799a04d4c105b31231a8d2e0b88af0d2d0e2 |
| tests/test_transaction_architecture.py | 4f2acf9d30e497542e148aff71b8882fff9c5696ffb562bf53503cf37d65e575 |

All three P1 hashes, the other 493 inventoried nonprivate files, HEAD/origin,
empty index, Alembic head, database hash and operator metadata remain unchanged.
No files were added/deleted; final Git status remains the complete block above.
The operator script was not inspected/executed. Unrelated work is preserved.

No stage, commit, push, P1 adaptation, lifecycle/import/denial audit, schema change,
operational migration, staging DB, Render, deployment, dependency installation,
I3B/I3C/I4/I5, E06+ or Temporal work occurred. TX remains local/unpublished and
requires a completely fresh R4 independent publication review.

## R4A: recovery-permit lifetime and ContextVar cleanup (2026-10-15)

### A. Baseline

Branch main; HEAD and origin/main both
64aa67919be55e7ecd61d2af37390828bee8bcdf; index empty; sole Alembic head
5d59e6268f43. All ten supplied R4 candidate hashes and all three protected P1
hashes matched independently before editing. The database SHA256 remains
217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a.
The preservation inventory records 498 nonprivate files and operator metadata
only. Neither private dotenv nor operator contents were read.

### B-C. Independent reproduction and root cause

Before any production edit, the actual candidate reproduced the R4 path using a
disposable SQLite file and a public before_insert mapper event:

service_transaction -> service_savepoint -> ORM flush ->
connection.execute(DDL("COMMIT")) -> TransactionPolicyViolation -> SQLAlchemy
rollback-savepoint recovery -> broken-root cursor rejection -> E02 teardown.

Observed after complete E02 cleanup:

| State | Pre-R4A observation |
|---|---|
| current_root | None |
| current permit | Present, SAVEPOINT_ROLLBACK |
| remaining stages | ["savepoint_sql"] |
| flush context | None |
| Session transaction / active | False / True |
| Connection closed / invalidated / in_transaction | True / False / False |
| DBAPI state | Closed; reading in_transaction raises ProgrammingError |
| Independent observer rows | 0 |

Both a subsequent root on the same Session and a subsequent root on a different
Session, in the same execution context, then raised TransactionPolicyViolation.
The stale permit remained the same object. The next first-write PHYSICAL_BEGIN
permit was rejected because another permit was still installed. No accidental
authorization or durable insert was observed.

The rollback_savepoint callback installed a recovery permit without retaining
its reset token. The cursor called check() before consuming savepoint_sql;
broken-root rejection therefore left that stage unconsumed. Flush finally only
cleared exhausted permits, and root removal had no permit cleanup. Data rollback
succeeded, but authorization context survived root destruction.

Negative control: after adding the permanent regression, its same-Session case
was run in the saved pre-R4A snapshot, before production edits. It failed at the
post-cleanup `_permit.get() is None` assertion with exactly the leaked
SAVEPOINT_ROLLBACK / ["savepoint_sql"] value. Production was never weakened to
perform this control.

### D-E. Permit inventory and lifetime model

Permits are both context-scoped authorization and mutable ordered capabilities.
Nonce, Session, Connection, owner thread, lifecycle and operation checks still
precede stage consumption. consume() removes the next expected stage; teardown
revokes all remaining stages, including unconsumed ones.

| Operation / caller | Ordered stages | Lifetime owner after R4A |
|---|---|---|
| ROOT_COMMIT / GovernedRoot.commit | session_commit_api, session_commit, connection_commit | permit() finally; root backstop |
| ROOT_ROLLBACK / GovernedRoot.rollback | session_rollback_api, connection_rollback | permit() finally; root backstop |
| PHYSICAL_BEGIN / ensure_physical | begin_sql | permit() finally; root backstop |
| SAVEPOINT_CREATE / service_savepoint | session_savepoint_api, connection_savepoint_api, savepoint_create, savepoint_sql | permit() finally; root backstop |
| SAVEPOINT_RELEASE / service_savepoint | session_commit, savepoint_release, savepoint_sql | permit() finally; root backstop |
| SAVEPOINT_ROLLBACK / service_savepoint | savepoint_rollback, savepoint_sql | permit() finally; root backstop |
| SAVEPOINT_ROLLBACK / ORM flush recovery callback | savepoint_sql | guarded flush finally; root backstop |
| CLEANUP | Existing guard classification; no minting caller | Unchanged |

Every pre-repair ContextVar mutation was audited:

| Pre-R4A mutation | Previous token ownership | R4A disposition |
|---|---|---|
| _permit.set(p) in permit() | Captured and reset in finally | Centralized in open_permit; token retained by root-owned scope |
| _permit.set(recovery) in rollback_savepoint | Token discarded; consumption assumed | Removed; callback uses the same tracked permit creation |
| _permit.set(None) in flush finally | Token discarded; only exhausted permits cleared | Removed; owning scope resets its captured token regardless of stages |
| _flushing.set(authority) | Captured and reset in finally | Preserved; nested finally guarantees flush-marker reset |

After repair there is one production _permit.set site, paired with retained
tokens and one reset implementation. The only other authorization-context setter
is _flushing.set, whose captured token is reset in finally. Permit reads in entry,
consume, cursor, root rollback and savepoint rollback retain their operation and
identity checks. The old consumption-dependent clearing read is removed.

### F-J. Repair, cleanup semantics, recovery, tokens and root removal

Only transaction_policy.py changes production behavior. open_permit rejects
finished roots and any already-active permit, then records the permit and reset
token in the root's permit_scopes. permit() records its starting depth and clears
the scopes it owns in finally. clear_permits revokes remaining stages, resets
the exact token and removes its ownership record. Repeated teardown is safe.

Automatic savepoint recovery uses that same creation path. The guarded flush
records its starting scope depth and resets every recovery scope created within
that flush, even if SQL never runs, consumption is partial, or BaseException
interrupts cleanup. Its nested finally resets the flush marker. An enclosing
infrastructure permit is outside that depth and remains intact.

Nested permit entry remains forbidden. Entry rejection does not mutate the
existing permit; another root's teardown has no ownership record for it and does
not erase it. No universal _permit.set(None) overwrite remains. Root remove()
defensively clears its tracked scopes before removing listeners, restoring
methods and removing registry authority. Normal inner finally blocks run first;
the root backstop also handles teardown while a scope is still open. The later
scope finally then finds nothing to reset twice.

The broken-root cursor check deliberately remains first. A broken unit does not
need further subordinate SQL to become reusable: authorized fatal E02 cleanup
invalidates/discards the Connection and Session. Its attempted savepoint SQL may
still be rejected, but the recovery token now resets deterministically. This
chooses reset-and-discard rather than weakening provenance or broken-root checks.
No general permit-based SQL bypass is introduced.

For healthy ordinary row-conflict recovery, the existing exact rollback clause
and ordered stage remain executable. While SAVEPOINT_ROLLBACK is active, other
business SQL is now also rejected, including reentrant SELECT/INSERT/UPDATE/DELETE
before or after the rollback stage is consumed. COMMIT, root ROLLBACK, SAVEPOINT,
RELEASE and DDL cannot borrow that permit. Native fatal invalidation/discard
remains available for broken-root cleanup.

### K-O. Later roots and cleanup regressions

The exact mapper-event regression now passes: root removed, permit None, flush
marker None, Session outside a transaction, no provisional Lead insert visible,
and the prior flushed Lead status restored to New. A later legitimate root uses
a fresh nonce and commits normally on the same Session, on a different Session,
and in a context copied after cleanup. This tests the supported sequential
Session contract, not arbitrary concurrent use or task sharing of a live root.

| New regression group | Cases |
|---|---:|
| Exact R4 attack, same/different Session and copied-context later roots | 3 |
| Root success, ordinary error, BaseException, settlement/SQL attacks and invalidation | 9 |
| Savepoint create/release/rollback failures with Exception and BaseException | 6 |
| Unconsumed recovery interruption, with/without invalidation failure | 4 |
| Recovery reentrancy: nine operations, healthy and broken roots | 18 |
| Successful savepoint and recoverable ValueError/BaseException body | 3 |
| Unconsumed, partially consumed and exhausted permits; normal/interrupted exit | 6 |
| Same-root nesting rejection preserves enclosing permit | 1 |
| Other-root cleanup preserves enclosing permit | 1 |
| Defensive root removal revokes active permit, including repeated removal | 1 |
| Old-root nonce cannot authorize a new root | 1 |
| Connection binding cannot be transferred | 1 |
| Total new cases | 54 |

All cleanup matrix exits leave current_root, _permit and _flushing empty after
complete E02 exit. Independent observers verify failed work is absent. Injected
recovery Exception/BaseException objects survive final cleanup by identity,
including injected invalidation failures; the exact R4 attack still escapes as
TransactionPolicyViolation. No reset error masks those failures.

### P-S. Reentrancy and preservation of earlier repairs

All eighteen recovery-callback reentrancy cases pass. Only the expected
subordinate rollback SQL can use a healthy recovery permit; broken-root business
execution remains denied. Permit reuse, cross-Session, cross-Connection,
wrong-operation and old-root nonce checks pass. Consumed and unconsumed captured
permits have empty remaining capabilities after scope exit.

R1 creation/materialization fail-closed cases pass, including body tripwires,
no continuation and prior Lead/audit rollback. The unchanged R2A scanner suite
passes. R3A DDL/emitted-SQL, normal typed SQL, infrastructure BEGIN, observer and
raw-DBAPI negative-control cases pass. No scanner, ADR, E02 contract, CSV, I3A,
auth, processing or tenant production file changed.

### T. Required R4A answers

| Q | Answer |
|---|---|
| 1 | Automatic ORM flush rollback_savepoint callback installed untracked _permit recovery state. |
| 2 | YES; independently reproduced before production edits, including later-root failure. |
| 3 | Cursor check() rejected the broken root before consuming savepoint_sql. |
| 4 | Cleanup required an exhausted remaining list; this permit was unconsumed. |
| 5 | YES; one centralized permit setter with tracked token ownership, plus scoped flush marker. |
| 6 | YES; tokens retained and reset by their owning finally or root backstop. |
| 7 | NO. |
| 8 | NO, within the supported sequential execution-context contract. |
| 9 | YES; remove clears root-owned scopes before registry authority. |
| 10 | NO; foreign/enclosing scope ownership is preserved and tested. |
| 11 | Nesting is forbidden; entry rejects without erasing the enclosing permit. |
| 12 | NO. |
| 13 | YES for authorized fatal invalidation/discard; subordinate SQL on a broken root remains denied because it is not needed for discard. |
| 14 | NO. |
| 15 | NO. |
| 16 | NO. |
| 17 | YES. |
| 18 | NO. |
| 19 | NO. |
| 20 | NO durable failed-root change; observers see original data. |
| 21 | YES. |
| 22 | YES. |
| 23 | YES. |
| 24 | NO. |
| 25 | NO. |
| 26 | NO. |
| 27 | NO. |
| 28 | NO. |
| 29 | NO. |
| 30 | NO. |
| 31 | NO. |
| 32 | NO. |
| 33 | NO. |
| 34 | NO. |
| 35 | NO. |
| 36 | NO. |
| 37 | YES. |
| 38 | YES. |
| 39 | YES. |
| 40 | YES for a completely fresh R5 review; not publication approval. |

### U-X. Fresh tests, PostgreSQL collection and quality

All acceptance execution uses published HEAD plus exactly the ten TX files in a
temporary git-archive snapshot. Frozen P1 and unrelated dirty work are not
overlaid. Python -B, scripts.ci_pytest, mock AI, blocked external test networking,
no pytest cache and mandatory no-skips enforcement are used.

| Gate | Result |
|---|---|
| Policy | 286 passed; 560 warnings; 70.37 seconds |
| Existing E02 + architecture | 22 + 117 = 139 passed; 102 warnings; 7.54 seconds |
| CSV/import | 23 passed; 51 warnings; 2.64 seconds |
| I3A create/audit | 26 passed; 189 warnings; 8.81 seconds |
| Auth/password/session | 40 passed; 690 warnings; 25.70 seconds |
| Processing | 22 passed; 195 warnings; 7.09 seconds |
| Lead API/workspace | 5 passed; 124 warnings; 4.14 seconds |
| Tenant/attack matrix | 35 passed; 684 warnings; 20.25 seconds |
| Full backend | 1,496 collected/passed; 0 failed/errors/skips; no subtests; 3,876 warnings; 212.72 seconds |
| PostgreSQL collection | 10 TX / 99 total; both commands exit 0 |
| Local PostgreSQL execution | NOT RUN: no disposable configuration or local docker/postgres/pg_ctl command |
| Quality | git diff --check, exact-ten-file whitespace, changed Python compilation and redacted exact-ten-file Gitleaks pass |
| Dependencies | pip check passes; installed dependency audit reports no known vulnerabilities; no installation |

Focused total: 576 passed. Full backend reconciliation: previous 1,442 + 54 new
policy cases = 1,496. Policy reconciliation: previous 232 + 54 = 286. Full-run
JUnit confirms all 54 R4A cases, all 286 policy cases, all 117 architecture cases
and all 22 E02 cases executed without skips. Warnings are the existing UTC
deprecations, with 123 additional fixture/model warnings from the new cases.

Actual scans remain 142 approved-snapshot files / 0 findings and 143 dirty
worktree files / exactly the same three frozen P1 findings: lead_repository.py:80
TX-CONTROL connection; :83 TX-CONTROL connection; :83 TX-RAW driver_connection.
No finding is suppressed. PostgreSQL collection is not runtime evidence;
exact-SHA CI and real PostgreSQL execution remain future publication gates.

### Y-AB. Acceptance update, exact delta and hash preservation

R4A changes exactly these three existing candidate paths:

1. backend/database/transaction_policy.py
2. tests/test_transaction_policy.py
3. docs/v2/E05_I3B_P1_TX_ACCEPTANCE_REPORT.md

The two changed Python hashes are:

| File | SHA256 |
|---|---|
| backend/database/transaction_policy.py | 599625d62f109c093fb8b768de1d53eb3590407332157123c16ab3d4fab38100 |
| tests/test_transaction_policy.py | f03c0f500fa6f7a4f88de75d3991e15ef49f17896186d62864f3a457bfd022cb |

The seven other TX candidates retain their supplied R4 hashes. All three P1
hashes remain exactly as supplied. The other 495 inventoried files remain
byte-identical. No eleventh TX publication file or new repository path is added.
The tested candidate Python bytes match the worktree. The report alone is updated
after the successful code gates; it does not require another backend execution.

### AC-AD. Final worktree and scope

HEAD/origin/main remain 64aa67919be55e7ecd61d2af37390828bee8bcdf; index empty;
sole Alembic head 5d59e6268f43; database hash unchanged. Operator contents remain
uninspected/unexecuted and recorded metadata is unchanged. Git status remains
exactly the full original status block in Y-AA above; unrelated work is preserved.

No staging, commit, push, amend, rebase, force push, P1 adaptation, lifecycle audit,
import audit, denial audit, schema change, operational migration, staging database,
Render operation, deployment, dependency installation, I3B/I3C/I4/I5, E06+ or
Temporal work occurred. Existing isolated migration tests ran only against their
disposable test databases; no application/staging migration was performed.

E05-I3B-P1-TX-R4A recovery-permit lifetime repair complete locally. Transaction
operation permits are now deterministically scoped to their governed root and
cannot survive root cleanup, including broken-root savepoint recovery paths.
TX remains unpublished and requires a completely fresh R5 publication review.

## R5A addendum - pre-release flush and recoverable savepoint conflicts

STATUS: PASS locally, 2026-10-15. This addendum supersedes the R4A local results
for the repaired candidate. TX is unpublished; P1 remains local and unadapted.
A completely fresh R6 publication review is required.

### A. Baseline

Before editing: branch main; HEAD and origin/main both
64aa67919be55e7ecd61d2af37390828bee8bcdf; index empty; sole Alembic head
5d59e6268f43. All ten supplied TX hashes and all three protected P1 hashes
matched. leadforge.db SHA256 was and remains
217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a.
Installed SQLAlchemy is 2.0.51. Tests used a disposable git-archive snapshot
of published HEAD with exactly the ten TX candidates overlaid; unrelated work
and the three local P1 files were not overlaid.

### B. R5 defect reproduction

Independently reproduced before production edits: add a duplicate ORM row inside
service_savepoint without calling flush, then leave the body normally. The
before_flush tripwire observed SAVEPOINT_RELEASE. Automatic rollback collided
with that permit and TransactionPolicyViolation escaped instead of IntegrityError.
Root broken/failed were true; Session.is_active was false, the root transaction
remained present, and the nested transaction remained present but inactive.
After helper failure, _permit and _flushing were empty. Outer exit rejected the
broken root; after teardown the root was removed. An independent observer saw
only the original row. No durability or token escape occurred.

The explicit-flush control observed no permit during business before_flush,
raised IntegrityError, left root broken/failed false, and recovered to an active
Session with no nested transaction. The new implicit phase-tripwire regression
failed against the saved pre-R5A policy, as expected; the original source was
not weakened to construct that negative control.

### C. Root cause

The helper granted SAVEPOINT_RELEASE before calling nested.commit while ORM
business state was still pending. Commit preparation flushed that state inside
release authorization. This incorrectly converted a subordinate business
conflict into a policy-integrity failure.

### D. nested.commit / flush semantics

Installed SQLAlchemy SessionTransaction._prepare_impl invokes before_commit,
then flushes until clean, bounded at 100 iterations, before physical RELEASE.
On a failed ORM flush, Session._flush calls transaction.rollback with
_capture_exception=True. That invokes rollback_savepoint; the existing governed
flush marker permits a distinct SAVEPOINT_ROLLBACK recovery scope when no other
permit is active. Successful automatic rollback deactivates the nested
transaction. The helper's subsequent nested.rollback completes logical cleanup
without emitting a second physical rollback. Tests observe exactly one
ROLLBACK TO SAVEPOINT for ordinary conflicts.

SQLAlchemy emits after_soft_rollback only after successful rollback and logical
cleanup. When physical rollback raises, its rollback_err is re-raised before
that event. Consuming the cursor stage alone cannot prove recovery succeeded.

### E. Repair

Only backend/database/transaction_policy.py changed in production. The helper
now performs governed business flushes after the yielded body and before the
release scope. Body-flush and exit-materialization errors share the existing
subordinate rollback path. Real release errors retain the fatal path.

To satisfy the required rollback-failure injection, automatic recovery now
records successful after_soft_rollback completion on the existing rollback
permit. A flush whose newly opened recovery scope does not complete marks the
root broken/failed before resetting its tokens. This covers both unconsumed
and consumed-but-failed rollback authorization. No new operation or broader
permission was added.

### F. Pre-release materialization

The helper calls the normal guarded db.flush, including a harmless no-op when
there is no pending work. It drains callback-created state using public
Session.new, dirty and deleted collections, bounded at 100 flushes. A
nonconverging callback raises FlushError and rolls back its savepoint. No private
unit-of-work inspection was introduced. Autoflush=False remains supported.

before_flush tripwires see no permit during ordinary business materialization;
before_commit and release tripwires see no pending ORM state. A callback that
adds ORM state after release authorization causes the flush guard to reject
that late flush before business before_flush runs. A successful explicit flush
is followed only by a no-op, without duplicate mutation.

### G. Recoverable conflict

Implicit and explicit duplicate conflicts preserve the original IntegrityError
object, leave root broken/failed false after successful recovery, and restore an
active Session. A NOT NULL conflict also recovers; no UNIQUE-specific exception
handling was added. Unexpected callback exceptions retain the existing
savepoint-body recovery contract; ordinary Exception and BaseException objects
are preserved by identity, with clean context state.

### H. Release-permit separation

CREATE, RELEASE and ROLLBACK remain separate operations with unchanged stages.
RELEASE cannot authorize ROLLBACK. Reentrant typed SELECT and UPDATE retain
their existing policy behavior; COMMIT, ROLLBACK and another SAVEPOINT are
denied. The new restriction prevents pending ORM business materialization under
RELEASE; it does not claim to prohibit every existing typed business statement
in a release callback.

### I. Same-root continuation

After catching either implicit or explicit IntegrityError, tests query, add and
flush valid work, enter another savepoint and commit the outer root. The root
commit counter is exactly one. Forced outer failure produces zero root commits.

### J. Observer proof

Independent Sessions verify the duplicate and failed-savepoint sibling rows are
absent. Successful continuation persists only intended prior/later work. Failed
outer transactions leave only the original durable data. Mechanism failures
also leave the observer unchanged.

### K. ORM insert/update/delete

The success/outer-rollback matrix covers empty savepoints, typed Core DML,
explicitly flushed inserts, implicit inserts, multiple inserts, pending updates
and pending deletes. Every case preserves outer rollback authority. A separate
after_flush_postexec callback adds follow-up work: both business flushes occur
before release authorization.

### L. Multi-row failure

Valid and duplicate rows in one savepoint flush are rolled back together. Neither
the explicit nor implicit path preserves the valid sibling of a failed flush.

### M. Prior outer work

Prior outer updates survive subordinate rollback provisionally. If the outer
root subsequently fails, both prior and later provisional work disappear.

### N. Second savepoint

A second savepoint succeeds after the conflict is caught, without stale permit
state, and remains subordinate to the same outer root.

### O. Release failure

Injected physical release Exception and BaseException occur after successful
materialization, verified through the Connection. Their original objects escape,
the root becomes broken/failed, continuation is denied, context state is clean
and no provisional update becomes durable.

### P. Rollback cleanup failure

The required fault probe exposed an additional in-scope failure before edits:
an automatic rollback callback could raise, yet the root remained healthy and a
valid sibling from the failed flush could be committed. The permanent regression
failed against the saved pre-R5A policy because root.broken remained false.

R5A tests inject Exception/BaseException both in rollback_savepoint before the
cursor stage and in dialect.do_execute after that stage, immediately before the
DBAPI call, for explicit and implicit flushes. All eight cases now mark the root
broken/failed immediately, deny queries and further savepoints, clear contexts
and discard provisional changes. SQLAlchemy's escaping injected rollback-fault
object is preserved by identity; successful recovery preserves the original
business IntegrityError. No failure is disguised as successful recovery.

### Q. Policy error during preflush

Mapper callbacks attempting DDL COMMIT during pre-release flush are denied,
break the root and produce no durability. Ordinary RuntimeError/BaseException
callback cases preserve their original errors and the existing body-error
recovery semantics. No callback observes a release permit during preflush.

### R. Permit cleanup

Recoverable conflicts leave no CREATE, RELEASE, ROLLBACK or PHYSICAL_BEGIN
permit and no flush marker. The healthy root stays registered until outer exit;
after exit, current_root, _permit and _flushing are empty. Failure cases retain
the deterministic R4A cleanup and original error preservation.

### S. R1

Creation/materialization failures still break the root before exposing the body;
continuation is denied and prior provisional work is discarded. Existing cases
pass unchanged.

### T. R2A

The unchanged 117-case architecture suite passes, including relative imports.
Actual scanner results remain 142 approved-snapshot files / zero findings and
143 worktree files / the same three frozen P1 findings: lead_repository.py:80
TX-CONTROL connection; :83 TX-CONTROL connection; :83 TX-RAW driver_connection.
No finding is suppressed.

### U. R3A

Representation-independent control fences, emitted-SQL checks, compiled/runtime
DDL denial and normal typed SQL cases pass. The new preflush DDL callback test
also passes. No scanner or SQL classification change was needed.

### V. R4A

All earlier permit-lifetime, root teardown, interrupted recovery and reentrancy
regressions pass without altering their test bytes. Rollback-completion tracking
adds a failure decision before the existing deterministic token reset.

### W. Required Q1-Q42 answers

| Q | Answer |
|---|---|
| Q1 | nested.commit preparation implicitly flushed pending ORM work after the helper had entered RELEASE authorization. |
| Q2 | YES; independently reproduced before production edits. |
| Q3 | YES; governed materialization precedes release authorization. |
| Q4 | NO; RELEASE cannot authorize ROLLBACK. |
| Q5 | NO; release operations and stages were not broadened. |
| Q6 | YES; implicit duplicate returns IntegrityError. |
| Q7 | YES; explicit duplicate remains equivalently recoverable. |
| Q8 | NO, when subordinate recovery succeeds. |
| Q9 | NO, when subordinate recovery succeeds. |
| Q10 | YES; exactly one physical subordinate rollback. |
| Q11 | YES; original IntegrityError object preserved. |
| Q12 | YES; typed query after catch. |
| Q13 | YES; valid write after catch. |
| Q14 | YES; explicit flush after catch. |
| Q15 | YES; second savepoint after catch. |
| Q16 | YES; outer root later commits once. |
| Q17 | YES; duplicate absent from observer. |
| Q18 | YES; later valid work commits. |
| Q19 | YES, provisionally; prior outer work survives subordinate rollback. |
| Q20 | YES; outer rollback removes prior and later provisional work. |
| Q21 | YES; multiple pending valid rows. |
| Q22 | YES; pending update. |
| Q23 | YES; pending delete. |
| Q24 | YES; valid sibling and duplicate both roll back. |
| Q25 | YES; successful explicit flush. |
| Q26 | YES; typed Core DML. |
| Q27 | YES; empty savepoint. |
| Q28 | NO; late pending ORM flush under RELEASE is denied before materialization. |
| Q29 | YES; actual release failure breaks root. |
| Q30 | YES; rollback callback and driver failures break root. |
| Q31 | YES; preflush DDL policy violation breaks root. |
| Q32 | NO; no permit or flush-marker leak. |
| Q33 | YES; R1 unchanged and green. |
| Q34 | YES; R2A unchanged and green. |
| Q35 | YES; R3A unchanged and green. |
| Q36 | YES; R4A unchanged and green. |
| Q37 | YES; CSV/import behavior unchanged. |
| Q38 | YES; I3A unchanged. |
| Q39 | YES; 1,540 full-backend tests pass without skips. |
| Q40 | YES; 10 TX and 99 total PostgreSQL cases collect. |
| Q41 | NO P1 adaptation, operational migration, staging or deployment work. |
| Q42 | YES for completely fresh R6 review; this is not publication approval. |

### X. Focused tests

| Gate, in required execution order | Result |
|---|---|
| Policy | 330 passed; 812 warnings; 82.60 seconds |
| E02 + architecture | 22 + 117 = 139 passed; 102 warnings; 7.57 seconds |
| CSV/import | 23 passed; 51 warnings; 2.74 seconds |
| I3A create/audit | 26 passed; 189 warnings; 8.94 seconds |
| Auth/password/session | 40 passed; 690 warnings; 25.42 seconds |
| Processing | 22 passed; 195 warnings; 7.14 seconds |
| Lead API/workspace | 5 passed; 124 warnings; 4.21 seconds |
| Tenant/attack | 35 passed; 684 warnings; 20.21 seconds |

Focused total: 620 passed; zero failures, errors or skips. The 44 new permanent
policy cases reconcile as follows:

| New regression matrix | Cases |
|---|---:|
| Implicit/explicit conflict, sibling, outer commit/rollback | 8 |
| Seven business-state forms, outer commit/rollback | 14 |
| Callback-created follow-up work before release | 1 |
| Late before_commit work cannot flush under RELEASE | 1 |
| Automatic rollback failure: event/driver, explicit/implicit, Exception/BaseException | 8 |
| Actual release failure: Exception/BaseException | 2 |
| Preflush DDL/Exception/BaseException callbacks | 3 |
| Five reentrant release operations | 5 |
| Non-UNIQUE integrity conflict | 1 |
| Bounded nonconverging flush callback | 1 |
| Total | 44 |

### Y. Full backend

1,540 passed; zero failed/errors/skips; no subtests; 4,128 warnings; 224.62
seconds. Full-run JUnit confirms all 44 R5A cases, 330 policy cases, 117
architecture cases and 22 E02 cases executed. Reconciliation: prior 1,496 + 44
= 1,540; prior policy 286 + 44 = 330. The 252 additional warnings come from
new regression fixture/model use; warnings remain UTC deprecations.

Execution used Python -B, scripts.ci_pytest, mandatory no-skips enforcement,
mock AI, blocked external test networking, no pytest cache and disposable local
databases. The two changed Python files and all seven Python candidate files
match the tested snapshot bytes.

### Z. PostgreSQL collection

Collection passes: 10 TX cases and 99 full-suite cases, unchanged. Local
PostgreSQL runtime: NOT RUN; no configured disposable admin URL and no local
docker, postgres or pg_ctl command. Staging was not accessed. Collection is not
runtime evidence; PostgreSQL execution and exact-SHA CI remain publication gates.

### AA. Quality

git diff --check, exact-ten-file whitespace, compilation of all seven Python
candidates, and Gitleaks over exactly the ten TX candidate files with repository
configuration and full redaction pass. pip check reports no broken requirements;
the installed dependency audit reports no known vulnerabilities. No dependencies
were installed. Report-only edits receive another whitespace/compile/secret
check after the successful code gates; backend execution is not repeated for
documentation alone.

### AB. Acceptance report

Only this report is updated after all local code gates pass. Historical evidence
is retained, the current status points to R6, and explicit/implicit recovery,
continuation, observers, fault injections and PostgreSQL limitations are recorded.
No ADR or E02 contract change was made.

### AC. Exact R5A delta

Exactly three existing candidate paths changed in R5A:

1. backend/database/transaction_policy.py
2. tests/test_transaction_policy.py
3. docs/v2/E05_I3B_P1_TX_ACCEPTANCE_REPORT.md

No eleventh TX publication file or new repository path was added. All pre-existing
policy test bytes remain an unchanged prefix of the final test file. The changed
Python SHA256 values are:

| File | SHA256 |
|---|---|
| backend/database/transaction_policy.py | 0a7150910ffcf185a0af4d385dbeff1bed96752350b8cfe238f37af9de175e72 |
| tests/test_transaction_policy.py | 3f785d5c26b6618e4f184826005da13a8fb481905248ada4429246ef0945b1bb |

### AD. TX hash preservation

The seven frozen TX candidates retain their supplied hashes:

| File | SHA256 |
|---|---|
| backend/database/transactions.py | 2cf3ab5cc15bffe8a92354d39711c71f0262e7c74439567a9dbe13a7f5eb3d9a |
| backend/services/lead_import_service.py | d7ccdd04721602259d24095195a4dddcf5252fe4d485d73c41bb7e0da6d6c1d8 |
| docs/v2/E02_SERVICE_OWNED_TRANSACTIONS.md | 7d54e811d97fcac7a17e1687930ad98807d8723a939d402882fcb1bac3adedba |
| docs/v2/adr/ADR-002-TRANSACTION-GOVERNANCE.md | e4468bb62a9ad1d63fd488fe876a36e8810d3dc6d7026b3ec29726a22a456894 |
| tests/test_transaction_architecture.py | 4f2acf9d30e497542e148aff71b8882fff9c5696ffb562bf53503cf37d65e575 |
| tests_postgres/test_postgres_baseline.py | 7f4e170b4cc213b2345c9a83acf005366185e80902ccdf7827ccbe5ee23de171 |
| tests_postgres/test_transaction_policy.py | ceaac9c1ac85a9ce5d2c968ad72cbc6192f0add4978d4dd220499e3fc86fa326 |

### AE. P1 preservation

| Protected file | Unchanged SHA256 |
|---|---|
| backend/repositories/lead_repository.py | 491f0786093e2f804638903b674211608c96227fd28c32624634395c065bc856 |
| tests/test_lead_lifecycle_locking.py | 8ecf82888027cfe4e6ce7586976404ff5fbf2c00173896ce6b96348560c3a836 |
| tests_postgres/test_lead_lifecycle_locking.py | 2b88512ae1732572bbc38810eca0391ffb35722afb68e2fee20f313c1ef4d70d |

The other 495 inventoried files remain byte-identical. leadforge.db is unchanged.
The operator script was neither inspected nor executed; its metadata remains
size 2332, mtime_ns 1791786871246713700, ctime_ns 1791786871246713700.

### AF. Final Git status

main, HEAD and origin/main remain at the baseline; index empty; sole Alembic head
5d59e6268f43. The complete initial/final status is identical:

```text
 M Dockerfile
 M backend/database/transactions.py
 M backend/repositories/lead_repository.py
 M backend/services/lead_import_service.py
 M deploy/render/provision.py
 M docs/CONFIGURATION.md
 M docs/RENDER_STAGING.md
 M docs/STEP_5F_VERIFICATION.md
 M docs/v2/E02_SERVICE_OWNED_TRANSACTIONS.md
 M tests_postgres/test_postgres_baseline.py
?? _temporary_staging_login.py
?? backend/database/transaction_policy.py
?? deploy/render/database_identity.py
?? deploy/render/preflight.py
?? docs/STEP_5H_B_REMOTE_VERIFICATION.md
?? docs/STEP_5H_B_SCHEMA_READINESS_DIAGNOSIS.md
?? docs/STEP_5H_B_VERIFICATION.md
?? docs/v2/E05_I3B_P1_TX_ACCEPTANCE_REPORT.md
?? docs/v2/adr/ADR-002-TRANSACTION-GOVERNANCE.md
?? package-lock.json
?? package.json
?? tests/test_lead_lifecycle_locking.py
?? tests/test_render_database_identity.py
?? tests/test_render_preflight_diagnostics.py
?? tests/test_transaction_architecture.py
?? tests/test_transaction_policy.py
?? tests_postgres/test_lead_lifecycle_locking.py
?? tests_postgres/test_transaction_policy.py
```

### AG. Scope

No staging, commit, push, amend, rebase, force push, P1 adaptation, lifecycle audit,
import audit, denial audit, migration addition/application, staging database,
Render operation, deployment, dependency installation, I3B/I3C/I4/I5, E06+ or
Temporal work occurred. Existing isolated migration tests ran only against their
disposable databases; no application or staging migration was performed. No .env
contents or operator-script contents were read. This is local evidence for the
supported governed execution contract, not a hostile-code sandbox or proof
against direct raw DBAPI control or ambiguous database commit outcomes.

E05-I3B-P1-TX-R5A recoverable implicit-savepoint-flush repair complete locally. service_savepoint now materializes pending ORM business state before SAVEPOINT_RELEASE authorization, so ordinary constraint conflicts remain subordinate and recoverable without broadening transaction permits. TX remains unpublished and requires a completely fresh R6 publication review.


## R6C frontend security remediation addendum - 2026-11-03

Current local status: R6C PASS. TX remains unpublished. This addendum records
local evidence only; it is not publication approval. A completely fresh R7
independent publication review is required. All historical sections above remain
byte-for-byte intact and retain their original verification boundaries.

### R6A and R6B status

R6A restored exclusive E02 root-settlement ownership locally, but publication
remained blocked by the dependency security gate. Its production and test files
are unchanged in R6C. All 74 ownership regressions and the R1/R2A/R3A/R4A/R5A
families pass freshly.

R6B changed only the runtime langgraph-sdk pin from 0.4.4 to 0.4.6. Its clean
resolution established that certifi, dnspython and pyasn1 were stale runtime
transitives, while filelock was a stale verification-only transitive through
pip-audit -> CacheControl[filecache]. Those four required no new project pins.
R6C preserves requirements.txt exactly. The same existing Python audit freshly
reports zero known vulnerabilities across 104 installed packages; pip check
passes and langgraph-sdk resolves to 0.4.6. Verification uses the disposable
canonical R6B environment, not the unchanged stale developer environment.

### Vite advisory and minimal resolution

A fresh npm audit reproduced the HIGH affected package at node_modules/vite,
version 8.2.2, including GHSA-587h-7wmj-h5pm. The maintainer advisory confirms
Vite >=8.2.0,<=8.2.3 is affected and 8.2.4 is patched:
https://github.com/vitejs/launch-editor/security/advisories/GHSA-587h-7wmj-h5pm

Canonical frontend/package.json changes only vite from ^8.2.2 to ^8.2.4,
preserving its existing dependency style. npm-generated lockfile changes are
limited to two entries: root devDependency metadata and node_modules/vite.
Only Vite's version, resolved tarball URL and integrity change in the latter.
No other package version, dependency edge, plugin, React, npm or Python pin
changes. The lockfile remains version 3 and resolves exactly Vite 8.2.4.
The legacy root-level npm files remain unrelated and unchanged.

### Fresh frontend verification

Node v22.22.2 and bundled npm 10.9.7 were used without upgrading either tool.
A clean npm ci in the disposable approved snapshot passes. The local frontend
installation was then aligned using npm ci and also resolves Vite 8.2.4.
Explicit npm audit --audit-level=high passes with zero findings at every
severity; GHSA-587h-7wmj-h5pm is absent. No audit fix, force, ignore or exemption
was used.

Canonical npm run lint and npm run build pass. The two existing AuthContext
lint warnings remain; no source was changed to silence them. No new production
build warning or configuration change was required. A read-only case check
validates 63 literal relative imports. Dev-server smoke returns HTTP 200 for
the application entry, /src/main.jsx and /@vite/client under Vite 8.2.4.

All 13 existing frontend tests pass without test-source edits or new exclusions:
9 production/validation journeys, 3 isolated change-password tests using their
existing configuration, and 1 recovery test. Browser execution uses separate
headless Chrome profiles, a production frontend build, and a disposable local
SQLite/mock backend; it is not a PostgreSQL or deployment claim. The existing
fixture and migrations target only the newly created disposable test database.

The first recovery attempt hit the existing HTTP 429 login budget because the
disposable harness omitted the documented inter-phase pause. Its failed report
is retained. After that attempt's 60-second timeout and a local backend restart,
the unchanged recovery test passes against retained synthetic failure state.
No retry setting, rate limit, test assertion or application code was changed.

### Fresh backend and architecture verification

The published baseline plus the exact TX candidate, R6B requirements and R6C
frontend manifests formed the approved snapshot. Protected local P1 files were
not adapted or included in the publication acceptance snapshot.

| Focused suite | Passed |
|---|---:|
| Transaction policy | 404 |
| Architecture | 117 |
| Service transactions | 22 |
| CSV/import | 23 |
| I3A | 26 |
| Auth/password/session | 40 |
| Processing | 22 |
| Analysis contract | 5 |
| Lead API/workspace | 5 |
| Tenant/attack | 35 |
| Total | 699 |

Focused execution: 699 passed, zero failures/errors/skips, 3,132 warnings,
177.57 seconds. Full backend: 1,614 passed, zero failures/errors/skips, 4,289
warnings, 252.87 seconds. The count remains 1,540 prior tests plus 74 R6A cases.
PostgreSQL collection passes: 10 TX and 99 total. Docker is unavailable; real
PostgreSQL execution remains an exact-SHA R7 CI gate. No staging access occurred.

Approved architecture scan: 142 backend files, zero findings. Dirty worktree
scan: 143 files and exactly the three protected P1 findings at lead_repository.py
lines 80 and 83. No scanner or suppression changes. Existing Gitleaks scans
487 approved source files and its synthetic negative control passes. Diff and
candidate whitespace checks, Python compilation, pip check, both dependency
audits, frontend gates and backend gates pass. Report-only edits receive final
whitespace, secret and preservation checks without repeating unchanged code tests.

### Scope and preservation

R6C changes frontend/package.json and frontend/package-lock.json plus this
explicitly authorized append-only report update after all code gates passed.
R6A production SHA256 remains
0292ac609ebd5fd2f1cacb1f6437bdcc2043aaa96c02b7086472017a76c793be;
R6A test SHA256 remains
b2da89c5742180afbb079ecc50f6c225bfe2ac3081e03cb819b8c781ed474be0.
R6B requirements SHA256 remains
c31fbfb2e7051008ebc09cb45593955994758723a0bc9fa6a3b156278f4e8952.
Other TX files, all three P1 files, leadforge.db, operator size/mtime and unrelated
inventoried work are preserved. Operator contents were not inspected or executed;
private dotenv contents were not read.

main, HEAD and origin/main remain at
64aa67919be55e7ecd61d2af37390828bee8bcdf; the index remains empty. No staging,
commit, push, deployment, staging migration, P1 adaptation or lifecycle audit
integration occurred. R7 was not started.

E05-I3B-P1-TX-R6C frontend security remediation complete locally. Vite was
patched from 8.2.2 to 8.2.4, removing the high-severity frontend audit blocker
without broad dependency upgrades. R6A transaction ownership, R6B Python
security remediation, all prior transaction-governance regressions, frontend
quality gates, and backend regressions remain green. TX remains unpublished
and requires a completely fresh R7 publication review.
