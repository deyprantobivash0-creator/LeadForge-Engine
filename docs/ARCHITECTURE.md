# Architecture

Step 5H prepares a separate staging Compose deployment with strict production
configuration, explicit synthetic mock opt-in, direct Nginx TLS termination and
non-superuser application/migration/backup roles. Remote deployment is pending
target/account/hostname authorization; local rehearsal is not a production or
remote staging readiness claim. See [staging runbook](STAGING.md).

The Step 5B local runtime uses a production-built frontend/Nginx proxy,
non-root FastAPI/Uvicorn image and PostgreSQL 16.15 on private Docker networking,
with a one-shot Alembic startup gate. The 5A host database workflow remains
separate. See [container runtime](CONTAINERS.md) for its local development/mock
configuration, commands and deployment limitations.

Step 4G completes the customer-facing Phase 4 surface for the current release
scope. The authenticated shell mounts Dashboard, Leads, Import, Intelligence,
Reports, and Settings for an explicitly selected workspace. Changing workspace
remounts route state. Unknown paths show a product-level not-found page; the
active Lead Details drawer follows the dark workspace theme and supports
keyboard focus and Escape. Phase 5 production engineering remains open.

Step 4F Settings is a read-only customer workspace. One authorized
`/api/settings/overview` request supplies the account, selected membership
role, workspace, safe local AI configuration status, and implemented capability
flags. The service evaluates configuration without constructing a provider or
making network calls. The frontend has no provider or integration mutation
controls; sign out reuses the established AuthContext logout flow. Switching
workspaces remounts the application shell and fetches a new authorized status.

Step 4E adds a versioned Reports workspace. Dashboard v2 is a current Lead
snapshot; Reports v2 is historical LeadAnalysis activity over a UTC period.
The report route authorizes the organization, the service resolves windows and
shapes typed responses, and the repository aggregates and ranks with SQL
tenant/date predicates. The React page makes one overview request and a
separate full-period CSV request on export. Legacy report routes remain.

## CURRENT state

The FastAPI application starts at `backend/main.py`. It registers auth, lead, import, dashboard, report, and system routes. Customer routes resolve an authenticated User and active Organization membership before tenant-scoped service/repository calls; writes and import preview require session-bound CSRF. Analytics aggregates, date queries, rankings, and limits apply the Organization predicate in SQL. The legacy `backend/api/routes/ingestion_routes.py` remains empty and unregistered. Lead processing is registered at `POST /api/leads/{id}/process`.

The React/Vite application starts at `frontend/src/main.jsx` and routes pages through `frontend/src/App.jsx`. `AuthProvider` restores `/api/auth/me`, loads active memberships from `/api/organizations`, and requires an explicit workspace before mounting the application shell. `frontend/src/services/api.js` returns parsed JSON, includes browser credentials, adds the selected organization header to customer requests, and reads the CSRF cookie for writes. Leads, Dashboard, Intelligence, Import, Reports, and Settings use registered backend APIs.

### Current domains

| Domain | Current implementation |
| --- | --- |
| Organizations and authentication | `User`, `OrganizationMembership`, and `AuthSession` back first-party login, logout, and current-user validation. `/api/organizations` lists only the caller's active memberships in active organizations. Customer routes require explicit `X-Organization-ID` selection verified again on every request; `/me` grants no organization context. |
| Leads and lifecycle | Lead CRUD subset, scoped repository methods, lifecycle validation and follow-up query. Routes now pass the authorized Organization ID; lead writes require CSRF. |
| Ingestion | Step 4D uses `LeadImportService` and `LeadImportRepository` for bounded CSV preview and explicit confirmation. The old file-path importer opens its own session and invokes the legacy AI graph/analysis-by-email path; it remains quarantined and unregistered. `IngestionJob` exists but is not used for Step 4D. |

