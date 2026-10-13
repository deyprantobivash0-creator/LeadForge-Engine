# E05 proposed audit schema and migration plan

E05-D2 refinement: 2026-10-13. Baseline `e38d1863fcba8bbd331808a25d546275ffc0bbdb`. **Proposal only. No revision ID generated, migration file created, model installed or database accessed.** [Behavior/security design](E05_AUDIT_LEDGER_DESIGN.md), [acceptance gates](E05_ACCEPTANCE_CRITERIA.md).

## Physical choices and repository conventions

Propose one table, **audit_events**, mapped through existing Base/naming convention. V1 Organization/User/Lead IDs remain integers. Use canonical hyphenated UUID4 string for event_id: standard-library uuid4 generates it before persistence, no new dependency, same family as existing correlation/processing IDs. SQLAlchemy `String(36)` on both dialects avoids a PostgreSQL-native UUID dependency or SQLite representation mismatch. UUID4 has random index locality; acceptable for bounded v1 volume, benchmark later. Do not invent UUIDv7 support in Python 3.12 or rewrite V1 IDs. Event ID is neither command idempotency key nor commit sequence.

Use application StrEnum + portable String + named CHECK for explicit event/action/outcome/principal/reason columns. JSON evidence permission/decision/reason values use strict application enums, not SQL native enums or per-item DB CHECKs. Avoid native PostgreSQL enums and their extension/downgrade friction. Each accepted taxonomy change requires application compatibility and a reviewed CHECK migration; a payload schema_version alone cannot admit a new DB enum value. Use portable SQLAlchemy JSON (PostgreSQL JSON, not JSONB; SQLite JSON serialization), matching LeadAnalysis convention. No JSON index or arbitrary queryable payload.

All timestamp values are aware UTC in the audit API. `DateTime(timezone=True)` maps to PostgreSQL TIMESTAMPTZ; SQLite needs an explicitly tested audit-only adapter: normalize aware input to naive UTC at bind and reattach UTC on result (or equivalent tested portable type). Reject naive input. Do not change V1 naive UTC columns or silently reinterpret arbitrary offsets as UTC. Two timestamps have distinct sources: occurred_at is server-observed decision/result time; recorded_at is UTC sampled by the append writer at insertion. Neither means database commit time; no ordering/uniqueness inference from clocks. No recorded_at>=occurred_at CHECK: clocks can move and separate denial writers may differ. Both values must be supplied/validated; no server or Python automatic default that conceals missing event context.

## Complete 22-column proposal

`N` means NOT NULL; `Y` means nullable. No column has a SQL server default, onupdate default or independent unique constraint unless noted. `details` uses a fresh Python empty-dict builder when the closed schema is empty; schema_version is explicitly stamped by the builder, not inherited from DB defaults. Index abbreviations are defined below. Snapshot columns carry the historical value, not an ORM relationship. This table has no hard foreign keys; authority_version and all six fixed permission-slot columns are absent.

