# Step 5J-L verification and pre-commit report

Verified 2026-10-08. **STEP 5J-L — COMPLETE.** No commit or push performed.

| # | Check | Evidence/result |
| --- | --- | --- |
| 1 | Source HEAD | `7026210bcd7d32e2b400edc18a879e4e31ccd2ca`, main; unchanged, no commit/push yet. |
| 2 | Runtime tested | Two fresh production-built Nginx/FastAPI/PostgreSQL 16.15 Compose projects; private test network, canonical http://127.0.0.1:8080. Existing runtime retained. |
| 3 | Tool/browser | Playwright 1.58.2; Chromium 145.0.7632.6; pinned official browser image. |
| 4 | Browser count | 5 unique tests; 4 primary + 2 recovery executions per rehearsal; 12 passed across two complete rehearsals, 0 failed, no retries. |
| 5 | Login | Valid and invalid sign-in pass; generic invalid-credential message; authentic Argon2id retained. |
| 6 | Session | Navigation/reload, logout, revoked-cookie replay and protected-route rejection pass. Real server expiry: validation changes from 200 to 401. |
| 7 | Workspace | Explicit selection, Alpha/Beta switching, retained selected context and invalid organization rejection pass. |
| 8 | Dashboard | Current snapshot counts one analyzed Lead despite two seeded historical events; no double counting; renders without unexpected errors. |
| 9 | Leads | Rows, responsive details, lifecycle update, priority and current intelligence pass. |
| 10 | Intelligence | Real mock processing request, observed busy indicator, persistence/score/priority/current analysis pass. Later injected provider failure preserves prior analysis and Lead score/priority; recovery browser renders it. |
| 11 | CSV | Select/preview/confirm/result, nonmutating preview, duplicate/invalid skips, empty input and no automatic AI pass; API boundary tiers below. |
| 12 | Reports | Two seeded historical events versus one unique analyzed Lead; Today UTC selection and real CSV download pass. Concurrent summaries deterministic. |
| 13 | Settings | Read-only overview renders; provider mock; no credential/configuration inputs or fake integration controls. |
| 14 | Direct routing | All seven routes /, /leads, /imports, /ai, /ai/:id, /reports, /settings pass through production Nginx. |
| 15 | Browser errors | Zero unexpected console/page errors or failed requests in passing runs. Known 401/403/404/422 responses classified by path and status; navigation cancellations excluded. |
| 16 | CSP/CORS | Zero detected CSP/CORS violations; same-origin browser traffic; security headers retained. |
| 17 | Accessibility | Labeled inputs, named buttons, navigation landmark, keyboard Tab and dialog Escape pass. No full accessibility/contrast certification. |
| 18 | Responsive | 1440x900 desktop, 768x1024 tablet and 390x844 mobile: Lead search/details and closing remain usable. |
| 19 | Measured APIs | Health, readiness, Lead list/detail, Dashboard v2, Reports v2 Today, intelligence and session; 30 measured requests each after warmup, 0 failures. |
| 20 | p50 | Exact endpoint results in latency table below, in milliseconds. |
| 21 | p95 | Exact endpoint results in latency table below; local evidence, not an SLA. |
| 22 | p99 | Interpolated small-sample estimates in latency table below; limited tail confidence. |
| 23 | Concurrency | 1, 5, 10, 25, 50 concurrent authenticated requests; one synthetic session shared via separate worker clients; not 50 independent login users. |
| 24 | Concurrency errors | 0/900 unexpected read failures per rehearsal, 0% error rate; no tenant sentinel leakage; deterministic Dashboard/Reports. |
| 25 | Duplicate race | 10 direct HTTP creates: exactly 1 success + 9 HTTP 409, 0 HTTP 500. Deterministic PG regression observes SQLSTATE 23505 and uq_leads_organization_email, confirms session recovery, preserves unrelated 23502 errors. |
| 26 | CSV tiers | 10/100/500/1000 rows all preview/confirm/import correctly and repeat as duplicates; durations below. Empty/NUL/malformed/1001 rows return 422; >1 MiB returns 413. |
| 27 | Query review | 20/100-row pages both use 2 SQL queries; Dashboard 5, Reports 4. Primary slowest query 4.94 ms on 1613 Leads; no N+1 growth or proven missing-index defect. No query/index changes. |
| 28 | Database pool | Primary: 2 idle connections before, 5 after load, 1 after recovery (+ one active inspection connection). No idle-in-transaction, bounded <=16 total; no pool exhaustion/leak observed. |
| 29 | DB outage | Under light authenticated traffic, readiness 503, liveness 200, generic customer 500 without secret/connection details; database restart restores readiness and traffic. |
| 30 | Backend restart | Primary light probe: 24 HTTP 200 and 6 transient unavailable responses; recovered. Single-instance zero downtime is not claimed. |
| 31 | Frontend restart | Primary light probe: 29 HTTP 200 and 1 transient unavailable response; recovered. Browser auth and retained-intelligence recovery tests pass. |
| 32 | Request IDs | Selected browser e2e-browser-* and performance e2e-* IDs correlate in logs; successful responses preserve supplied IDs. Passwords and synthetic payload excluded from logs. |
| 33 | Auth/security negatives | Unauthenticated 401, invalid organization 403, cross-tenant Lead 404, bad CSRF 403, revoked/expired session 401; no-store/nosniff/CSP verified. Existing shared login budget emits 429 + Retry-After. |
| 34 | XSS | Harmless script-like CSV company text renders literally; window.__xss remains undefined; no script execution. |
| 35 | Pagination/large lists | 1613 Alpha Leads; API pages capped at 100 and disjoint. UI search/filter/newest-first behavior verified; no arbitrary sort claimed. Large-offset/substrings remain future scaling considerations. |
| 36 | Classification | GREEN: sequential read endpoints and correctness. ACCEPTABLE: concurrency-50 queuing, authentic password work and bounded batch imports. No remaining measured defect classified NEEDS OPTIMIZATION; no cloud production SLA/readiness claim. |
| 37 | Defect discovered | Direct-create advisory precheck raced; initial 10-request run produced 1 success, 7 duplicates and 2 generic HTTP 500s despite unique rows remaining intact. |
| 38 | Fixes | Narrow direct-create IntegrityError classification after rollback: exact PG SQLSTATE/constraint, exact SQLite uniqueness. Unrelated integrity failures still raised. Two SQLite and one PG regressions added; no schema/auth/AI changes. Generator TLS setup/cpu attribution and test timing corrected. |
| 39 | Compose regression | Two isolated full rehearsals pass; existing containers healthy. Existing CI clean/no-cache image build, Compose HTTP and log-privacy gate also passes; own volumes removed. |
| 40 | Kubernetes regression | Docker Desktop safety, four Ready workloads, completed jobs, exact schema head, frontend SPA/health, backend readiness, mock configuration and retained Bound PVC pass. Patched backend image leadforge-backend:5j-l-local; no cloud operations. |
| 41 | Backend | 266 passed, 0 skipped; existing deprecation warnings retained. |
| 42 | PostgreSQL | 6 passed, 0 skipped, PostgreSQL 16.15 (baseline five plus deterministic direct-create regression). |
| 43 | Alembic | Single intended head e5d4c3b2a1f0; fresh disposable PostgreSQL base -> head passes; no migration changes. |
| 44 | Frontend | npm ci, lint and production build pass; 8 unchanged accepted warnings, no new errors. Final Docker build also lints/builds the final test sources. |
| 45 | Gitleaks | Current source scan and injected negative control pass; redacted scanner; no private artifacts included. |
| 46 | Actionlint | quality.yml passes with existing optional shellcheck/pyflakes tool integrations disabled; workflow unchanged. |
| 47 | Dependency/security | pip check passes; pip-audit no known findings; npm audit 0 vulnerabilities. Existing runtime OS/image finding ledger is not erased or re-certified by dependency audits. |
| 48 | SQLite integrity | leadforge.db SHA256 217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a before/after; untouched. |
| 49 | Docs | E2E_TESTING.md, PERFORMANCE_LOCAL.md and this STEP_5J_L_VERIFICATION.md. |
| 50 | Artifacts excluded | Ignored local JSON/logs/traces/screenshots/archives; generated frontend reports excluded from Git and Docker context. No browser binaries, secrets, dotenv, DBs, dumps, keys or dependency directories in proposed scope. |
| 51 | Exact changed files | 23-file proposed scope listed below. Preexisting STEP_5F modification, STEP_5H_B report and root manifests excluded and hash-preserved. |
| 52 | Proposed scope | Local browser/performance/resilience tooling and documentation, artifact exclusions, pinned frontend test dependency, narrowly proven create-race fix and regressions. No CI deployment/cloud changes. |
| 53 | Commit message | `test: add browser E2E and local performance validation` |
| 54 | Step 5J-L | STEP 5J-L — COMPLETE (local engineering validation; approval pending for publication). |
| 55 | Step 5H | STEP 5H — DEFERRED. REAL REMOTE STAGING NOT YET EXECUTED. |
| 56 | Step 5I | STEP 5I — BLOCKED BY REMOTE STEP 5H. |
| 57 | Next recommendation | Approve the reviewed 5J-L commit/push and verify its exact-SHA remote quality gate; next engineering milestone is authorized real remote Step 5H staging, before Step 5I. |

