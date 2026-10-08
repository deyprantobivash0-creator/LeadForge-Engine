# API contracts

Step 5E preserves successful response shapes and business semantics. Login accepts
email up to 254 and passwords of 1–1024 characters; extra login/lifecycle write
fields and NUL text are rejected with 422. Lead path IDs must be positive signed
64-bit values; search strings, pages and history offsets are bounded. Direct and
proxied requests are limited to 2 MiB, CSV to 1 MiB. Rejections include 400 Host,
413 size and 429 login budget with Retry-After. All customer API responses are
no-store. Production disables docs/OpenAPI. See [security policy](SECURITY.md).

## Runtime health and readiness (Step 5B)

`GET /health` remains process liveness and returns HTTP 200 with
`{"success":true,"status":"healthy"}`. `GET /ready` returns HTTP 200 with
`{"success":true,"status":"ready","database":"ok"}` only when database
access works and stored Alembic heads match the application's migration heads.
It returns HTTP 503 with `success:false`, `status:"not_ready"` and
`database:"unavailable"` or `"schema_outdated"` otherwise. Database exceptions
and connection details are not exposed. These routes require no authentication
and access no customer data. Duplicate unreachable definitions in `main.py`
were removed; the system router owns this surface.

The local Nginx runtime proxies `/api`, `/health` and `/ready` without changing
customer API paths/shapes, and exposes `/frontend-health` for static-server
liveness. See [container runtime](CONTAINERS.md) for the browser boundary.

## Settings & Integrations (Step 4F)

`GET /api/settings/overview` is a typed, read-only customer route. It requires
the authenticated session and an active membership in the organization selected
by `X-Organization-ID`; it returns `Cache-Control: no-store`. `account.email`
comes from the authenticated User. `workspace.id/name/slug/role` comes from the
authorized Organization and membership. The response contains safe AI status
and capability flags; it never serializes API keys, hostnames, environment
values, password hashes, session data, or CSRF values.

AI status checks local server configuration only. `configuration_ready` means
required settings are present, **not** that a provider is reachable, has
credits, or has an installed model. Mock is development/test only. Gemini
requires a configured key and model; Ollama requires a configured host and
model. DeepSeek is unavailable even if a key exists. The endpoint makes no
provider network call. CSV import and Reports are available; CRM sync and
automation integrations are not available in this release. Settings offers no
API to change providers, connect integrations, or alter account credentials.

## Reports v2: historical analysis activity (Step 4E)

`GET /api/reports/v2/overview` and `GET /api/reports/v2/export.csv` require an
authenticated session and an authorized `X-Organization-ID`. Both accept
`preset=today|7d|30d|custom` (default `30d`). Custom requires ISO dates `start`
and `end`, inclusive calendar dates in UTC, ordered and at most 365 days.
Invalid combinations return 422. The backend stores naive UTC and reports
half-open `[start, end)` windows. Today begins at 00:00 UTC and ends at request
time; 7d and 30d are rolling windows ending at request time. No timestamp
migration is part of this step.

The typed overview returns `period`, `summary`, `activity`,
`priority_distribution`, `top_opportunities` (at most 5), and
`recent_analysis_events` (at most 10). `analysis_events` counts persisted
LeadAnalysis rows. `unique_analyzed_leads` counts distinct non-null linked Lead
IDs with an event in the period. Repeated analyses count as multiple events
but one unique Lead. Unlinked legacy rows count as events but have `lead_id:
null`, never link to a Lead, and never contribute to the unique count or top
opportunities. `average_analysis_score` averages event scores and is null for
an empty period. Dashboard v2 instead averages each Lead's current analysis.
Hot/Warm/Cold counts are exact historical event priorities; all other stored
values appear in `Other` without remapping or modifying stored rows.