| Column / database type | Null / default | FK / uniqueness / index | Purpose and source of truth | Privacy, deletion and extension |
|---|---|---|---|---|
| event_id String(36) | N / none | PK `pk_audit_events`; globally unique | Trusted server UUID4 assigned once to draft | Opaque identifier; stable through retry/transport, not authority |
| organization_id Integer | N / none | Historical snapshot, NO FK; all read indexes lead with org | Server-validated trusted tenant identifier | Required even after tenant deletion; no cascade/rewrite, no raw selector; tenant IDs must not be recycled |
| occurred_at DateTime(timezone=True) | N / none | Timeline / target / actor / action indexes | Aware UTC observed after result or decisive rejection, before commit | Bounded timing evidence; not exact commit order |
| recorded_at DateTime(timezone=True) | N / none | None | Aware UTC audit writer insertion time | Reveals delayed denial persistence; not transport/client time |
| event_type String(64) | N / none | CHECK v1 event types | Server event factory | Semantic class, not permission; reviewed extension |
| action String(64) | N / none | CHECK three enforced actions; action index | Canonical command's typed action | No model/client-selected arbitrary string |
| outcome String(16) | N / none | CHECK SUCCEEDED/DENIED | Server result classification | FAILED/etc not admitted until designed |
| reason_code String(48) | N / none | CHECK three v1 reasons | COMMAND_COMPLETED / ACTION_PERMISSION_DENIED / EXECUTION_TENANT_MISMATCH | No raw error text or SQL/provider message |
| principal_type String(16) | N / none | CHECK USER/SYSTEM/AGENT/WORKFLOW/INTEGRATION; actor index | Validated E03 principal snapshot | No FK to future principals; survives removal |
| actor_id String(128) | N / none | Actor index; no FK | USER positive integer encoded as canonical decimal; machine ID unchanged | Pseudonymous identifier can be personal data; never email/name |
| delegated_by_type String(16) | Y / none | CHECK nullable principal domain; no FK | Optional E03 immediate ActorReference type | Bounded one hop; no recursion/grant claim |
| delegated_by_actor_id String(128) | Y / none | No FK/index | Optional immediate delegator canonical ID | Snapshot survives user/machine deletion |
| correlation_id String(64) | N / none | Correlation index | Validated E03 correlation (HTTP request ID or trusted caller value) | Potentially caller-chosen; grouping only, no uniqueness/authentication |
| workflow_run_id String(128) | Y / none | No FK/index | E03 provenance if present | Existing machine identity string, not claim a WorkflowRun table exists |
| agent_id String(128) | Y / none | No FK/index | E03 provenance if present | Required/equal actor for AGENT by validator |
| integration_id String(128) | Y / none | No FK/index | E03 provenance if present | Required/equal actor for INTEGRATION; no credential reference |
| target_type String(32) | N / none | CHECK lead/lead_import; target index | Typed command target class | Add account/contact/campaign/intent types only through review |
| target_id String(128) | Y / none | No polymorphic FK; target index | Success: owned Lead decimal ID or import event UUID; denial: null | Does not copy unverified submitted resource ID; survives deletion |
| authorization_evidence JSON | N / explicitly built list, no default | No FK/index; closed repeating snapshot | Actual server E04 evaluations: 0..8 objects of permission/decision/reason_code, <=2048 canonical UTF-8 bytes | No arbitrary client JSON/capability dump; action-specific cardinality/order checks; future multi-check extension |
| authority_role String(16) | Y / none | CHECK null/owner/admin/member; no FK/index | Role of the exact live human snapshot used for evaluation; null for machine or unmapped/missing role | No client role, no membership FK or arbitrary unknown label |
| details JSON | N / builder {} where allowed | No FK/GIN index | Closed per-event supplementary metadata, <=2048 canonical UTF-8 bytes | Only lifecycle vocabulary/changed-field names or import counts; no payload dumping |
| schema_version SmallInteger | N / explicit 1 | CHECK =1 initially | Versions event envelope + per-event details/authorization-evidence interpretation | Not Alembic revision; new format needs compatible reader and constraint review |

The eight permission domain values are exactly lead.read, lead.create, lead.lifecycle.change, lead.process, lead.import, analysis.read, report.read, workspace.read. Other values are rejected by the application evidence validator; privileged raw SQL is outside this JSON-validation guarantee. The v1 **action** domain remains only lead.create, lead.lifecycle.change, lead.import; storing a read permission in the enum domain does not allow emitting a read event.

Authority role must be obtained from the same evaluation snapshot, not a second current-role lookup after mutation. Proposed E04 internal orchestration adjustment can return a bounded evaluated-authority receipt alongside PermissionDecision without accepting caller roles; no widening of authority or redesign of ExecutionPrincipal. For denial, the narrow check site must retain actual decision/receipt without parsing an exception message. PermissionDecision currently lacks role; this is a planned integration change, not existing evidence.

## Bounded authorization-evidence schema

Required JSON array, 0..8 items, <=2,048 UTF-8 bytes after deterministic canonical serialization. Each item has EXACTLY `permission`, `decision`, `reason_code`, all non-null stable E04 enum/string values. No optional arbitrary keys, nested metadata or capability list. Reject unknown/duplicate permissions, untyped values and contradictory reasons (PERMIT only PERMITTED_BY_ROLE/PERMITTED_BY_CAPABILITY; DENY only the six DENIED_* reasons). Serialize in actual evaluation order with fixed keys/compact separators, never alphabetically reorder short-circuit checks. Construct from typed server evaluation receipts; no caller dictionary, request body or arbitrary JSON input is accepted by the append API.

