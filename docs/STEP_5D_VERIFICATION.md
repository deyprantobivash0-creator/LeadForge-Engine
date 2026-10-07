# Step 5D verification report — 2026-10-06

**Status: COMPLETE.** Logging, correlation, health and privacy gates passed.
LeadForge is still not production-ready. Stop after 5D. The canonical operator
reference is [OBSERVABILITY.md](OBSERVABILITY.md); 5C policy remains in
[CONFIGURATION.md](CONFIGURATION.md).

| Requested report item | Result |
| --- | --- |
| 1. Status | COMPLETE; all applicable gates verified; no later phase started. |
| 2. Before | Rich/plain application logs, unchecked incoming request IDs, BaseHTTP request middleware missing exception paths, Uvicorn access duplication, import-time startup notice, safe but quiet readiness, default query-bearing Nginx access/error detail. |
| 3. After | One stdlib JSON strategy; outer ASGI request correlation/completion, ContextVar, lifecycle and safe domain events, actionable readiness/migration categories, private Nginx hop logs. |
| 4. Library | Python stdlib logging/json/contextvars/time; no new dependency or external logging platform. Existing Rich dependency retained without unrelated dependency changes. |
| 5. Format | Single JSON object/event, explicit UTC timestamp, level/logger/event/message/environment/service; bounded additional fields. Migration has distinct service identity. |
| 6. Levels | Exact DEBUG, INFO, WARNING, ERROR, CRITICAL through 5C Settings. Healthy probes DEBUG; successes INFO; rejected requests/domain/readiness WARNING; server errors ERROR. |
| 7. Production default | INFO; production DEBUG remains rejected by the preserved configuration contract. |
| 8. Request-ID design | One outer ASGI boundary; request.state + ContextVar; reset after streaming/error; IDs included in request and exception events. |
| 9. Incoming policy | Exactly one 1–64-character ASCII token `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; invalid/duplicate/oversized values replaced with UUID4 hex. Diagnostic only; never authentication. |
| 10. Response header | One X-Request-ID, including generic backend errors; CORS exposes it for development cross-origin clients. |
| 11. Nginx behavior | Edge validates/preserves or generates its random ID, forwards it, hides upstream duplicate and returns authoritative header, including proxy errors. |
| 12. HTTP fields | request_id, method, route-template path, status_code, duration_ms, service/environment. Unmatched path becomes `<unmatched>`; no raw parameters/query/body/header. |
| 13. Duration | perf_counter monotonic milliseconds, measured through response streaming and exception completion; no percentile aggregation. |
| 14. Slow requests | SLOW_REQUEST_MS=2000 default, integer 1–600000; threshold emits additional correlated WARNING http.request.slow; focused timing test passed. |
| 15. Exceptions | ERROR http.exception, type and bounded basename/function/line stack locations; no exception text, absolute paths, SQL parameters, source or locals. Unknown component messages become safe Runtime diagnostic. |
| 16. Client errors | Existing generic 500/domain/validation response semantics preserved; failure/privacy tests pass. A stream failure after headers cannot rewrite the original status, but emits failure diagnostics. |
| 17. Startup | Lifespan app.starting/config.loaded/database.engine.ready/app.started with version, provider and dialect only; engine-ready is configuration, not connection readiness. |
| 18. Shutdown | app.stopping/app.stopped, engine disposal; Docker graceful restart verified. Forced kill cannot log graceful shutdown. |
| 19. Auth | Safe login started/completed/failed, session failed and logout/revocation operation events; successful user ID/durations/types, no email/password/token. |
| 20. Tenancy | tenant.access.denied uses authenticated user ID and selector ID; workspace selection remains client state and every operation still authorizes membership. |
| 21. Imports | Preview/confirm started/completed/failed with counts/duration/tenant/user IDs; existing non-mutating preview and transactional uniqueness semantics preserved. |
| 22. AI | Analysis started/completed/failed/conflict, tenant/Lead/Analysis IDs, provider/state/category/duration. No prompt, output or lead contents. All global/integration execution remains mock. |
| 23. DB failures | readiness.failed distinguishes database_unavailable and schema_not_ready using safe driver categories; SQL echo=false, engine logger WARNING. No URL or driver message. |
| 24. Migrations | started/completed/failed JSON, dynamic shipped target revision, safe category/type; fixed nonzero RuntimeError on failure, no chained driver values. Alembic no longer disables existing application loggers. Historical migrations unchanged. |
| 25. Uvicorn | Image --no-access-log; middleware owns the single backend completion event. Runtime logs use canonical JSON, raw third-party text suppressed. |
| 26. Nginx | Query-free JSON access log to stdout, coarse path classes/upstream status/native timing; static/probe noise reduced. Critical native errors to stderr; lower request-detail errors intentionally suppressed because they can echo queries. |
| 27. Redaction | Explicit allowlist + body/header exclusion; 5C configured-secret/encoded-password/credential-URL redaction before JSON encoding; arbitrary third-party text/exception messages dropped. Not a universal PII detector. |
| 28. Sentinel | Random externally injected DB/API-key/integration sentinels absent from production lifecycle logs, image/filesystem/metadata/public assets/docs/normal responses; network disabled for dry run. Generated sentinel file removed after verification. |
| 29. DB URL | 5C malformed-URL/error tests and safe encoded synthetic migration failure passed; raw credential-bearing URL/password absent from app/migration diagnostics. |
| 30. Tokens/cookies | Emitted-log audit used actual synthetic login session/CSRF values and Cookie/Authorization headers, verified absence from backend/frontend/migration logs, then logged out. |
| 31. AI key | Externally injected synthetic GEMINI_API_KEY with mock selected; production lifespan startup/shutdown JSON contained no key. Unit formatter redaction also passed; no provider requests. |
| 32. Customer privacy | Synthetic email/password and non-mutating CSV preview payload absent from emitted logs. Prompt/model-output logging never introduced. Preview still returns scoped customer content per existing API contract. |
| 33. Liveness | GET /health: 200 success:true/status:healthy, DB-independent and cheap; stable response retained. |
| 34. Readiness | GET /ready: 200 success:true/status:ready/database:ok only for reachable DB and exact Alembic heads; otherwise 503, existing payload contract retained. |
| 35. Failure categories | Responses retain unavailable/schema_outdated; logs distinguish database_unavailable/schema_not_ready. Invalid configuration refuses app import rather than exposing a live endpoint. |
| 36. DB outage | Controlled PostgreSQL stop: liveness200/readiness503, matching request ID and database_unavailable event; no credentials. |
| 37. Recovery | PostgreSQL start restores readiness200 without manual state repair; volume/data preserved. |
| 38. Migration failure | Temporary wrong synthetic DB credentials cause migrate exit nonzero, backend/frontend unstarted; JSON failure category and fixed error, sentinel absent. Standard stack restored without volume deletion. |
| 39. Health privacy | Runtime audit and tests: no credentials, stack, config values, topology or customer data; version stays in startup logs to preserve response contract. |
| 40. Streams | Backend/Uvicorn/Alembic JSON stdout; Nginx JSON stdout/critical stderr; Docker raw logs parsed successfully. PostgreSQL native diagnostics are a separate component. |
| 41. Read-only | Logging works with existing read-only root filesystems/tmpfs; no primary log files created; non-root backend/migrate10001:10001 and frontend101:101 preserved. |
| 42. Docker commands | backend/frontend/migrate log streams inspected; Compose service is `migrate`, not `migration`; exact commands below. |
| 43. Event catalog | Implemented lifecycle/HTTP/auth/tenant/import/AI/report/readiness/migration/proxy/runtime events documented in OBSERVABILITY.md. No fictional event names. |
| 44. Documentation | Created OBSERVABILITY.md and this 66-item report; linked README, updated CONFIGURATION.md and CONTAINERS.md; example includes only safe threshold/defaults. |
| 45. SQLite | Final full suite **179 passed in 68.56s**, original169 +10 focused observability cases; no prior regression. Final logging/config/readiness focused suite **57 passed**. |
| 46. PostgreSQL | **5 passed**, 0 failures/skips/errors, 4.87s; disposable actual PostgreSQL16.15. |
| 47. Configuration | All 45 dedicated DB/production configuration cases included; strict environment/production/provider/cookie/origin/secret rules intact. Network-disabled production lifespan and final image sentinel audit passed. |
| 48. pip | Project venv pip check passed; clean image pip check: no broken requirements. |
| 49. Lint | Clean Linux frontend npm run lint: 8 existing warnings, 0 errors. |
| 50. Build | Clean Linux npm run build passed, Vite 508ms; no frontend source/dependency changes for 5D. |
| 51. No-cache build | Both changed images rebuilt --no-cache from stopped state; final backend logging corrections rebuilt afterward. No development bind mounts. |
| 52. Runtime start | Standard local stack healthy; one-shot migration exit0; no restart loops; PostgreSQL16.15 unchanged. |
| 53. Compose ps | Backend/frontend/PostgreSQL healthy, migrate Exited(0); final restart counts0. Only runtime127.0.0.1:8080 published; separate5A DB binding127.0.0.1:55432 preserved. |
| 54. Browser | Disposable browser passed login/workspace, Dashboard/Leads/Imports/Intelligence list+detail/Reports/Settings, reloads/logout; zero JS errors; browser container removed. |
| 55. End-to-end ID | Valid synthetic ID returned once and found in proxy/backend events; malformed/oversized IDs replaced; exactly one backend completion event; probes intentionally DEBUG. |
| 56. Original DB | SHA256 before/after `217E5D8A5128936BE5FB5FEE8FE1F54036F9106E318514DA5E6E98D485221A4A`; unchanged. |
| 57. Diff | git diff --check passed; status/stat reviewed; existing dirty work preserved; no reset/restore/clean/commit/push. |
| 58. Created files | Exact inventory below. |
| 59. Modified files | Exact inventory below; no historical migration, database or frontend source/dependency edits. |
| 60. Warnings | Existing 8 frontend lint warnings, Python/Starlette/dependency deprecations, image size and build pip root notice/Git line-ending notices; not expanded into unrelated fixes. |
| 61. npm advisory | Existing one high advisory remains explicitly queued for5E; no blind audit fix, no security clearance claimed. |
| 62. External telemetry | Prometheus/Grafana/ELK/OTel collector/Sentry/APM, log retention/central storage/alerting/metrics/tracing deferred; none installed. |
| 63. Log commands | Exact safe Compose commands below; external local password required, explicit empty env file, no interpolated config dump. |
| 64. Health commands | curl.exe -i /health and /ready through127.0.0.1:8080, plus synthetic-ID API request; exact commands below. |
| 65. Troubleshooting | Correlate returned ID, safe reason/category, dependency/container/lifecycle state. Docker explicit kill suppresses restart; process-level SIGTERM verified auto restart. Migration gate failure must be fixed, never bypassed. See OBSERVABILITY.md. |
| 66. Recommendation | Accept5D operational visibility, preserve local mock runtime and stop. Still not production-ready;5E+ untouched. No paid/real provider calls, real credentials or customer data. |

## Exact file inventory

Created:

- backend logging tests: tests/test_observability.py
- local emitted-log/privacy audit: scripts/observability_smoke.py
- guarded reversible failure exercise: scripts/observability_faults.py
- docs/OBSERVABILITY.md
- docs/STEP_5D_VERIFICATION.md

Modified:

- .env.example
- README.md
- Dockerfile
- alembic/env.py
- backend/main.py
- backend/core/config.py
- backend/core/logger.py
- backend/core/error_handlers.py
- backend/core/request_id.py
- backend/core/request_logging.py
- backend/services/authentication_service.py
- backend/services/organization_authorization_service.py
- backend/services/lead_import_service.py
- backend/services/lead_processing_service.py
- backend/services/report_v2_service.py
- backend/services/runtime_readiness_service.py
- backend/api/routes/report_routes.py
- deploy/nginx.conf
- tests/api/test_runtime_readiness.py
- docs/CONFIGURATION.md
- docs/CONTAINERS.md

The 5C redaction utility is reused, not replaced. Existing service transactions,
provider validation, tenant scopes and response models are retained.

## Exact verification/operator commands

From repository root. The local password below is the documented development-only
placeholder, not a production credential. Always pass the empty tracked Compose env
file to avoid loading private `.env`; never print interpolated Compose secrets.

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
.\venv\Scripts\python.exe -m pytest tests/test_observability.py tests/test_production_configuration.py tests/test_database_config.py tests/api/test_runtime_readiness.py -q
.\venv\Scripts\python.exe -m pip check
$env:LEADFORGE_POSTGRES_ADMIN_URL = 'postgresql+psycopg://leadforge_dev:leadforge_dev_only@127.0.0.1:55432/leadforge_dev'
.\venv\Scripts\python.exe -m pytest tests_postgres -q
$env:LEADFORGE_RUNTIME_DB_PASSWORD = 'leadforge_dev_only'
docker compose --env-file deploy/compose.env -f compose.runtime.yml config --quiet
docker compose --env-file deploy/compose.env -f compose.runtime.yml down
docker compose --env-file deploy/compose.env -f compose.runtime.yml build --no-cache
docker compose --env-file deploy/compose.env -f compose.runtime.yml up -d --wait
docker compose --env-file deploy/compose.env -f compose.runtime.yml ps -a
docker compose --env-file deploy/compose.env -f compose.runtime.yml logs --tail 100 backend
docker compose --env-file deploy/compose.env -f compose.runtime.yml logs --tail 100 frontend
docker compose --env-file deploy/compose.env -f compose.runtime.yml logs --tail 100 migrate
curl.exe -i http://127.0.0.1:8080/health
curl.exe -i http://127.0.0.1:8080/ready
curl.exe -i -H 'X-Request-ID: synthetic-operator-5d' http://127.0.0.1:8080/api/auth/me
Get-Content scripts/container_smoke.py -Raw | docker exec -i leadforge-runtime-local-backend-1 python -
.\venv\Scripts\python.exe scripts/observability_smoke.py
.\venv\Scripts\python.exe -u scripts/observability_faults.py
Get-Content scripts/container_smoke.py -Raw | docker exec -i leadforge-runtime-local-backend-1 python - --check-persistence
Get-FileHash -Algorithm SHA256 leadforge.db
git diff --check
git status --short
git diff --stat
```