Activity is grouped by UTC hour for Today and UTC day otherwise, with zero
buckets filled over the selected window. Top opportunities choose the highest
score per linked Lead in the period (latest timestamp, then highest ID on a
score tie), then order by score, timestamp, and ID descending. Recent events
order by timestamp and ID descending and may repeat a Lead. Every SQL query
filters organization and period before aggregation, ranking, or limiting.

The CSV endpoint exports **all** historical events in the selected period with
`analysis_id,lead_id,company,email,score,priority,analyzed_at`; it uses the same
authorized filters, SQL ordering, streaming, CSV quoting, and spreadsheet
formula neutralization. No provider payload or credentials are exported. The
old `/daily`, `/weekly`, `/monthly`, and `/executive` routes remain for
compatibility; their `total_leads` field still means analysis rows and must
not be used for new clients.

## Step 3C lead contract

Lead priority is `Hot`, `Warm`, or `Cold`; lifecycle is `New`, `Qualified`,
`Contacted`, `Meeting`, `Won`, or `Lost`. Processing status is `pending`,
`processing`, `completed`, or `failed`. `LeadResponse` now includes
`processing_status`; the typed detail response adds `current_analysis`, null
when none exists. Its analysis
is `{id, lead_id, priority, lead_score, result, created_at}`. The typed
`GET /api/leads/{id}/intelligence` response retains `{id, company, email,
source, analysis}` with that same analysis shape. `PATCH /api/leads/{id}/lifecycle`
returns typed `LeadResponse`. `GET /api/leads/{id}/analyses?limit=50&offset=0`
returns `{items, total, limit, offset}`; limit is 1–100 and tenant ownership is
checked before querying. All customer reads require authentication and active
membership; cross-tenant Lead IDs return 404.

`POST /api/leads/{id}/process` is registered and returns typed
`{lead_id, processing_status, analysis, error}` on successful synchronous
completion. It requires session, authorized organization, and CSRF. Missing or
cross-tenant Lead is 404; an active attempt is 409. Provider configuration or
availability failure is 503, timeout 504, malformed output 502, and an
unexpected persistence failure 500. Failure never replaces prior intelligence.
List/search/follow-up pagination remains page based (1-based,
page size 1–100); history uses zero-based offset. Organization filtering occurs
before pagination.


## Contract principles

This document records routes registered by `backend/main.py` and the target security contract. **CURRENT:** `/api/auth` authenticates callers. Registered Lead, Import, Dashboard, Report, and Settings customer routes require a valid session and active Organization membership selected by `X-Organization-ID`; mutations and import preview require CSRF. Analytics queries apply that Organization predicate in SQL. The legacy file-path ingestion route is unregistered. A route marked IMPLEMENTED has code registered; it is not necessarily production safe or integration tested.

## Authentication (implemented; Lead tenant authorization active)

| Method and path | Contract |
| --- | --- |
| `POST /api/auth/login` | JSON `{email, password}`; on success returns `{user: {id, email, is_active}}`, sets an HttpOnly opaque session cookie and a browser-readable CSRF cookie. Raw tokens and password hashes are absent from JSON. Unknown email, wrong password, and inactive account share the same 401 response. Validations use 422; disallowed `Origin` uses 403; IP rate limiting uses 429. |
| `GET /api/auth/me` | Requires a non-expired, non-revoked session belonging to an active User. Returns `{id, email, is_active}`; missing or invalid session uses 401. It carries no organization claim. |
| `POST /api/auth/logout` | Requires a valid session and matching `X-CSRF-Token` header plus session-bound CSRF cookie. Returns `{success: true}`, revokes the server session, and clears both cookies. Missing or invalid session uses 401; bad CSRF uses 403. Repeated logout after revocation returns 401. |

The session cookie is Secure by default, HttpOnly, SameSite=Lax, and Path=/; the CSRF cookie shares Secure/SameSite/Path but is readable by browser JavaScript. Local HTTP development can explicitly set `SESSION_COOKIE_SECURE=false` only with `ENVIRONMENT=development` or `test`. Login checks a supplied `Origin` against explicit `CORS_ORIGINS`. Authentication requests and responses do not select an organization.