The generic container bound supports future repeating checks, not new current command requirements: action/event validators enforce the exact initial rows below. The max-eight validator test is separate from a complete v1 command envelope; create with eight evidence items must fail its one-check contract. Oversize tests exercise rejection of oversized malformed material, without relaxing enum domains to generate large valid items. Authorization evidence and details have independent 2,048-byte budgets (maximum 4,096 canonical JSON bytes together, plus bounded explicit columns).

| Case | authorization_evidence in evaluation order | Required result |
|---|---|---|
| Successful create | Exactly one lead.create/PERMIT/actual reason object | SUCCEEDED; lead target ID; details={} |
| Successful lifecycle | Exactly one lead.lifecycle.change/PERMIT/actual reason object | SUCCEEDED; owned lead target; safe lifecycle details |
| Successful import | Exactly two: lead.import/PERMIT, then lead.create/PERMIT, each with actual reason | SUCCEEDED; lead_import target/event UUID; four bounded counts |
| Denied create/lifecycle | One corresponding permission/DENY/actual reason | DENIED; target_id=null, details={} |
| Import denied at first check | One lead.import/DENY/actual reason | DENIED; no fabricated second decision; action defines the unevaluated requirement |
| Import denied at second check | lead.import/PERMIT, then lead.create/DENY, each with actual reason | DENIED; not OR; target_id=null |
| Trusted principal/explicit tenant mismatch | Empty array [] | security.command.rejected/DENIED; EXECUTION_TENANT_MISMATCH; target_id=null |

One event carries all actual evaluations for its command. Preserve actual reason/role snapshots, not a new post-mutation authority lookup. This bounded repeating structure avoids numbered columns and a child table's joins/inserts while keeping tenant, actor, action, outcome, target and correlation query dimensions explicit. No evidence JSON index or query contract initially; revisit a child table only if measured query/volume requirements make JSON materially unsuitable.

**authority_version removed:** there is no authoritative version in current E04. No synthetic e04-1, application-build substitution or schema_version-as-authority. schema_version versions only the event envelope/details/evidence shape. Future genuinely versioned grants/policies can add truthful references after their owning epic is implemented and reviewed.

## Revised constraints and validation boundary

Use Base naming convention and reviewed emitted names; avoid doubled CHECK prefixes:

* `ck_audit_events_domains`: explicit event_type/action/outcome/reason_code/principal/delegator/target_type/authority_role domains only; split names if useful. JSON item permission/decision/reason domains are strict application validation, not this CHECK.
* `ck_audit_events_event_outcome`: completed iff SUCCEEDED/COMMAND_COMPLETED; permission.denied iff DENIED/ACTION_PERMISSION_DENIED; security.command.rejected iff DENIED/EXECUTION_TENANT_MISMATCH. Use explicit NULL-safe branches.
* `ck_audit_events_tenant_positive`: organization_id>0. **No organization FK** and no live-row existence requirement for historical reads/post-settlement denial persistence. Ordinary business append builders verify currently valid tenant ownership; denial builders require captured trusted scope.
* `ck_audit_events_bounds`: explicit positive bounded String lengths, correlation 1..64, event_id length 36, schema_version=1. SQLite VARCHAR alone does not enforce length. Strict UUID/ASCII/decimal shape remains application validation.
* `ck_audit_events_delegator_pair`: both delegator fields null or both present; USER no machine/delegated provenance; AGENT/WORKFLOW/INTEGRATION required matching provenance. No identifier FK.
* `ck_audit_events_target`: action/target_type mapping, successful target_id required and denied target_id forbidden, using explicit IS NULL/IS NOT NULL conditions.
* NOT NULL constraints include organization_id, authorization_evidence, details and other required columns. Validators reject JSON null as well as missing values; SQL JSON null may differ from SQL NULL and must not evade the append contract.

