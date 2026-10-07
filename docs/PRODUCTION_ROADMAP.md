# Production roadmap

## October 6, 2026: Step 5B local runtime

Step 5A PostgreSQL verification and Step 5B container/runtime verification are
complete in the local disposable environment. Step 5B adds non-root application
images, production frontend assets, same-origin proxying, private database
networking, coordinated migrations and truthful readiness. Clean/cached builds,
functional/browser smoke checks, persistence and controlled dependency failures
were verified. See [runtime commands and evidence](CONTAINERS.md).

This is not production readiness: mock AI and local development cookie settings
remain explicit. Step 5C configuration/secrets and all subsequent milestones
remain unstarted by this work. Older milestone notes below describe their
historical context; this dated local verification is the current runtime status.

Phase 4 customer-facing product surface is complete after Step 4G integration
and release-surface QA. This is not production readiness. Phase 5 must still
verify database migrations on PostgreSQL, container/runtime configuration,
secrets, observability, security hardening, CI and tests, backups and recovery,
deployment, real provider operation, performance, and release validation.

Step 4F adds the truthful Settings & Integrations workspace. HubSpot, OpenClaw,
CRM synchronization, provider connectivity checks, account credential changes,
and production operations remain planned work. Step 4G completed the product
surface audit; Phase 5 infrastructure has not begun.

Step 4E adds tenant-scoped historical Reports v2 and a CSV export. It does not
establish production readiness. Remaining Reports work for a later milestone
includes PostgreSQL runtime verification, export load testing, and an audited
policy for historical noncanonical priorities. Step 4F remains unstarted.

This roadmap starts from the current working tree, not an assumed production architecture. A milestone is complete only when its exit criteria are demonstrated in an isolated environment. Within each phase, complete prerequisite milestones before dependent product flows. No application changes are authorized by this document alone.

Steps 3B.2C–D established authenticated, membership-authorized Lead, Dashboard, and Report routes. Analytics SQL now scopes aggregates, rankings, limits, and date windows to the authorized Organization; isolated repository and two-tenant HTTP tests pass. The local development database remains unmigrated and unseeded for login; production readiness milestones below remain open.

## P0 — Production Safety & Baseline

| Milestone | Objective | Dependencies | Major deliverables | Exit criteria |
| --- | --- | --- | --- | --- |
| P0.1 Reproducible repository | Make the actual source and dependency baseline reviewable. | Current-worktree inventory. | Resolve intended untracked/deleted files; reconcile Python/Node manifests; repair syntax/import blockers, including AI company schema; clean-install instructions. | A clean checkout installs, imports the registered app without side effects, and passes agreed static checks without credentials. |
| P0.2 Identity and tenant context | Replace shared development organization on business paths. | P0.1 and a membership/data migration design. | Authentication design, User/Membership ownership, authorized organization dependency, route/service context rules. | Requests without valid membership cannot read or mutate customer data; no business route creates or selects the shared default organization. |
| P0.3 Tenant isolation | Close cross-tenant analytics and prove scoping. | P0.2. | Tenant-scoped lead, intelligence, dashboard, report, and job queries; two-organization integration tests. | Overlapping data from two organizations never crosses list, detail, update, analytics, or background-job boundaries. |
| P0.4 Migration baseline | Establish safe schema evolution. | P0.1; P0.2 schema decisions. | Review existing Alembic chain, default/constraint drift, clean and legacy upgrade scenarios, disposable PostgreSQL migration run. | Clean SQLite and PostgreSQL databases reach head; representative existing data upgrades without loss; drift and rollback policy documented. |

## P1 — Core Platform Stabilization

| Milestone | Objective | Dependencies | Major deliverables | Exit criteria |
| --- | --- | --- | --- | --- |
| P1.1 Contract and transaction policy | Make API and persistence operations predictable. | P0 tenant context and migration baseline. | Versioned response shapes, lifecycle/priority vocabulary, error model, operation-level transactions, duplicate handling, Lead-to-Analysis relationship and current/history decision. | Contract tests cover create/list/detail/lifecycle/intelligence; concurrent duplicates map to defined errors; partial multi-step writes roll back. |
| P1.2 Canonical AI foundation | Select one executable processing architecture. | P1.1 relationship/transaction decisions. | Consolidated workflow, provider factory/injection, async contract, mock path, structured validation, deterministic scoring and result provenance. | Mock end-to-end analysis passes in isolation; malformed/provider failures are bounded and tested; competing paths are classified for later retirement. |
| P1.3 Verification and operability | Make change safety repeatable. | P0.1, P1.1–P1.2. | Isolated test fixtures, safe pytest target, single health/readiness contract, request/error observability, frontend API wrapper consistency and case-sensitive import checks. | CI can run safe tests and frontend lint/build; readiness fails correctly when required dependencies fail; no external AI call is needed. |