## Organization selector

`GET /api/organizations` requires a valid session and returns a bare JSON array of `{id, name, slug, role}` for active memberships joined to active organizations, ordered by name and ID. It returns `[]` when none are available and 401 without a session. It has `Cache-Control: no-store`; it does not grant authorization to use a selected ID.

Every registered Lead, Dashboard, and Report route requires `X-Organization-ID` as a positive decimal Organization ID. The header selects a workspace; the backend authorizes it through an active membership joined to an active Organization. Missing, malformed, duplicate, zero, or out-of-range selectors return 400 after authentication. Missing/invalid sessions return 401; non-membership, inactive membership, and inactive Organization return the same 403. A record ID outside the authorized tenant returns 404. Lead `POST` and `PATCH` require the session-bound `X-CSRF-Token` header and CSRF cookie; failed CSRF returns 403. Lead creation rejects client-supplied `organization_id` and other extra fields with 422. `/me` remains identity-only. There is no implicit `leadforge-dev` fallback.

Dashboard `/v2/overview` is a current Lead snapshot: each tenant Lead contributes at most one current linked analysis, selected by `created_at DESC, id DESC`. `pipeline.total_leads` counts Leads, `analyzed_leads` counts Leads with a linked current analysis, and `average_current_score` is null when none are analyzed. Its priority, lifecycle, and processing distributions count current Leads. Top opportunities rank current analyzed Leads once each. `recent_analysis_activity` is explicitly historical and may include repeat events for a Lead or unlinked legacy events (`lead_id: null`). The optional `priority` narrows only the top/current and recent/event lists, not snapshot metrics. The original `/overview` route is retained for existing callers and continues to count history rows. Reports remain historical analysis activity over their selected periods; their `total_leads` field still counts analysis rows. Every query is tenant scoped in SQL.

Historical `recent_analysis_activity.priority` retains known legacy values `High` and `Unknown` alongside canonical `Hot`/`Warm`/`Cold`. This compatibility applies only to the historical event field. Current Lead priority and top opportunities remain strictly canonical; legacy labels are not mapped or counted as current priority. This resolves response validation for existing unlinked history without rewriting it.

Report windows use stored naïve UTC: daily is `[00:00 UTC, next 00:00 UTC)`, weekly is the rolling seven days, and monthly is the rolling thirty days. The executive report summarizes the same monthly window. Empty tenants return zero metrics and empty lists. Invalid or reversed programmatic ranges raise `ValueError`; the current HTTP routes do not accept custom date boundaries.

`frontend/src/services/api.js` returns parsed JSON directly, never `{data: ...}`. It supports GET/POST/PUT/PATCH/DELETE and query parameters; all requests use `credentials: "include"`. Customer services request `X-Organization-ID` from the selected workspace, and writes read the browser-readable CSRF cookie for `X-CSRF-Token`. The selected ID is a UI preference, not authorization. A 401 clears frontend auth state; a customer-route 403 refreshes available workspaces and clears a selection that is no longer authorized. Errors expose `status`, `message`, and optional validation `details`.

All current lead routes use prefix `/api/leads`; trailing slashes below are significant to the registered route. Timestamps serialize as JSON date/time strings. No common success envelope exists for these business responses. FastAPI validation produces 422; custom error handlers may alter validation body shape. Lead routes remain PARTIAL because of other contract and transaction gaps, while their authenticated tenant authorization is implemented and tested.

