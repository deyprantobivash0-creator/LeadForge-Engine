# Step 5H-B host/port source hotfix

October 9, 2026 (Asia/Dhaka). Source hotfix and local verification only; Step 5H
remote acceptance remains incomplete. No Render operation, commit or push authorized
by this task. Starting main SHA: `79f36db0e6f2fdde5a06bc6b04c5810a542dcf2e`.

## Root-cause evidence recorded before source changes

The supplied incident reports port 8000 discovery/network restart and repeated HTTP
400 probes until timeout. A production-configured isolated TestClient reproduction
with mock AI, a synthetic PostgreSQL URL, frontend-only CORS and
`RENDER_EXTERNAL_HOSTNAME=backend-fixture.onrender.com` returned
`400 {"detail":"Invalid host."}` for originless `/ready`; a stubbed readiness service
was called zero times. `RequestSecurityMiddleware.__call__` rejects Host before route
handling because canonical Settings ignores the platform hostname on direct Uvicorn
startup. This proves the source failure path, not the actual remote environment.

The existing Render adapter already consumes PORT (validated 1024–65535, fallback
8000), binds 0.0.0.0, and merges an exact validated onrender hostname before importing
Settings. render.yaml explicitly selects that adapter. Dockerfile's default CMD
instead launches Uvicorn directly with --port 8000 and bypasses hostname adaptation.
The reported symptoms are consistent with that default/overridden launch path;
the actual remote command, environment and response body were not provided or
independently inspected. Do not claim its precise remote configuration is proven.