## Local latency (primary complete rehearsal)

All values are milliseconds; 30 requests per row, zero failures.

| Endpoint | p50 | p95 | p99 |
| --- | ---: | ---: | ---: |
| health | 1.68 | 1.93 | 2.09 |
| readiness | 2.58 | 2.85 | 3.0 |
| leads | 7.22 | 8.71 | 9.09 |
| detail | 6.21 | 6.46 | 6.99 |
| dashboard | 9.2 | 9.86 | 10.07 |
| reports | 8.11 | 10.24 | 11.03 |
| intelligence | 5.78 | 6.52 | 7.38 |
| session | 3.4 | 3.6 | 3.83 |

| Auth operation | Count | p50 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: |
| login | 5 | 79.64 | 83.46 | 83.56 |
| logout | 4 | 8.5 | 9.12 | 9.21 |

## Bounded concurrency

900 reads per complete rehearsal, zero failures.

| Concurrency | Endpoint | Count | p50 | p95 | p99 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | leads | 50 | 7.33 | 8.51 | 8.65 |
| 1 | dashboard | 50 | 9.38 | 13.04 | 15.48 |
| 1 | reports | 50 | 8.19 | 10.68 | 12.74 |
| 5 | leads | 50 | 38.62 | 48.46 | 52.03 |
| 5 | dashboard | 50 | 57.85 | 64.36 | 72.12 |
| 5 | reports | 50 | 46.08 | 53.57 | 54.81 |
| 10 | leads | 50 | 78.76 | 163.77 | 168.12 |
| 10 | dashboard | 50 | 107.15 | 122.15 | 133.15 |
| 10 | reports | 50 | 91.99 | 108.73 | 110.86 |
| 25 | leads | 50 | 185.17 | 254.45 | 265.34 |
| 25 | dashboard | 50 | 276.71 | 344.91 | 378.8 |
| 25 | reports | 50 | 264.16 | 422.65 | 444.95 |
| 50 | leads | 100 | 374.72 | 502.9 | 657.27 |
| 50 | dashboard | 100 | 501.2 | 608.38 | 824.29 |
| 50 | reports | 100 | 471.42 | 643.25 | 705.7 |