| Status | Method and path | Current request and response | Current errors and tenant rule |
| --- | --- | --- | --- |
| PARTIAL | `POST /api/leads/` | JSON `company` (1–200), `email` (EmailStr), `source` (1–100). Returns `LeadResponse`: `id, company, email, source, industry?, lead_score?, priority?, ai_reason?, next_action?, status, notes?, last_contacted?, next_follow_up?, created_at`. | Active membership and CSRF required; ownership comes from context. Extra payload fields return 422; duplicate returns 409, including the verified tenant/email create race (Step 5J-L). |
| PARTIAL | `GET /api/leads/` | `page` default 1; `page_size` default 50, max 100. Optional `status`, `priority`, `processing_status`, `source` (case-insensitive substring), `analysis_state` (`analyzed`/`unanalyzed`). Returns `{items, page, page_size, total, pages}`; each item extends `LeadResponse` with `current_analysis: {id, lead_score, priority} | null` from the latest linked analysis. | Authenticated, membership-authorized tenant list; filters and count run in SQL before pagination; 422 invalid filters. |
| PARTIAL | `GET /api/leads/search` | Optional company and email substring predicates (combined with AND), the same filters, and pagination. Returns the same list shape. | Authenticated, membership-authorized tenant search; filters and count run in SQL before pagination. |
| PARTIAL | `GET /api/leads/follow-ups` | `days` default 7, 1–365, plus pagination. Returns the same list shape. | Authenticated, membership-authorized tenant follow-ups; 422 bad query. |
| IMPLEMENTED | `GET /api/leads/{lead_id}` | Integer path ID. Returns typed `LeadDetailResponse` with `current_analysis` null or the latest linked analysis. | 404 absent or cross-tenant lead within the selected authorized Organization; 422 invalid ID. |
| IMPLEMENTED | `PATCH /api/leads/{lead_id}/lifecycle` | JSON optional `status`, `notes`, `last_contacted`, `next_follow_up`; returns typed `LeadResponse`. | Active membership and CSRF required; 422 invalid status/body, 404 absent or cross-tenant lead. |
| IMPLEMENTED | `GET /api/leads/{lead_id}/intelligence` | Returns typed `{id, company, email, source, analysis}`; `analysis` is null or `{id, lead_id, priority, lead_score, result, created_at}`. | Active membership required; 404 absent or cross-tenant lead, 422 invalid ID. Current analysis orders by `created_at DESC, id DESC`. |
| IMPLEMENTED | `GET /api/leads/{lead_id}/analyses` | `limit` 1–100, `offset` >=0; returns `{items, total, limit, offset}` in current-first order. | Active membership required; 404 absent or cross-tenant lead. |
| IMPLEMENTED | `POST /api/leads/{lead_id}/process` | Synchronous process request; returns typed `LeadProcessingResponse` with newly persisted analysis. Reprocessing appends history. | Session, authorized organization, and CSRF required; 404 cross-tenant ID, 409 active attempt, controlled provider errors. |
| PARTIAL | `GET /api/dashboard/overview` | Existing typed history-row shape with `total_leads, hot_leads, warm_leads, cold_leads, average_lead_score, top_opportunities, recent_analyses`. | Retained for compatibility. `total_leads` counts analysis rows, despite its legacy name. Tenant scoped in SQL. |
| IMPLEMENTED | `GET /api/dashboard/v2/overview` | Optional `limit` 1–20 and `priority` `Hot/Warm/Cold`; returns typed `{pipeline: {total_leads, analyzed_leads, unanalyzed_leads, average_current_score: number|null}, priority_distribution: {Hot,Warm,Cold,Unanalyzed}, lifecycle_distribution, processing_distribution, top_opportunities, recent_analysis_activity}`. Current opportunities include `lead_id, company, status, processing_status, lead_score, priority`; activity events include `analysis_id, lead_id|null, company, lead_score, priority, created_at`. | Authenticated and tenant scoped in SQL. Current metrics and ranking select only each Lead's latest linked analysis by timestamp then ID; activity is historical. 422 for invalid filters. |
| PARTIAL | `GET /api/reports/daily`, `/weekly`, `/monthly` | Optional `limit` 1–20 and `priority` `Hot/Warm/Cold`; returns period bounds, counts, average score, and top analyses. | Authenticated and tenant-scoped in SQL; 422 for invalid filters. |
| PARTIAL | `GET /api/reports/executive` | Returns `{period, overview, top_leads, recommendations}` from the authorized tenant's monthly report. | Authenticated and tenant-scoped in SQL; recommendations follow existing score/priority thresholds. |
| IMPLEMENTED (Step 4D) | CSV Lead import | `POST /api/imports/leads/preview` and `/confirm` use authenticated membership, workspace selector, and CSRF. Both accept raw UTF-8 CSV (`Content-Type: text/csv`); confirm also requires `X-Import-Preview-Token`. | Preview never writes Leads. Confirm re-uploads the same bytes and revalidates before tenant-owned insertion. The old ingestion route remains unregistered. |