Git executable on this host:
`C:\Users\USER\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe`.
Fault script temporarily disrupts only guarded local synthetic runtime and restores
it; it never deletes volumes. It should not be run against shared/customer systems.
Normal shutdown is the above `down` command, with no `-v`.

Build output: host TEMP leadforge-5d-build.log; final backend build:
leadforge-5d-final-build.log. SQLite/PostgreSQL/focused evidence captured to
leadforge-5d-tests.log, leadforge-5d-postgres.log, leadforge-5d-final-focused.log.
These are generated verification artifacts, not primary runtime log files.
Clean frontend Dockerfile executes npm ci, npm run lint, npm run build; Nginx runtime
has no Node/Vite dev server. Backend remains one Uvicorn worker/no reload.

Production lifecycle/sentinel dry run uses externally injected synthetic DB URL,
GEMINI_API_KEY and inactive integration token, ENVIRONMENT=production, AI_PROVIDER=mock,
explicit HTTPS origin, image --network none/read-only/tmpfs. It enters/exits the existing
lifespan only, without connecting to DB/provider. Output JSON was parsed and audited.
The reused 5C configuration_audit.py inspects image filesystem/history/config, public
assets, repository/docs, normal app/migration/frontend streams and health. Its focused
credential-pattern scan is not a universal credential/security audit. No values printed.

Operational caveats: unknown third-party log text is suppressed; Nginx lower error
levels are suppressed to prevent raw query leaks; no external aggregation/retention
or alerting. Docker explicit kill is a manual stop, while process exit triggers restart
policy. Forced kills require Docker event/exit metadata; they cannot run Python shutdown
handlers. Exact guarantees and event catalog are in OBSERVABILITY.md.

Final sentinel audit: 325 repository files at scan time, 431 historical tracked blobs,
zero known credential-pattern findings; backend15147/frontend1021 image files checked.
This is a focused 5C regression audit, not a universal secret/security clearance.