## Imports and mock analysis

| CSV rows | Preview ms | Confirm ms | Imported | Repeat duplicates |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 7.19 | 20.01 | 10 | 10 |
| 100 | 13.69 | 109.61 | 100 | 100 |
| 500 | 46.77 | 510.95 | 500 | 500 |
| 1000 | 85.51 | 1029.39 | 1000 | 1000 |

**MOCK PROVIDER ONLY:** request including persistence 26.46 ms; subsequent persisted read 8.05 ms; total observed 34.50 ms. Commit-only timing is not instrumented.

With 1613 Leads, list/Dashboard/Reports p95 were 19.5/20.88/8.59 ms (30 requests each, zero failures).

## Reproduction, resource evidence and limitations

Both complete projects `leadforge-e2e-30b778400388` and `leadforge-e2e-35be8c6d2860` passed browser/performance/fault/privacy/cleanup checks. Durations 300.41/295.62 seconds include deliberate shared-login-budget waits. Repeat concurrency-50 p95 (Leads/Dashboard/Reports): 486.52/632.83/662.85 ms; zero failures. Separate reports are retained rather than pooled or selecting the fastest run.

Primary resource samples: five samples, maximum combined service+driver CPU 140.74% (about 1.41 cores on 16 logical CPUs); backend sample maximum 107.47%. Sampled memory remained bounded (backend about 108 MiB; PG about 74 MiB; driver about 24 MiB of its 256 MiB cap). Samples are sparse and are not peak-memory guarantees. Host AMD Ryzen 7 5700X, about 16 GiB RAM; Docker 29.8.2, 16 CPUs, 8288563200 bytes RAM. No paid provider calls.

