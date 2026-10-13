# E05 implementation acceptance criteria

E05-D2 refinement: 2026-10-13. Design baseline `e38d1863fcba8bbd331808a25d546275ffc0bbdb`. **Tests below are planned, not executed. E05 implementation is not authorized by these documents.** Read [ledger design](E05_AUDIT_LEDGER_DESIGN.md) and [schema/migration plan](E05_AUDIT_SCHEMA_AND_MIGRATION_PLAN.md). This document is not an implementation acceptance report.

## Architecture approval before implementation

Approve the three-command scope, revised 22-column schema, bounded repeating evidence, historical organization ID without a FK, no synthetic authority_version and no public audit API. E02 remains generic and unchanged; denial capture/recording belongs to an explicit application/audit-service boundary AFTER the owning transaction settles. Nested compositions must pass their audit operation context explicitly to obtain best-effort denial persistence; an uncontextualized external E02 scope retains safety and emits coverage-loss diagnostics instead of writing while the root transaction is active.

The selected guarantee is best-effort denial evidence, not an unresolved requirement for lossless intake. Approve a same-database independent-Session recorder with one attempt and a proposed 5-second total deadline. Test pool/connect/statement/lock budget accounting; individual 5-second timeouts do not prove a total deadline. If drivers cannot meet it, revise the budget/integration before acceptance. No audit-aware transaction hook, generic new framework, implicit identity or altered E02 failed-state semantics.

Before production deployment, privacy/security owner must approve retention/hold/deletion/backup rules, capacity/denial-abuse monitoring and actual audit-table privilege carve-out. Design completeness is not approval to deploy or a legal/compliance certification. Disposable implementation validation can precede these production approvals only after architecture approval.

## Exact guarantee acceptance language

| Class | Required acceptance language |
|---|---|
| MUST HOLD | Successful business mutation cannot commit without its required success audit event in the same owning transaction. |
| MUST HOLD | Audit failure cannot convert DENY to PERMIT or replace denial with privileged execution. |
| MUST HOLD | A denied command performs no business mutation; earlier root writes still obey E02 rollback-only behavior. |
| BEST-EFFORT | Structural denial auditing attempts durable persistence after confirmed business settlement; crash, storage failure, missing outer context or ambiguous commit can lose/obscure evidence. Never claim every denial is losslessly audited. |
| MUST HOLD on observable audit failure | Preserve original safe denial/TransactionAborted and emit content-free operational evidence-loss diagnostics; do not leak infrastructure details. Hard process death can also prevent diagnostics. |
| DEFERRED | Failed business command durable audit. |
| DEFERRED | Cryptographic tamper evidence. |
| DEFERRED | Authentication/account/platform-global security ledger. |

The available-storage normal-path recorder test must pass; that proves behavior under those conditions, not a failure-independent durability guarantee. Crash/outage fixtures intentionally demonstrate the coverage gap. E05 implementation fails acceptance if it claims mandatory/lossless denial durability or adds a business commit to preserve rejection evidence.

## Planned behavioral tests (56 scenarios)

Use the existing `tests/` isolation and CI network guard. All databases disposable; no provider calls or leadforge.db writes. Add proposed audit tests only during a separately authorized implementation task. Low-level schema tests use raw inserts/SQL; command tests invoke the canonical authorized services, not private shortcuts.