### Step 4D CSV import

The exact supported headers are `company,email,source`; all are required. Header names are trimmed and lowercased. Extra columns are ignored and reported in `ignored_headers`; duplicate normalized headers and missing required headers reject the file. Values are trimmed, then validated with `LeadCreate` (`company` 1–200 characters, valid email up to the model column's 200 characters, `source` 1–100 characters). There are no optional/defaulted CSV fields. In particular, `organization_id`, IDs, scores, priority, status, analysis and processing state cannot be supplied through CSV. The limit is 1 MiB and 1,000 nonblank data rows; preview returns the first 100 rows. UTF-8 BOM, quoted commas/newlines, and blank lines are supported. Empty/header-only and malformed files return 422; oversized files return 413; unsupported content type returns 415.

`POST /api/imports/leads/preview` returns `{token, summary: {total, ready, duplicates, invalid}, rows: [{row_number, company, email, source, status, errors}], preview_limit, ignored_headers}`. The token expires after 15 minutes and is signed with the current session's server-held CSRF digest. It binds the exact file digest, user, and authorized organization. No CSV bytes are retained server-side. The client re-uploads the file to `POST /api/imports/leads/confirm`, with the token in `X-Import-Preview-Token`; the server verifies it and revalidates against current tenant data. Confirmation returns `{total, imported, duplicates, invalid}`. A changed file, workspace, session, or expired token requires a fresh preview.

First valid occurrence of an email in the file is the candidate; later exact canonical email matches are duplicates. Existing email checks use only the selected organization. Invalid rows and duplicates are skipped, never overwritten. Confirm uses a single outer transaction and per-row savepoints; database uniqueness conflicts for an email that now exists in the same organization count as skipped duplicates. Other database errors roll back the whole batch. Repeating confirmation is safe and returns zero new imports once all candidates exist. Import creates Leads with canonical `New`/`pending` defaults and no analysis, score, priority, or AI call.

## Vocabulary and frontend gaps

- Backend and active LeadDetails lifecycle statuses: `New`, `Qualified`, `Contacted`, `Meeting`, `Won`, `Lost` (`LeadLifecycleUpdate` and `LeadLifecycleService`).
- Backend scoring priority uses `Hot`, `Warm`, `Cold`. The unregistered legacy AI prompt uses urgency terms `Low/Medium/High` and is not part of the canonical processing path.
- Backend lead list uses `items`, not a bare array. Its `current_analysis` summary is the current linked analysis; legacy Lead scalar score/priority fields remain for compatibility. Active LeadDetails fetches the typed detail response and displays only analysis score/priority when an analysis exists.
- API changes require coordinated schema, service, frontend, and isolated contract tests. Do not invent fields or present missing metrics as real data.

## Step 5K-L browser error behavior

The browser API client still returns parsed JSON directly (or an explicitly requested Blob), includes cookie credentials, supplies the selected membership context and preserves CSRF headers. It now bounds header/body receipt to 90 seconds without automatic mutation retry, retains a response request ID on ApiError, normalizes transport/server failure copy, and maps field-level validation while retaining specific safe domain messages. A timeout does not prove that a server-side mutation failed; check the saved result before retrying. This is a client behavior change, not a new server response envelope or API version.