Step 4D uses a signed, 15-minute preview token tied to the current auth session, user, organization, and SHA-256 file digest. Confirm re-uploads and revalidates CSV, so no uploaded file or preview state is stored. A service signs the token, validates rows, and owns the batch transaction; a repository performs tenant-scoped email queries and inserts. This works across app workers that share the auth database, without in-memory session affinity. Token reuse is harmless because confirm rechecks duplicates. There is no import history or durable idempotency key yet; a production job ledger, audit trail, and PostgreSQL concurrency test remain future work.
| AI processing | `LeadProcessingService` is the registered entry point; `LeadBrainWorkflow` is its async LangGraph, using the provider interface and application-owned scoring. Older graph/agent paths remain unregistered legacy code. |
| Intelligence | Lead and analysis history have a direct tenant-constrained link; current analysis is selected by timestamp and ID. |
| Dashboard and reports | Dashboard `/v2/overview` counts tenant Leads and uses each Lead's latest linked analysis (`created_at DESC, id DESC`) for current scores, priorities, and rankings. Its recent intelligence feed is historical analysis activity. The original `/overview` stays history based for existing callers. Reports continue to summarize historical analysis rows over selected periods; their `total_leads` field is an analysis-row count. |
| Integrations | Package placeholder only; no verified HubSpot or OpenClaw integration. |

## TARGET state

```text
Frontend -> FastAPI route -> request dependencies -> service
         -> repository -> SQLAlchemy model -> database
```

The customer request context must be:

```text
Authenticated User -> Membership -> authorized Organization
                   -> tenant-scoped service -> tenant-scoped repository
```

The route validates transport input and maps errors. A service owns the operation and transaction boundary. A repository performs all customer-data reads and writes with required organization scope. The schema and response contract are explicit; frontend services normalize them once. Background or AI work carries the same authorized tenant context and records an auditable state.

## CURRENT known architectural debt

- The shared development organization helper remains in code, but no registered business route uses it. `scripts/bootstrap_dev_user.py` is the explicit development-only setup path.
- Historical analyses without an unambiguous tenant/email match remain unlinked for review.
- `backend/graph/`, `backend/workflows/`, and `backend/ai/workflow/` compete or are incomplete. Do not extend one until the canonical path is selected.
- The legacy file-path importer remains unregistered; Step 4D's tenant-owned CSV preview and confirmation API is active. Durable import job history remains future work.
- The active frontend workspaces use registered backend response shapes. Some unused legacy components remain in the tree for later review.

## Step 3D processing ownership

The route authorizes session, organization, and CSRF; `LeadProcessingService`
owns the operation. `LeadProcessingRepository` atomically claims an attempt
and guards completion with its attempt ID. `LeadBrainWorkflow` runs company,
contact, and intent assessments through one `AIProvider` boundary. The graph
then uses `LeadScorer` for final score and priority. `AnalysisService` persists
the validated result and Lead update within one final transaction. Legacy
`backend/graph`, `backend/agents`, and `backend/workflows` are unregistered and
are not the canonical processing path.
- The Step 5A runtime requirements installed in a fresh Windows Python virtual environment and the registered app imported with mock AI and an in-memory SQLite URL. PostgreSQL runtime verification remains separate.

See [API contracts](API_CONTRACTS.md), [AI architecture](AI_ARCHITECTURE.md), and [database policy](DATABASE.md) for domain-specific decisions. These target boundaries are requirements, not claims of current behavior.
# Step 3C lead intelligence contract

`LeadAnalysis.lead_id` links a successful analysis to one tenant-owned Lead. A
composite foreign key on `(organization_id, lead_id)` prevents cross-tenant
links. Nullable `lead_id` retains unmatched historical records, which remain
available to tenant-scoped analytics but are not current intelligence. New
canonical writes require a linked Lead. Current intelligence is the linked
analysis ordered by `created_at DESC, id DESC`; history uses the same order.
The registered HTTP surface remains read-only for intelligence until Step 3D.
