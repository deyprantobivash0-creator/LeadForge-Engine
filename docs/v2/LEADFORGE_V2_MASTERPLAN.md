# LeadForge V2 engineering masterplan

**Product:** LeadForge — Human-Governed Autonomous Revenue Operating System.
**Audit date:** 2026-10-12 (Asia/Dhaka). **Code baseline:** `641658ef6510438e10470fc5b7a448acaa91005f` on `main`.
**Status:** proposed architecture and implementation plan, not implemented V2 behavior or deployment approval.

## How to use this package

Read this audit first, then [architecture](LEADFORGE_V2_ARCHITECTURE.md), [domain model](LEADFORGE_V2_DOMAIN_MODEL.md), [agents](LEADFORGE_V2_AGENT_ARCHITECTURE.md), [governance](LEADFORGE_V2_SECURITY_GOVERNANCE.md), [integrations](LEADFORGE_V2_INTEGRATIONS.md), [UX](LEADFORGE_V2_UX_ARCHITECTURE.md), and [roadmap](LEADFORGE_V2_ROADMAP.md). The roadmap ends with fifteen independently reviewable foundation epics in execution order. Approve an epic and its migration plan before implementation; this package authorizes none.

The product cycle is **understand → discover → explain → propose → govern → execute → observe → learn → govern again**. Sending messages is one permitted outcome, not the definition of the product. Human operators own business goals, budgets, acceptable markets, policies, and material strategy changes.

## Audit method and evidence limits

Inspected registered FastAPI routes, dependencies, services/repositories, all model families, migration revision headers, active React routing/state/client, canonical and legacy AI paths, runtime/Render/Kubernetes assets, CI definitions, test fixtures, and backup tooling. No application, database, deployment or provider operation was executed. Historical local results and the prior successful Quality run are context, not fresh runtime verification. Current Render settings/data were not queried. Documentation contains historical statements contradicted by later code; implementation evidence takes precedence.

The worktree includes unrelated deployment changes and untracked operator/database files. In particular `_temporary_staging_login.py` is present again at this audit baseline. Its contents were not inspected or printed; it was not executed or removed. Files were checksummed only to verify preservation. V2 analysis must not absorb that work into a claimed published baseline. No environment-secret file was read. Runtime configuration assets describe intended behavior; they do not prove the live staging topology.

## Verified repository map

