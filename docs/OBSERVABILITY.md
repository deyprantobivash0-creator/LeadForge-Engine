# Observability — Step 5D

LeadForge uses stdlib logging with one JSON formatter for application, Uvicorn and
Alembic runtime events. Logs go to stdout; Nginx access logs go to stdout and its
critical startup/error stream goes to stderr. PostgreSQL retains its own native logs.
No external APM, metrics collector, analytics service or new logging dependency was added.

## Backend format and privacy

Every canonical event is a single valid JSON object with UTC `timestamp` (Z), `level`,
`logger`, stable `event`, `message`, `environment`, and `service`. Services are
`leadforge-backend`, `leadforge-migration`, and the separate `leadforge-nginx` proxy.
Request context adds `request_id`. HTTP completion includes method, route-template
path, status_code and duration_ms. Unmatched paths become `<unmatched>`; no raw path
parameters or query values are recorded. No request/response body or headers are logged.

Event fields are explicitly allowlisted: IDs, counts, provider name, fixed failure
category, status, duration, version/dialect/revision, and safe exception locations.
Do not pass customer strings to an allowed metadata field. Configured secrets and
credential URLs use the 5C redaction utility; recursive string redaction happens
before JSON serialization so replacements cannot break JSON. Unknown third-party
messages are replaced with `Runtime diagnostic`, retaining level/logger and safe
exception type/location. No SQL parameters, exception messages, source lines or
frame locals are serialized. SQLAlchemy engine logging remains WARNING/echo=false.
This intentionally sacrifices third-party message detail to protect privacy.

Unexpected failures emit ERROR `http.exception` with exception type and up to 20
basename/function/line stack locations. No absolute paths or source/locals. Clients
retain generic 500 responses, without server traces. If a stream fails after headers
were sent, its HTTP status cannot be rewritten; a failed completion/export event
still diagnoses the failure. Existing validation/domain responses remain unchanged.

5C SecretStr, configuration validation, source isolation and secret injection remain
unchanged. Bootstrapping configuration failure happens before logging is initialized;
its fixed key/category-only import error may be plain stderr. Alembic failure also
ends with a fixed RuntimeError traceback after its JSON failure event. PostgreSQL and
Nginx critical diagnostics are separate native component streams. Legacy unregistered
manual scripts with print statements were not expanded or run as application entrypoints.
No universal PII detector is claimed; future fields/handlers must obey this contract.

## Correlation and timing