| ID | Planned scenario | Required assertion |
|---|---|---|
| A01 | Authorized human create | One owned Lead + exactly one SUCCEEDED event; same org, target ID, actor/correlation, one exact authorization-evidence item and actual human role; no authority_version. No customer content. |
| A02 | Successful nested create/lifecycle | No inner commit; business writes and one event per invoked command persist together at one root commit. |
| A03 | Audit append raises before/after flush | Root rolls back Lead mutation and any provisional event, original safe infrastructure failure propagated; no orphan success. |
| A04 | Later outer failure | Previously flushed business writes + success rows all disappear. Audit repository never commits. |
| A05 | Business validation / exact duplicate / unrelated constraint failure | Existing safe result and rollback behavior preserved; no surviving SUCCEEDED row and no fabricated FAILED event. |
| A06 | Commit fails before durable acceptance | No mutation/event; Session cleaned up. Separate transport-ambiguity fixture may show both persisted, never assert rollback proves absence after unknown commit. No automatic mutation retry. |
| A07 | Denied create, standalone | No Lead; original denial; independent observer sees one durable permission.denied row after root rollback. |
| A08 | Nested denial after early writes | Early writes + provisional success events roll back; explicit outer application/audit context captures first decisive rejection, which persists in a separate transaction after settlement when storage is available. |
| A09 | Catch nested denial | Root remains rollback-only and raises TransactionAborted under unchanged E02 semantics. Application boundary records its first captured rejection after root exit; no audit knowledge/callback dispatch or new abort-on-entry behavior in E02. |
| A10 | Rejection audit unavailable / flush error / commit error | Original denial/TransactionAborted unchanged, zero business mutation; safe audit failure diagnostic, no secret or raw exception message. |
| A11 | Rollback/invalidation failure | Failed Session/connection never reused for audit; bounded safe cleanup/failure signal, no invented durable evidence. Preserve original exception. |
| A12 | Death after rollback before rejection commit | No business mutation; explicitly demonstrate denial row may be absent. Test documents accepted coverage gap; not disguised as durable success. |
| A13 | Shared file-backed SQLite, early write then nested denial | Original write lock released before independent audit insert; no self-deadlock, no reuse of original connection. Confirm observer persistence. |
| A14 | Membership changes after evaluation | Event preserves exact authority snapshot actually used; no second lookup substitutes a later role. Denial persistence does not require the rejected actor to regain authority. |
| A15 | Lifecycle normal/no-op/not-found | Safe status before/after and changed_fields only; one event for accepted no-op, no success for foreign/missing Lead; notes/contact dates absent. |
| A16 | Two concurrent lifecycle updates | PostgreSQL locked before-image yields actual serialized transition, not two stale before values; safe SQLite write-lock behavior. Both event/state atomic pairs. |
| A17 | Successful CSV batch and all-duplicate replay | One command event per confirmation, not one per row; counts match existing result and no AI calls. New confirmation gets new event ID; token replay is not event deduplication. |
| A18 | CSV audit failure after released savepoints | Entire batch + success event roll back, including early SQLite rows. Preserve explicit outer BEGIN. |
| A19 | Import permissions neither / import only / create only / both | First three deny with zero imports; denial evidence contains only actual evaluated items (short circuit respected). Both permits and successful event records both PERMIT reasons. No OR interpretation. |
| A20 | Session/digest/file/expiry mismatch after permission PERMIT | Existing 422/no imports; no success event; preview remains nonmutating and has no command ledger append. No token/session data persisted. |
| A21 | Missing/invalid/None principal; old alias/signature | Existing fail-closed behavior; no fabricated organization/principal event. Original E04-R direct-call regressions remain green. |
| A22 | Trusted explicit tenant mismatch | Zero business mutation; rejection in trusted principal's org only; no submitted foreign org/target ID in details. Pre-principal HTTP auth/CSRF/selector rejection remains operational-only. |
| A23 | All four machine types | Missing/empty/wrong principal/tenant/raw dictionary scope denies; matching typed scope permits create/lifecycle. Evidence includes exact machine/provenance/delegator IDs; SYSTEM no privilege. |
| A24 | Identity/delegation/correlation snapshots | Original bounded immutable values survive membership change and target deletion; no recursive provenance or transport secrets. Correlation collisions never grant access or imply causality. |
| A25 | Actor deletion/provenance removal | No actor/target FK cascade mutates ledger; erased/reused ID is not silently resolved as same current actor. Future deletion workflow's non-reuse requirements documented. |
| A26 | Organization deletion | No audit FK: deleting a disposable org row (with unrelated dependent business data removed by fixture) leaves the event and organization_id unchanged; history is queryable internally without a live join. Non-reuse/generation gate blocks interpreting it as another tenant. |
| A27 | Tenant A event retrieval/list filters/cursor | Org B receives no row, even with exact UUID, colliding actor/correlation or crafted cursor. Every repository read has explicit org predicate before filters/limit. |
| A28 | Repository/service surface | Append + scoped read APIs only, no update/delete/save or customer/operator bypass; returned receipts/DTOs immutable, no modifiable tracked ORM object exposed. |
| A29 | Attempt ORM UPDATE/DELETE | Application guards reject persisted AuditEvent mutations/deletion; flush does not rewrite history. Raw SQL limitation explicitly recorded, not falsely prevented by naming. |
| A30 | Secrets / arbitrary metadata | Unknown keys and prohibited payload paths rejected; builders never serialize entire request, User, Session, Lead, exceptions or provider results. Synthetic secret fixtures are redacted in outputs. |
| A31 | Size/depth/value abuse | <=2048 canonical UTF-8 bytes, <=2 depth, <=8 keys; unknown enums, floats/NaN, oversized/unbounded arrays, count overflow/arithmetic mismatch reject safely. Multibyte byte cap tested. |
| A32 | Raw inserts violating schema | DB checks reject explicit-column NULL/domain/delegator/type/target/bounds/version violations. Application validators reject malformed evidence, missing import PERMIT, JSON null and contradictory reasons; do not claim DB alone enforces JSON semantics. |
| A33 | UTC/ordering | Naive times rejected; aware offsets normalized; PostgreSQL roundtrip aware UTC; SQLite conversion explicit; equal timestamps deterministic keyset tie-break with UUID, no global/commit order claim. |
| A34 | UUID/collision | Canonical UUID4 survives JSON/SQLite/PostgreSQL; duplicate event ID rejects and never silently accepts mismatched evidence; command correlation is not unique. |
| A35 | Recorder boundedness | One decisive draft per explicit audit operation; no audit-aware E02 hook or recursive retry; independent factory injected, same configured DB; timeout <=5 seconds total under pool, connection and lock failure. Session close does not accidentally commit business. |
| A36 | No repository/route business commit | Existing E02 assertion plus audit repository append inside owning scope; dedicated rejection recorder is the only separate audit-only transaction owner. |
| A37 | Migration clean + populated upgrade | SQLite and PostgreSQL new table/constraints/indexes only; V1 data unchanged, no synthetic historical events/backfill. Exactly one new head. |
| A38 | Migration downgrade/upgrade | Disposable empty/populated table drops intentionally, V1 state preserved, re-upgrade clean; destructive audit-history limit is explicit. No production downgrade rehearsal. |
| A39 | PostgreSQL concurrent create/import audit | Existing uniqueness and independent-backend assertions retained; no lost committed audit or cross-tenant evidence; no hard audit FK is assumed. Import produces one event per successful command, not per row. |
| A40 | PostgreSQL indexes/query plans | Introspect exact five indexes; representative tenant/time/actor/target/correlation/action queries select intended bounded indexes. Avoid brittle tiny-table EXPLAIN assumptions. |
| A41 | Future role hardening fixture | In disposable PostgreSQL, non-owner app can SELECT/INSERT, cannot UPDATE/DELETE/TRUNCATE/assume migrator; backup/migration work; re-provision default grants cannot restore audit mutation rights. Separate deployment gate, no staging operation. |
| A42 | Backup/restore and evidence boundary | Disposable restore includes events and constraints, preserves IDs/times/tenant and any authorized deletion replay plan; no claim backup is cryptographic tamper proof. |
| A43 | Regression/security | E02/E03/E04, auth/password concurrency, tenant attack matrix, CSV, processing/read contracts, logging and full backend remain green; no weakened tests or new skips. |
| A44 | Development safety | Before/after leadforge.db SHA256 unchanged, unrelated files preserved, operator script unread/unexecuted, no dotenv opt-in or paid provider/staging access. |
| A45 | Single authorization-evidence item | Ordinary create/lifecycle success contains exactly the actual required PERMIT item; omission/extra items rejected. |
| A46 | Two authorization-evidence items | Import success contains lead.import then lead.create, both PERMIT with actual reasons; first/second denial lists reflect short-circuit evaluation only. |
| A47 | Maximum evidence item count | Generic repeating validator accepts eight distinct valid enum items within size bound; v1 action validators still reject extra checks for single/two-check commands. |
| A48 | Evidence item overflow | Nine items rejected before append; no success mutation commits when evidence is invalid. |
| A49 | Oversized authorization evidence | >2048 canonical UTF-8 bytes rejected; malicious oversized malformed value rejected without weakening enum types; separate evidence/details byte limits tested. |
| A50 | Unknown evidence field | Fourth/arbitrary nested field, missing field, JSON null, list/string coercion and unknown top-level dump rejected by closed schema. |
| A51 | Invalid permission/decision/reason | Unknown strings, wildcard, untyped/invalid enums and PERMIT with DENIED_* or DENY with PERMITTED_* rejected. |
| A52 | Client-controlled evidence/details | Submitted JSON/dictionaries/request/ORM dumps do not become trusted evaluation receipts or details; existing transport extras rejected, no arbitrary append payload endpoint. |
| A53 | Deterministic evidence | Stable ordered serialization; duplicate permission rejected; import order preserved, no false unevaluated item. |
| A54 | Removed authority_version/schema recount | Exactly 22 columns; no authority_version or six numbered-slot columns or child table; schema_version remains payload format only. |
| A55 | Generic E02 independence | Existing helper state/ownership/rollback-only tests unchanged; no permission/event/audit callback knowledge. Explicit audit composition records only after root settlement. |
| A56 | Nested owner without audit context | Original E04 denial and root rollback-only still hold; no independent writer while active, safe coverage-loss diagnostic, no guaranteed durable row. Successful nested events remain atomically required. |