Delete fixed permission-pair/command-authority slot CHECK proposals. **Action-specific JSON authority completeness, enum/reason consistency, cardinality, ordering, byte/depth limits and details allowlists are mandatory application checks.** No PostgreSQL-specific JSON path trigger or portable-equivalence claim is added. Raw inserts can bypass JSON semantics; they must not be cited as proof that the DB alone enforces import AND or secret safety. Raw SQL tests prove the actual explicit-column constraints; application tests prove JSON and cross-envelope evidence rules. Existing E04 remains the authorization enforcement boundary; ledger data never grants permission.

Details are constructed from event-specific server allowlists: create/rejection {}, lifecycle statuses and changed field names, import counts. Bound <=2,048 canonical UTF-8 bytes, <=2 depth, <=8 keys, no floats/NaN. Prohibit arbitrary caller dictionaries, ORM serialization, request-body serialization and "sanitize then store everything". A required success event failing validation rolls back business mutation. Denial draft/append validation failure preserves DENY with safe evidence-loss diagnostics.

## Index and query plan

No standalone speculative indexes on nullable provenance or JSON evidence. Proposed five B-tree indexes:

| Index | Columns, in order | Bounded query |
|---|---|---|
| ix_audit_events_org_time | organization_id, occurred_at, event_id | Tenant/time timeline; outcome filter applied within bounded time window |
| ix_audit_events_org_actor_time | organization_id, principal_type, actor_id, occurred_at, event_id | Actor history; type avoids machine/user ID collisions |
| ix_audit_events_org_correlation | organization_id, correlation_id, occurred_at, event_id | Correlation trail with tenant predicate |
| ix_audit_events_org_action_time | organization_id, action, occurred_at, event_id | Action history / outcome-filtered investigation |
| ix_audit_events_org_target_time | organization_id, target_type, target_id, occurred_at, event_id | Resource history without resource joins |

PK index provides event equality lookup, but internal repository still includes organization_id. Initial list reads require explicit org, bounded [from,to) UTC range, limit 1..100 (default 50), safe typed filters and descending keyset `(occurred_at,event_id)`. Cursor validates shape and caller scope; it grants no access. Equal timestamp IDs produce deterministic tie-break order, not causal/commit order. No global timeline, unbounded OFFSET/export or operator bypass. Outcome-only queries are residual filters in a bounded tenant/time range; no JSON permission search surface initially; measure before adding an index. No global unique correlation/action/target constraint; retries and no-op invocations legitimately share those dimensions.

## Snapshots, deletion and causation

### Organization FK alternatives and selected snapshot

| Concern | A: hard FK + RESTRICT | B: non-null historical ID, no FK (selected) |
|---|---|---|
| Tenant isolation | Prevents missing live parent, but FK alone grants no access | Required tenant predicates and trusted writer validation; same access boundary |
| Query integrity | All parent rows must remain; joins convenient | Deleted-tenant historical rows intentionally valid; no live join required; explicit IDs remain queryable |
| Physical organization deletion | Audit rows block it until purged/relocated | Lifecycle policy decides deletion without a ledger FK veto |
| Append-only evidence | RESTRICT avoids cascades but couples org/evidence cleanup | Parent deletion does not cascade, null, mutate or delete history |
| Privacy deletion / holds | Enforces sequencing, not legal basis or erasure | Separately governed retention/holds/exceptional erasure; deletion alone does not erase audit |
| SaaS lifecycle / ID reuse | Retained parent helps prevent collision, but later purges still need identity rules | Must enforce non-reuse before deletion/re-provisioning; no new ID allocator/schema added in E05 |

Choose B. organization_id remains NOT NULL, positive and indexed; it snapshots trusted tenant identity, not a selectable client grant. It is not a FK, so the ledger does not dictate future org deletion policy. All identity/target fields are snapshots; table has **zero hard FKs**. Business success writer must validate the current organization/owned result before append. A post-settlement denial may use captured trusted identity after the org disappears, without reauthorizing the rejected action or creating a tenant row. Unknown/untrusted input cannot become a historical event merely by passing an integer check.