## P2 — Product Functionality

| Milestone | Objective | Dependencies | Major deliverables | Exit criteria |
| --- | --- | --- | --- | --- |
| P2.1 Tenant-owned ingestion | Turn CSV/import intent into a reliable job. | P0 tenant context; P1 transaction/contract policy. | Registered import API, normalization, validation, deduplication, Lead writes, IngestionJob statistics, row errors, limits, retry/idempotency policy. | Valid, duplicate, malformed, and partially failing imports produce correct tenant-owned records and counts. |
| P2.2 Processing and Lead Brain persistence | Analyze an authorized Lead safely. | P1.1–P1.2. | Process endpoint/service, pending→processing→completed/failed transitions, duplicate guard, persisted result/score/action/evidence, current intelligence retrieval. | Mock provider flow survives retry/failure tests and returns the persisted result for the same lead and tenant. |
| P2.3 Lead Intelligence M2.1 and live workspaces | Replace fixtures with honest product views. | P2.1–P2.2 and stable API contracts. | Lead directory/detail, Open Lead fetch, Analyze Lead refresh, evidence/confidence UI, Import Center, live dashboard/reports, loading/error/processing states. | UI can import, open, analyze, revisit, and report on tenant data; no hardcoded intelligence is presented as real. |

## P3 — Commercial & Production Operations

| Milestone | Objective | Dependencies | Major deliverables | Exit criteria |
| --- | --- | --- | --- | --- |
| P3.1 Production platform | Operate the service on PostgreSQL. | P0 migrations; P1 verification; P2 product paths. | PostgreSQL deployment, Docker configuration, CI/CD, structured observability, backup/recovery and deployment runbooks. | Staging deployment, migration, health, recovery, and rollback exercises pass. |
| P3.2 Commercial controls | Enforce paid usage and provider budgets. | Auth/membership, processing telemetry, production platform. | Usage metering, plan enforcement, provider cost limits, per-tenant quotas and audit records. | Limits cannot be bypassed through concurrent or alternate endpoints; usage reconciles with operations. |
| P3.3 Integrations | Add external revenue operations workflows. | Stable tenant/API contracts and commercial controls. | HubSpot and OpenClaw integration designs, tenant-scoped credentials, synchronization and retry policies. | Sandbox integration tests prove ownership, idempotency, failure recovery, and credential isolation. |

Step 3B.2E established the frontend authentication/workspace shell and real Lead, Dashboard, and Report reads. Later Phase 4 milestones added the Intelligence, Import, Reports v2, and Settings workspaces. Overall production readiness remains open. The development account requires an explicit manual bootstrap after migration.

Step 4D adds the authenticated CSV Import Center with bounded preview and explicit tenant-owned Lead creation. It does not use the legacy AI ingestion path or `IngestionJob`, and it does not start Lead Brain processing. Durable import history, audit/retry controls, and PostgreSQL concurrency verification remain P2.1 follow-up work. Steps 4E and 4F added historical Reports and read-only Settings; Step 4G audited the combined product surface.

Review this roadmap after each milestone. A planned integration or UI capability must not be described as implemented until its exit criteria pass.
# Step 3C to 3D handoff

3C establishes the direct tenant-safe Lead–Analysis history link, typed lead
detail/intelligence/lifecycle/history responses, and the canonical vocabulary.
Step 3D should implement one processing orchestrator with mock-provider tests,
explicit state transitions, short transaction boundaries, validated provider
output, failure recovery, and scoring-policy confirmation. No production AI
processing or UI redesign is delivered by 3C.

## Step 3D delivered and Step 4A scope

Step 3D registers the tenant-authorized Lead Brain process route, atomic
processing lease, async LangGraph, bounded provider abstraction, structured
evidence, application-owned scoring, history writes, and a minimal LeadDetails
action. Automated checks use mock only. Gemini and Ollama require manual
verification; DeepSeek remains unsupported. Step 4A should address operational
provider smoke tests, PostgreSQL migration/runtime verification, model output
review and provenance policy, processing observability, and the legacy AI and
ingestion path retirement plan. Premium intelligence UI remains separate.