## Required implementation gates

| Gate | PASS requirement |
|---|---|
| SCHEMA | Approved 22 columns, bounded evidence JSON/event matrix, explicit defaults, five indexes, no hard FKs/authority_version/numbered slots; ORM/migration agree; raw SQL checks plus application evidence validators tested (A32/A45-A54). |
| TRANSACTION ATOMICITY | A01-A06/A15-A18/A36: one root commit; no committed consequential mutation without required success event; no provisional success surviving failure. |
| BEST-EFFORT DENIAL RECORDING | A07-A14/A19/A22/A35/A55/A56: normal available-storage persistence AFTER settlement; crash/outage/context-loss gaps explicitly demonstrated, original denial preserved. No lossless claim. |
| TENANT ISOLATION | Required historical org ID without FK, non-reuse/generation lifecycle gate, ownership-validated target, scoped event/list/cursor access, trusted-org rejection attribution; A22/A26/A27/A39. |
| IDENTITY PROVENANCE | Snapshots preserve validated E03 actor/delegator/correlation/machine fields, no client identity grants; A21/A23-A25. |
| AUTHORIZATION EVIDENCE | Exact E04 receipts captured at check site in bounded typed repeating JSON, actual role snapshot, no synthetic version, import BOTH; A14/A19/A23/A45-A54. |
| APPEND-ONLY CONTRACT | Append-only service/repository and ORM guards pass A28/A29/A36; documentation states raw SQL/admin limits. No false immutable/tamper-evident claim. |
| PRIVACY/SECRET SAFETY | Closed payloads and IDs only; A30/A31 plus secret scanner passes design/code/migration/test material. Production retention/hold/export/deletion approval recorded before real collection. |
| MIGRATION | New revision after sole current head; clean/populated upgrade/downgrade in disposable DBs, no V1 backfill/rewrite; pinned readiness/CI revision checks updated deliberately. A37/A38. |
| POSTGRESQL | 16.15 migration/explicit CHECK/UTC/index/concurrency and JSON-validator compatibility and independent denial-session tests pass. SQLite alone insufficient. A16/A37/A39/A40; approved deployment privilege fixture A41 before resistance claim. |
| REGRESSION | All required focused suites and full backend pass without unexpected skips; E04-R original blocker remains behavior-tested; no auth/process/read expansion. |
| CI | Exact eventual E05 pushed SHA: completed successful Quality backend, postgres, frontend, security, containers and quality-gate jobs. No claiming closure on an older run. |
| NO STAGING MUTATION | All design/development validation disposable; DB checksum and unrelated-work preservation verified; migration/deployment/Render/staging operations require separate explicit authorization. |