Physical org deletion leaves historical audit rows unchanged. Future privacy erasure/holds/archives remain explicit exceptional operations; no automatic cascade or evidence update. Historical records must not resolve to a new workspace by ID reuse. Current PostgreSQL sequences/SQLite allocation are not a permanent non-reuse contract. Before introducing org physical deletion/re-provisioning, require permanent non-reuse or an approved immutable tenant-generation mapping; that future feature is blocked without it. Current E05 adds no org lifecycle API. Live customer audit reads, if later added, must first authenticate current org membership and respect generation identity, never use a join to a recycled org ID as authority.

Actor, immediate delegator, target and machine provenance are identifiers captured from trusted command context, not FKs. User deletion/session cascade, membership role changes, Lead deletion or future agent/integration removal do not mutate events. Pseudonymous ID evidence survives, but reconstructing an erased person's identity may intentionally no longer be possible. IDs must not be reassigned; current SQLite integer allocation is not a guarantee of eternal identity non-reuse. Future deletion workflows must prevent ID recycling or introduce stable tombstone/opaque identity mapping before interpreting old actor IDs as current users. Initial E05 adds no physical delete route or such mapping.

Correlation preserves the E03 value with no separate redundant request_id column. Immediate delegator + workflow/agent/integration snapshots support bounded lineage; no recursive delegation blob. Explicit causation_event_id/parent_event_id, ActionIntent/grant/policy/approval/provider-receipt FKs and command idempotency are deferred because authoritative source objects do not exist. Later tables may reference audit event_id, with tenant binding checked and composite tenant FK/unique pair added by a reviewed migration when needed. E05 does not infer causation solely from a caller-supplied correlation.

## Future migration plan

Purpose: additive create-audit-events revision **after current `e5d4c3b2a1f0`**, provided it is still the sole head at implementation time. Assign the actual revision ID only after approval; do not invent it in this design. Upgrade creates one 22-column table, PK, two required portable JSON columns (authorization_evidence/details), named explicit-domain/outcome/provenance/target/bounds checks and five indexes; **no hard FKs, authority_version, fixed permission slots or child table**; no existing table rebuild/backfill or native enum. Register future AuditEvent in `backend/models/__init__.py` so Base metadata and schema verification see it. Alembic env already compares types/defaults and imports model metadata. No `create_all()` in runtime/startup; disposable test create_all remains fixture-only.

No V1 log/analysis backfill: logs cannot prove commit/authority, and replaying them would invent audit completeness and ingest PII. The ledger starts at the migration/integration rollout boundary. Old application processes may ignore the new table; they cannot remain active as unaudited writers after mandatory audit integration is enabled. Deploy matching code after operator migration, then verify every writing process runs the integrated version; readiness alone proves schema head, not event coverage.

PostgreSQL: migration role owns schema; app-role table DML/default privileges must be assessed separately, not altered as an incidental data migration. The current provisioning grants broad DML; no live audit restriction is claimed. Privilege carve-out is a future reviewed deployment gate. No triggers, RLS, partition, chain lock or external archive in initial revision. Review backup/restore table inclusion and role grants without staging access in implementation tests.

SQLite: create table with supported CHECK/JSON declarations (no audit FK) and matching indexes; enable foreign_keys in fixtures. If a later CHECK extension needs a table rebuild, it requires explicit migration/retention review; do not rewrite E05 history. Test audit-only UTC conversion, canonical UUID strings and independent denial Sessions against the SAME file-backed DB. In-memory engines that cannot provide separate connections are insufficient for denial durability tests. Preserve import's explicit outer BEGIN/savepoint semantics.

Downgrade: drops five indexes and the new table only, returns schema to the predecessor and leaves V1 business rows untouched. **Destructive to audit evidence**: allowed only in disposable tests or after an explicitly authorized export/retention/hold decision; never routine production rollback. Application rollback should leave ledger storage intact; use forward fixes for real evidence. Test empty and populated downgrade/upgrade in isolated databases and verify evidence loss is intentional, not silently described as reversible retention. No new startup migration runner.

During authorized implementation update all pinned schema-head expectations where repository searches find them (`scripts/ci.py`, readiness/runtime and migration tests), rather than weakening head checks. Future migration upgrade/downgrade, application JSON-evidence validation and privilege tests must run on disposable PostgreSQL 16.15 and SQLite. None ran in this design task.