| Area | Actual implementation and evidence | Implication for V2 |
| --- | --- | --- |
| HTTP application | `backend/main.py` registers auth, organizations, leads, imports, dashboard, reports, Settings, system routers; middleware bounds requests, sets headers, request IDs and safe logs | Keep thin routes and established error behavior; add explicitly versioned V2 contracts |
| Identity/session | `models/user.py`, `auth_session.py`; `services/authentication_service.py`, `repositories/auth_repository.py`; Argon2id, hashed random session/CSRF tokens, active-user validation, revocable sessions, guarded issuance, password change | Reuse; add recovery/onboarding/MFA and scoped machine principals without replacing browser authentication |
| Organizations | `organization_membership.py`, membership repository, organization dependency and authorization service | Selected header is validated membership context, never authority by itself |
| RBAC | Membership stores owner/admin/member; registered business dependencies check active membership, not an action-permission matrix | Roles exist; enterprise authorization does not yet exist |
| Persistence | SQLAlchemy models: User, AuthSession, OrganizationMembership, Organization, Lead, LeadAnalysis, IngestionJob; `database/session.py` uses one canonical engine/session factory | Extend through Alembic; no generic agent database sessions |
| Migrations | Six revisions: `9ed1e76d4c54 → e37cdcdf31dd → 24b5b28b09b7 → c3b2a1d0e9f8 → d4c3b2a1e0f9 → e5d4c3b2a1f0` | Do not rewrite history; test additive upgrade/backfill on disposable PostgreSQL |
| Lead operations | `api/routes/lead_routes.py`, lead/lifecycle services and repository; tenant predicates, unique tenant/email, lifecycle fields and pagination | Preserve API; Lead cannot substitute for a normalized account/contact/opportunity model |
| Intelligence/history | `lead_intelligence_service.py`, `lead_analysis_repository.py`; latest linked analysis by created_at then ID; composite tenant/Lead foreign key | Preserve historical facts and current projection; extend evidence rather than invent customer facts |
| Scoring | `decision/lead_scorer.py`: 40/25/35 weights, half-up rounding, Hot ≥80 and Warm ≥60 | Keep deterministic V1 scoring unchanged; future score versions require explicit evidence and rollout |
| Canonical AI | `LeadProcessingService → LeadBrainWorkflow → AIRouter/AIProvider`; sequential company/contact/intent assessments, app qualification; Pydantic validation | Reuse as a bounded worker activity; scores are assessments of supplied fields, not verified research |
| Processing concurrency | `lead_processing_repository.py`: 15-minute claim, attempt-ID guarded complete/fail; provider outside database transaction | Useful fencing precedent; no durable queue, restart resume, scheduler or approval pause |
| Providers | Mock, Gemini async SDK, Ollama async HTTP with status checks; structured parsing, timeouts and bounded transient retries; DeepSeek unsupported | Existing foundation is stronger than older AI documentation claims; no provider/tool cost ledger |
| Legacy paths | `backend/graph/`, `backend/workflows/`, specialized legacy agents/orchestrator and old ingestion generations coexist; empty ingestion router unregistered | Quarantine with import/dependency tests; do not expand or delete before callers are mapped |
| CSV | `LeadImportService`, repository, import routes: preview digest/session binding, bounded re-upload, tenant dedupe, savepoints and one confirm commit | Reuse parsing and duplicate safety; add durable import lineage/history later |
| Dashboard/reports | Dashboard v2 current Lead snapshot; Reports v2 historical analysis activity and streamed CSV with organization/date filters | Counts are not pipeline revenue, attribution or meeting outcomes |
| Settings | Safe local provider-readiness/capability overview; browser sign out; ChangePasswordForm and reviewed backend | No connector setup, provider administration or subscription management |
| Frontend | `App.jsx` React Router; AuthContext restores user/memberships, requires workspace, remounts shell on change; page-local state; API returns JSON directly | Retain credentials/CSRF/error semantics; add cache invalidation and durable activity projections |
| Runtime | Non-root Docker/Nginx, health/readiness and schema-head gates, Compose fixtures; Render adapter separates operator migration from startup | Add workers and external-action gateway with separate credentials; no deployment in this audit |
| Render | `render.yaml` specifies manual deployment; `deploy/render/runtime.py` mock staging restrictions, safe diagnostics, one Uvicorn worker | Repository intent only; neither live settings nor a V2 production platform verified here |
| Kubernetes | Local manifests, migration/provision/seed jobs, probes, resource/security contexts and verification scripts | Local rehearsal assets, not evidence of enterprise HA, autoscaling or worker isolation |
| Observability | JSON event allowlist, redaction, bounded stack metadata, request correlation and processing events | Operational logs are not immutable enterprise audit records or causal execution traces |
| Verification | Isolated `tests/`, disposable `tests_postgres/`, mock-only AI, attack matrices, migrations, backup/runtime tests; Playwright runtime suite plus isolated password suite | Extend tests for replay, competing workers, policy changes, duplicate webhooks and channel contracts |
| CI | `.github/workflows/quality.yml`: backend, PostgreSQL, frontend, security/secrets, containers, final quality gate | Keep required gates; browser/runtime scripts are not all automatically exercised by this workflow |
| Recovery | `scripts/postgres_backup.py`, recovery drill: manifests/checksums, bounded tools, empty-target restore guards; role provisioning assets | Add scheduled encrypted offsite backups, PITR, recovery SLAs and restore reconciliation before autonomous work |

## Capability gap register

Classification concerns the requested V2 capability, not whether a file exists. EXISTS = working constituent with a registered path; PARTIAL = usable subset; MISSING = no executable domain; NEEDS_REFACTOR = existing path must change ownership/execution before extension.