For eventual local validation use existing `.venv-ci/Scripts/python.exe -B -m pytest -p scripts.ci_pytest -q -p no:cacheprovider` with LEADFORGE_CI=1, AI_PROVIDER=mock and supported test isolation. Add future audit tests to focused E04/E03/E02/conflicts/tenant/import/auth/password/observability set, then full `tests/`. Run existing pip check, vulnerability audit, Gitleaks and diff checks. PostgreSQL goes through the existing disposable loopback service gate; if unavailable locally, mark NOT RUN and require the exact-SHA CI postgres job. Never supply a staging/admin connection as a substitute.

The 56 planned scenario rows include evidence cardinality/size/closed schema, org deletion without FK, missing authority version and application-boundary settlement coverage. No implementation tests were run by D2.

Current predecessor context, not new tests run by this design task: E04 66, E03 42, E02 22; expanded 221; password/concurrency 23; auth API 13/foundation 3; tenant Lead 30/attack matrix 5; CSV 3/conflicts 2; observability 10; full 572 +40 subtests. Future totals will increase; explain collection changes rather than matching a count by disabling tests.

## Design review answer checklist

| Question | Proposed answer / location |
|---|---|
| What is/is not an AuditEvent? | Bounded server historical evidence, not grant/command/outbox/full record; design scope. |
| Initial records / outcomes? | Three protected command successes, first decisive permission denial, attributable tenant mismatch; SUCCEEDED/DENIED. Account/failed-command events deferred. |
| Snapshots/FKs/tenant isolation? | Actor/delegator/provenance/target snapshots; organization required historical identifier with no hard FK; every read scoped. Schema column/deletion sections. |
| Atomic success? | Same E02 Session; append/flush before root commit; audit failure aborts mutation. |
| Durable denial? | Explicit application/audit context captures first rejection, root rollback/cleanup, best-effort short independent audit transaction; no audit-only commit of business Session. |
| Audit failure? | Success fails closed; denial stays original denial with safe missing-evidence signal, bounded crash/outage gap. |
| Failed execution? | Operational logging only initially; no surviving success/FAILED promise after rollback. |
| Update/delete/hardening? | No supported mutation API, guarded ORM; no DB-level append-only restriction currently. Future explicit privilege carve-out, admin limits and exceptional privacy operations. |
| Tamper evidence? | Deferred, no hash chain; later protected independent anchors. |
| PII/secrets/retention? | IDs can be personal data; no content/endpoints/transport/IP/prompts. Closed bounded details; production retention/hold/deletion approval pending. |
| Bulk behavior? | One command event incl no-op/duplicate replay; counts only, not per-row lineage or token/file signature. |
| Exact schema/index/migration? | Complete 22-column table, five indexes, portable enums/checks; additive revision after e5d4c3b2a1f0, no ID assigned or migration generated. |
| PostgreSQL requirements? | UTC, constraints, independent sessions, concurrent transitions/uniqueness, schema heads, later app privileges; mandatory exact-SHA Quality job. |
| E07/E09/E10/E11? | Delivery infrastructure, proposed actions, policy and approvals remain independent; future reviewed links/event extensions. |

## Design-task verification boundary

E05-D2 may modify only the three existing E05 documents. No production/test/migration change or runtime test/migration is necessary for documentation. Verify UTF-8/readability, cross-document field/count/decision consistency, whitespace and secret safety; before/after git status, empty index and HEAD; compare pre-existing file hashes excluding private environment files and operator content; compare operator metadata only and leadforge.db checksum.

Required database checksum: `217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a`. Preservation claims must state the actual hash/metadata coverage; no environment-secret or operator-script content inspection. `git diff --stat` excludes untracked new documents, so report their paths/line counts separately without staging. Leave architecture decisions visible for review; no source fixes, migration ID, dependency or E06+ implementation.