A supplemental attempt was interrupted when Docker Desktop was no longer running. The engine was started without reset; only that generated test project was removed, preserved services recovered, and the clean repeat passed. Earlier failing development attempts (test selector/timing, generator attribution and the actual create race) are not counted as passing evidence.

Query review: page query count stays 2 at 20 and 100 rows; Dashboard 5, Reports 4. Tenant/current-analysis predicates and existing unique/composite indexes remain intact. Offset cost, substring indexing, aggregate ranking, synchronous single-worker execution, row/savepoint imports and shared process-local login limiting remain future scaling limitations. No speculative optimization, migration or security-gate change. Chromium only; basic accessibility/responsive smoke is not device or accessibility certification.

Kubernetes PVC UID `dca3b5f4-1683-4a24-ab01-b41029afd222` remains unchanged and Bound. Required migration Jobs remain completed and schema gate reads e5d4c3b2a1f0. The retained local backend now uses the patched 5j-l image; no remote staging deployment was executed.

Evidence is local under `.staging-artifacts/5j-l/` and its `repeat/` directory. See [E2E runbook](E2E_TESTING.md) and [performance methodology](PERFORMANCE_LOCAL.md). Existing mandatory quality jobs and aggregate gate remain unchanged. Recommend local-first E2E now, optional CI stabilization later before making browser execution mandatory.

## Exact proposed commit scope

- `.dockerignore`
- `.gitignore`
- `backend/services/lead_service.py`
- `deploy/e2e.Dockerfile`
- `docs/E2E_TESTING.md`
- `docs/PERFORMANCE_LOCAL.md`
- `docs/STEP_5J_L_VERIFICATION.md`
- `frontend/e2e/auth.spec.js`
- `frontend/e2e/fixtures/data.js`
- `frontend/e2e/helpers/auth.js`
- `frontend/e2e/helpers/test.js`
- `frontend/e2e/import.spec.js`
- `frontend/e2e/product.spec.js`
- `frontend/e2e/recovery.spec.js`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/playwright.config.js`
- `scripts/e2e_fixture.py`
- `scripts/kubernetes_smoke_local.py`
- `scripts/local_performance.py`
- `scripts/verify_e2e_local.py`
- `tests/test_lead_create_conflicts.py`
- `tests_postgres/test_postgres_baseline.py`

Preexisting untracked files retained: `docs/STEP_5H_B_VERIFICATION.md`, root `package.json`, root `package-lock.json`. Existing `docs/STEP_5F_VERIFICATION.md` modification remains untouched. Index is empty; no staging, commit, amend or push performed.

STEP 5J-L — COMPLETE

STEP 5H — DEFERRED
REAL REMOTE STAGING NOT YET EXECUTED

STEP 5I — BLOCKED BY REMOTE STEP 5H

No production-readiness claim.