Port 8000 was reachable, so it was not itself the HTTP 400 blocker. Render detected
the alternate listener and reconfigured networking as reported. Its default PORT is
10000; HTTP probes use the onrender hostname when no verified custom domain exists.
Sources: [port contract](https://render.com/docs/web-services),
[probe Host](https://render.com/docs/health-checks),
[Docker CMD/override](https://render.com/docs/docker).

Startup migration claims also need qualification: neither backend lifespan nor the
Render start operation runs Alembic upgrade. Alembic revision imports during readiness
can emit migration logger diagnostics. Explicit migrate is a separate external
verified-TLS operator operation. Actual remote migration commands are unverified.

## Verification

| Gate | Result / evidence |
| --- | --- |
| Backend | PASS: 308 passed, zero skips; 2172 existing deprecation warnings. `.staging-artifacts/host-port-backend.log`. Focused Render tests: 42 passed. |
| PostgreSQL | PASS: PostgreSQL 16.15, six passed, zero skips, strict no-skips plugin. `.staging-artifacts/host-port-postgres-container.log`. |
| Fresh Alembic | PASS: base -> stored required head `e5d4c3b2a1f0`, revision imports and single head verified. |
| Render local simulation | PASS: `.staging-artifacts/host-port-render-20261009-retry/verification.json`; default Docker CMD, PORT=10000, synthetic exact hostname, PID 1 --host 0.0.0.0 --port 10000, originless `/ready` 200, unrelated and sibling Host 400 even with valid X-Forwarded-Host. |
| Render security/data | PASS: separated non-superuser roles, internal required TLS, app DML without schema CREATE/Alembic UPDATE, PostgreSQL/schema readiness, mock AI, auth/tenant/CSRF/cookies/CSV, TLS-negative, proxy correlation and log privacy. |
| Compose | PASS: uniquely named disposable production-image Compose project; backend fallback 8000, frontend 8080, migration prerequisite, mock provider, readiness and restart recovery. Existing runtime project untouched. `.staging-artifacts/host-port-e2e/verification.json`. |
| Kubernetes | PASS: focused read-only `python -m scripts.kubernetes_smoke_local`; four retained workloads Ready, jobs succeeded, mock config, schema/readiness/frontend/SPA smoke. Retained PVC UID `dca3b5f4-1683-4a24-ab01-b41029afd222` unchanged. This checks the existing deployment; it does not claim rebuilt hotfix images were rolled out there. |
| Playwright | PASS: nine existing browser journeys + two auth/recovery journeys after restart. Compose report status PASS with privacy/correlation and preserved hashes. |
| Frontend | PASS: Node 22.22.2, npm ci, lint and production build; case-sensitive Linux Docker frontend build/browser runtime also passed. |
| Dependencies | PASS: pip check; pip-audit no known vulnerabilities; npm audit zero vulnerabilities. `.staging-artifacts/host-port-security.log`. |
| Gitleaks | PASS: 8.30.1 source scan and negative control. `.staging-artifacts/host-port-gitleaks.log`. |
| actionlint | PASS: native installed verifier, no diagnostics. |
| Diff/source hygiene | PASS: git diff --check and scripts/ci.py hygiene. |

Initial verification issues were corrected without weakening gates: the Docker
engine was stopped and was started locally; Kubernetes smoke needed module invocation;
the original rehearsal binding assertion searched a diagnostic intentionally redacted
by logging, so it now inspects `/proc/1/cmdline` plus successful HTTP traffic. The first
local Render attempt passed DB/Host checks but failed that assertion; its FAIL artifact
is retained, and the complete retry is PASS. The sandbox denied audit registry sockets;
an authorized network-enabled audit then passed. No automatic approval rejection occurred.

Windows excluded TCP ranges cover 55432, preventing the host-published PostgreSQL
gate. The retry uses an owned ephemeral PostgreSQL container listening on 55432 with
no host publication and a disposable test runner sharing its network namespace.
The unchanged gate still targets 127.0.0.1:55432, leadforge_dev, required PostgreSQL
16.15, fresh random databases and strict zero-skips. Only scripts/tests_postgres/pytest.ini
were mounted read-only into the runner; no private dotenv/DB/credential files were
mounted. Test-only pytest was installed in its ephemeral /tmp. Owned containers were
removed; no host networking, development database or retained PVC was altered.

PowerShell records native stderr (pip notices and container progress) as
NativeCommandError even for successful inner checks. The gate summaries and machine
reports above are the evidence of success; the PowerShell wrapper's exit status alone
is not presented as proof. No outstanding application/test failure remains.

## Final requested report

| # | Requested field | Result |
| --- | --- | --- |
| 1 | Starting SHA | `79f36db0e6f2fdde5a06bc6b04c5810a542dcf2e`, main. |
| 2 | Root cause | Proven local source path: direct Uvicorn ignores platform hostname, causing Invalid host before readiness; actual remote command/env unverified. |
| 3 | 400 producer | `RequestSecurityMiddleware.__call__`, Host membership rejection. |
| 4 | Port 8000 blocker | No: HTTP 400 proves reachable HTTP, not failed port binding. |
| 5 | Port discovery restart | Default Docker CMD forced 8000, consistent with reported alternate-port discovery/network reconfiguration. Explicit Blueprint adapter already consumed PORT. |
| 6 | Port fix | Default CMD runs runtime.py container; validated PORT wins, absent fallback 8000, bind 0.0.0.0, same security Uvicorn flags. EXPOSE documents 8000 and 10000. |
| 7 | Host fix | Canonical Settings merges exact validated platform hostname with explicit TRUSTED_HOSTS, covering direct Uvicorn too. Adapter no longer mutates TRUSTED_HOSTS separately. |
| 8 | Platform hostname | Optional infrastructure field; strict exact lowercase single-label onrender.com hostname; malformed values fail closed, no echoed input. |
| 9 | Wildcards | Rejected in both host configuration inputs; random onrender sibling 400. |
| 10 | CORS | Exact frontend origins preserved, no wildcard, no coupling to backend hostname. |
| 11 | /ready | Unchanged dependency/schema readiness and safe generic payloads; originless valid Host reaches it. /health remains liveness. Render healthCheckPath remains /ready. |
| 12 | Unknown host | 400; X-Forwarded-Host cannot authorize it. |
| 13 | Local PORT=10000 | PASS, default image command plus actual process arguments and HTTP/PG readiness. |
| 14 | Startup migration | Source does not migrate during startup. Revision imports during readiness can produce Alembic events. Explicit upgrade head reruns at current head are no-ops; no migration redesign. Actual remote wrapper remains unverified. |
| 15 | Backend count | 308 passed, zero skips. |
| 16 | PostgreSQL | Six passed, zero skips. |
| 17 | Alembic | Fresh base -> e5d4c3b2a1f0 PASS. |
| 18 | Compose | PASS, isolated rebuild/runtime/restart with unchanged local URLs. |
| 19 | Kubernetes | Existing retained deployment read-only smoke PASS; hotfix image rollout not performed. |
| 20 | Playwright | Nine + two passed. |
| 21 | Security/dependencies | PASS, auth/tenant/CSRF/cookies/Host/privacy/TLS and Python/npm audits. |
| 22 | Gitleaks | PASS including negative control. |
| 23 | actionlint | PASS. |
| 24 | leadforge.db | Byte-identical SHA256 `217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a`. |
| 25 | Preexisting work | All five original dirty/untracked files byte-identical; historical reports untouched; index empty. |
| 26 | Changed files | Dockerfile; backend/core/config.py; deploy/render/runtime.py; scripts/verify_render_local.py; tests/test_render_deployment.py; docs/RENDER_STAGING.md; this new report. |
| 27 | Proposed commit | `fix(deploy): align Render host and port handling`. No staging, commit or push performed. |
| 28 | Redeploy recommendation | Recommend after approved commit/push and exact-SHA CI, with remote start-command/env drift review. Do not redeploy this dirty source. Remote Step 5H remains incomplete. |

## Preservation inventory

The initial dirty worktree consisted of modified docs/STEP_5F_VERIFICATION.md plus
untracked docs/STEP_5H_B_REMOTE_VERIFICATION.md, docs/STEP_5H_B_VERIFICATION.md,
package.json and package-lock.json. All hashes match the starting values:

| File | SHA256 |
| --- | --- |
| docs/STEP_5F_VERIFICATION.md | `07d87a793b4132c486cc289d4b60b0a203c977c7427220015ad48571ea22eff8` |
| docs/STEP_5H_B_REMOTE_VERIFICATION.md | `51cef4769a3e289c9c4b5aaac445e9675dcd772db73f79176db5b95c32745222` |
| docs/STEP_5H_B_VERIFICATION.md | `0744bb262ef48004a088c06afcfc999097446f2a4c95bd55d92715d343a947c2` |
| package.json | `1edb3fbc0f4f707b44b640e840974965ef2fd09fc7da772edc2d9d79dfe950b4` |
| package-lock.json | `3afa53c6825e891263a738bace87a439d681247b8c2392314f47f7acc5e82561` |

No private .env contents read, no secrets committed, no schema changes, no SQLite
deployment substitution, no tenant/business logic changes, no real AI, no remote
Render operation or billing change. Database URL normalization/TLS remains
postgresql+psycopg and LEADFORGE_RENDER_DB_TLS=internal as designed.