`X-Request-ID` accepts exactly one ASCII token matching
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`. Empty, duplicate, malformed or oversized IDs are
replaced by UUID4 hex. This is diagnostic context, never authentication or authorization.
Never put a secret in this header. Nginx is authoritative at the public edge: it preserves
a safe incoming ID or uses its built-in random request ID, forwards it to FastAPI, hides
the duplicate upstream header, and returns one authoritative response header, including
proxy errors. Direct backend requests use the same bounded policy. CORS exposes that
response header for the optional development cross-origin client.

An outer ASGI boundary surrounds the framework's error handlers. The ID is stored on
request.state and in a ContextVar, propagated into normal service/threadpool work, and
reset after response streaming/error handling. This ensures error responses have IDs.
One backend completion event is emitted after streaming finishes, even on exceptions.
Uvicorn access logging is disabled in the image; its runtime logger uses the same JSON
formatter. Proxy and backend completion events are distinct hop timings, not duplicate
backend access events. Request timing uses perf_counter, not wall time.

`SLOW_REQUEST_MS` defaults to 2000, integer 1–600000, through canonical Settings.
At/above it an additional WARNING `http.request.slow` records the same bounded metadata.
Successful health/readiness request completions are DEBUG; other success INFO, rejected
HTTP responses WARNING, server errors ERROR. Readiness failures always produce WARNING
with a fixed reason; no external aggregation or percentile calculation is implemented.
LOG_LEVEL retains exact DEBUG/INFO/WARNING/ERROR/CRITICAL. Default INFO; production
DEBUG remains prohibited. One JSON format is used in every environment, no format knob.

## Event catalog (implemented)

| Events | Meaning / safe context |
| --- | --- |
| app.starting, config.loaded, database.engine.ready, app.started | Lifespan startup, version, provider name, dialect. Engine-ready means configured, not a live connection; readiness proves DB/schema. |
| app.stopping, app.stopped | Graceful lifespan shutdown and engine disposal. A forced kill cannot run shutdown handlers. |
| http.request.completed, http.request.failed, http.request.slow | One request completion/failure, optional threshold warning; route template, status, timing, ID. |
| http.exception | Unexpected error type and safe stack locations, correlated request. |
| http.domain.rejected, http.validation.rejected | Fixed domain error code/status or validation status; no submitted values. |
| auth.login.started, auth.login.completed, auth.login.failed | Login operation; successful user ID, duration, failure type; no email/password/token. |
| auth.session.failed | Missing/invalid/expired/revoked session category; no raw session ID. Successful per-request resolutions are quiet. |
| auth.logout.started, auth.logout.completed, auth.logout.failed | Existing server revocation operation, duration/failure category; no token. |
| tenant.access.denied | Authenticated user ID and denied selector ID; no customer names. Workspace selection remains client state, authorized again per request. |
| import.preview.started, import.preview.completed, import.preview.failed | Non-mutating preview duration and total/ready/duplicate/invalid counts. |
| import.confirm.started, import.confirm.completed, import.confirm.failed | Transactional confirmation, imported/duplicate/invalid counts; no CSV rows or preview/session key. |
| ai.analysis.started, ai.analysis.completed, ai.analysis.failed, ai.analysis.conflict | Existing claim/completion/failure boundaries, tenant/Lead/Analysis IDs, fixed provider/category/state, monotonic duration; no prompts/responses/lead contents. |
| report.generate.started, report.generate.completed, report.generate.failed | Reports v2 overview service boundary, tenant ID and duration/failure type. |
| report.export.started, report.export.completed, report.export.failed | Existing CSV stream, tenant ID, row count and duration/failure type. |
| readiness.failed | database_unavailable or schema_not_ready, exception type where useful; no driver text or topology. |
| migration.started, migration.completed, migration.failed | One-shot migration target revision, fixed category/type; nonzero failures preserve startup gating. |
| runtime.log | Safe third-party runtime diagnostic category, source logger, level, optional safe exception locations. |
| proxy.request.completed | Nginx hop completion status, request ID, coarse path class, duration_seconds, upstream_status. |

## Health contracts

- `GET /health`: 200 `{"success":true,"status":"healthy"}`; process alive; cheap and DB-independent.
- `GET /ready`: 200 `{"success":true,"status":"ready","database":"ok"}` only with reachable DB and exact shipped Alembic heads.
- Unready: 503 `{"success":false,"status":"not_ready","database":"unavailable"}` for query failures, or database=`schema_outdated` for a head mismatch.
- Logs distinguish missing schema from connectivity using driver error codes, without changing the established response contract.
- Configuration is validated before app import; there is no live endpoint for invalid configuration.
- `GET /frontend-health`: static Nginx liveness, not backend readiness.

Liveness200/readiness503 is intentional during DB failure; restore the dependency,
then readiness recovers without manual state repair. No provider call, customer query,
Git metadata, credential, topology, or filesystem path is exposed by these responses.
Existing version is recorded in startup logs; health bodies retain their stable contract.
Readiness does not prove future real AI provider connectivity or any later production gate.

## Nginx responsibility and tradeoffs

JSON access logs use coarse `/api`, `/health`, `/ready`, `/assets`, `<spa>` path classes;
no query/body/header, customer path values or remote IP. Static assets and frontend-health
have access logging disabled. Timestamp carries an explicit UTC offset in the current
UTC image; Nginx uses native request_time seconds (wall-clock hop timing), backend uses
monotonic milliseconds. Upstream status and final status identify controlled 502/504s.
Nginx open-source error logs have no configurable field sanitizer and can echo a raw
request/query. Therefore request-detail error diagnostics are suppressed with critical
threshold; operational access events remain the source for proxy failure status/timing.
Critical startup/fatal Nginx messages retain stderr. Do not enable lower error thresholds
without re-evaluating privacy. This loses detailed upstream error text by design.

## Operator commands and troubleshooting

From repository root; inject the documented development-only local password externally.
Never print interpolated Compose configuration or inspect arbitrary environment values.

```powershell
$env:LEADFORGE_RUNTIME_DB_PASSWORD = 'leadforge_dev_only'
docker compose --env-file deploy/compose.env -f compose.runtime.yml config --quiet
docker compose --env-file deploy/compose.env -f compose.runtime.yml ps -a
docker compose --env-file deploy/compose.env -f compose.runtime.yml logs --tail 100 backend
docker compose --env-file deploy/compose.env -f compose.runtime.yml logs --tail 100 frontend
docker compose --env-file deploy/compose.env -f compose.runtime.yml logs --tail 100 migrate
curl.exe -i http://127.0.0.1:8080/health
curl.exe -i http://127.0.0.1:8080/ready
curl.exe -i -H 'X-Request-ID: synthetic-operator-5d' http://127.0.0.1:8080/api/auth/me
.\venv\Scripts\python.exe scripts/observability_smoke.py
```

Use the returned ID to match backend/proxy events. Compose prefixes service/container
names, so its console output wraps the JSON; raw `docker logs CONTAINER` retains bare JSON.
Liveness200/readiness503: inspect readiness.failed reason, PostgreSQL health and migrate
exit status. Missing schema/head mismatch: verify the one-shot migration succeeded on the
same configuration, never modify version tables manually. Migration failure: inspect
migration.failed and its fixed DB/schema category; backend/frontend should remain gated.
502: correlate Nginx upstream_status with backend state/lifecycle/readiness, not client
body or query. Login401: auth.login.failed and error category; do not log credentials.
CSRF403/session401: domain/session category; verify cookies/HTTPS and the established
CSRF flow. Import failure: operation ID/context, counts and fixed failure type; preserve
file contents outside logs. AI failure: tenant/Lead IDs and provider/state/category,
never prompt or model response.

Graceful Docker restart logs stopping/stopped/started. Process-level SIGTERM exit was
verified to trigger unless-stopped automatic restart and readiness recovery. An explicit
Docker kill is a manual control-plane stop on this runtime and suppresses auto-restart;
its exit137/not-OOM metadata plus proxy502 diagnose it, and `docker start` restores it.
Forced SIGKILL cannot produce graceful shutdown logs. Container events/exit state are
necessary for termination causes outside Python, not an application failure message.
Healthy runtime has zero restart loops; final ordinary recreation resets test counts.

Fault exercise (disrupts only the explicitly guarded disposable local runtime; preserves
volume and restores stack; do not run against a shared/customer deployment):

```powershell
.\venv\Scripts\python.exe -u scripts/observability_faults.py
```

It stops/starts local PostgreSQL, restarts/signals the backend, then tests invalid
synthetic migration credentials with a temporary override and normal down/up. No volume
reset or historical migration edit. Read-only filesystems remain compatible: logs are
streams, and Nginx temporary paths remain tmpfs. No runtime log files are created.

## Scope and remaining work

Verified configuration/privacy/health/logging is not production release readiness.
No external telemetry ingestion, long-term storage, retention/rotation policy,
alerting, centralized metrics, tracing, SLO aggregation, security audit or load test was
added. Prometheus/Grafana/OpenTelemetry/ELK/Sentry and similar integrations are deferred.
Existing npm high advisory remains assigned to 5E. Backups, CI, staging, real providers,
load/E2E and release audits remain later phases. Stop after 5D; no commit/push.