| V2 capability | Class | Evidence / missing scope | Program |
| --- | --- | --- | --- |
| Production-grade SaaS accounts/workspaces | PARTIAL | Password/session/tenant foundations; no registration/invite lifecycle, recovery, MFA, billing, entitlement enforcement or administrative audit | 0–1 |
| Revenue Brain | MISSING | No workspace business-knowledge/version/source domain | 2 |
| Autonomous lead discovery | MISSING | CSV/manual create only; no licensed source adapters or discovery runs | 3 |
| Enrichment and signals | MISSING | AI receives four Lead fields; no contact verification, monitoring or source events | 3 |
| Opportunity intelligence | PARTIAL | Lead score/next action/history exists; account graph, buying committee, deal amount/stage and explanations across evidence missing | 2–3 |
| HITL policy engine | MISSING | No action proposal, policy decision, approval or execution authority records | 0, 4 |
| Autonomous outreach | MISSING | No campaigns, sequences, send ledger, suppression or dispatch | 4 |
| Reply intelligence | MISSING | No reply ingestion, conversation state or stop-on-reply logic | 4–5 |
| Nurturing | MISSING | Follow-up date query is not a durable nurture workflow | 4–5 |
| Email/calendar/CRM integrations | MISSING | Empty integrations package; configuration placeholders are not adapters | 1, 4–5 |
| Messaging | MISSING | No channel transport or consent/endpoint model | 5 |
| ElevenLabs/Twilio voice | MISSING | No calls, telephony, streaming media or transfer integration | 5 |
| OpenClaw | MISSING | Settings marks automation unavailable; no command adapter/gateway | 6 |
| WhatsApp/Telegram owner control | MISSING | No paired external identity or scoped commands | 6 |
| Durable autonomous agents | NEEDS_REFACTOR | Request-bound LangGraph compiles without checkpointing; Lead attempt lease cannot resume a multi-day workflow | 0 |
| Revenue Autopilot | MISSING | No goal/plan/budget/portfolio objects or execution loop | 7 |
| Self-learning GTM intelligence | MISSING | No outcome labels, experiment assignment, evaluation or governed strategy versions | 7 |
| Enterprise auditability | PARTIAL | Safe diagnostic events exist; immutable action/decision/approval lineage absent | 0–1 |
| Compliance controls | PARTIAL | CSRF, tenancy, input limits and CSV safeguards; no lawful-basis registry, suppression, retention, rights workflows or voice rules | 0–5 |
| Production reliability/security | PARTIAL | Runtime/CI/recovery foundations; distributed budgets, workers, connector isolation, SLO evidence and live operational controls missing | 0–1 |
| Own-password change constituent | EXISTS | Registered endpoint, Argon2id reuse, CSRF, session revocation and issuance guard, deterministic tests | Retain |

## Reuse, evolution and unchanged contracts

Reuse FastAPI, SQLAlchemy/PostgreSQL, Alembic, active membership resolution, Argon2id/session/CSRF helpers, structured provider validation, deterministic scoring, linked analysis history, scoped repositories, CSV validation, safe errors/logging, React shell/client, and isolated test/CI infrastructure. Do not rewrite authentication, replace React, or split into microservices merely because agents are added.

Evolve transaction ownership: `LeadRepository.create_lead` and lifecycle repository operations currently commit internally, while import/processing/auth services own wider transactions. A targeted unit-of-work epic must make new multi-step V2 writes service-owned without breaking V1 behavior. Keep the account-level password exception to organization scoping: it remains authenticated-user-only.

Preserve V1 route/JSON shapes and current scoring semantics. A Hot Lead is not an outreach authorization. Keep mock AI usable without paid services, no automatic live provider selection, no silent default organization, no implied CRM connection, no migration-on-app-import, and no current-worktree deployment tooling folded into V2 source.

## Principal risks and sequence

1. Governance TOCTOU: approval becomes stale before send. Bind exact content/recipient/cost and reauthorize at execution.
2. Retry ambiguity: provider accepted a send before timeout. Reconcile; never promise exactly-once external delivery.
3. Worker tenancy: queued identifiers bypass membership checks. Persist tenant/principal scope and recheck grants before effects.
4. Prompt injection/data exfiltration: research, replies and voice transcripts are untrusted input, not instructions.
5. Coupled person/company Lead fields: normalization/backfill must retain original values and never merge across tenants.
6. Budget races: plan strings and lead-limit fields are not usage enforcement. Reserve cost atomically before dispatch.
7. Channel/legal mismatch: B2B email, messaging and synthetic voice require distinct jurisdiction policies.
8. Durable replay/version drift: long runs must pin versions and survive code changes, expiration and deletion.
9. Evidence contamination: AI-inferred facts cannot become user-confirmed through repeated summarization.
10. Provider/platform exposure: shared operator bots are not the LeadForge tenant boundary.

Implement Programs 0–1 foundations first, then Brain and discovery, then governed email outreach, then new channels/Commander, and finally bounded Autopilot. Run shadow proposals and outcome measurement before granting autonomous execution. Release gates, not calendar dates, determine readiness.
