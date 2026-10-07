# Step 5E verification — security hardening

Verified 2026-10-06 against the existing dirty working tree. Scope: registered application routes, mock AI, isolated synthetic databases, and the local container runtime. This is not a production-release certification. Private `.env` files were not read or modified. No customer data, paid AI, historical migration rewrite, reset/restore/clean, commit, push, or Step 5F work was performed.

The numbered table supplies all 84 requested report items. Detailed policy and threat boundaries are in [SECURITY.md](SECURITY.md); every remaining image package/CVE record and the original high/critical disposition ledger are in [STEP_5E_IMAGE_FINDINGS.md](STEP_5E_IMAGE_FINDINGS.md). Residual applicability is an inference from source, configuration and exercised paths; severity labels are retained.

| # | Requested item | Result / evidence |
| --- | --- | --- |
| 1 | Status | **COMPLETE** for Step 5E within the defined local/mock boundary. All applicable verification gates passed; no applicable exploitable HIGH/CRITICAL was identified in that boundary. |
| 2 | Architecture | Membership-scoped repositories, cookie sessions, CSRF dependency, bounded transport, same-origin Nginx, isolated internal PostgreSQL; no duplicate business/auth/config framework. |
| 3 | Threat model | Anonymous login abuse; authenticated tenant IDOR/overposting; hostile CSV/JSON; browser script/session theft; spoofed forwarding/Host; secret/log leaks; dependency/container compromise. |
| 4 | Priorities | Preserve tenant and CSRF boundaries; bound parsing/login state; reject unexpected writes; prevent exported formulas; patch applicable dependencies; assess residual image exposure individually. |
| 5 | Authentication | Existing membership/session model preserved. Generic bad-credential response; inactive users rejected; password verification precedes session creation. |
| 6 | Hashing | Argon2id, time cost 3, memory 65536 KiB, parallelism 4, salt 16 bytes, hash 32 bytes. Successful login rehashes stale configuration in the session operation transaction. |
| 7 | Password policy | Login password 1–1024 characters, email at most 254; extra fields rejected. Existing valid passwords remain supported; no new reset/registration workflow. |
| 8 | Enumeration | Wrong password and unknown account use the same public failure. This does not claim perfect timing indistinguishability; no account-existence API added. |
| 9 | Abuse design | 10 attempts per 60 seconds, socket-peer identity, 1024 fixed hash buckets, lock and monotonic clock. Collisions conservatively share budget; no unbounded key store. Production cannot disable it. |
| 10 | Sessions | Independent random 256-bit session/CSRF values; only SHA-256 digests persisted; constant-time CSRF comparison; malformed token rejected before query. |
| 11 | Fixation | Fresh token on each successful login; attacker supplied cookie is not adopted. Automated test passed. |
| 12 | Revocation | Logout revokes current session and clears cookie. Other independent sessions retain their own lifetimes; tested. |
| 13 | Expiration | Absolute seven-day TTL preserved; expired/revoked sessions rejected. No sliding renewal or scheduled cleanup introduced. |
| 14 | Cookies | Session HttpOnly; CSRF browser-readable; both SameSite=Lax, host-only, path=/; production Secure enforced. Local HTTP fixture deliberately non-Secure, browser verified. |
| 15 | CSRF | All six registered mutation families require authenticated session-bound CSRF; cross-session tokens rejected 403. Existing missing/invalid/valid cases remain passing. |
| 16 | Tenant isolation | Organization comes from authenticated membership. All registered customer paths audited; no default organization bypass introduced. |
| 17 | Attack matrix | Two-way tenants: 12 customer read paths including reports/settings/monthly/CSV; five foreign-record operations return 404; foreign workspace selection returns 403; cross-session writes return 403. |
| 18 | IDOR | Detail, intelligence, analyses, processing and lifecycle foreign IDs denied; signed bigint-positive IDs validated. |
| 19 | Mass assignment | Auth/lifecycle/create schemas forbid extras. Lifecycle injection of ownership/scoring/system fields rejects 422; no persistence. |
| 20 | Validation | Email/company/source/note/search/page/ID bounds; NUL rejection; validation error contexts removed for safe JSON serialization; password input not echoed. |
| 21 | Body limits | Backend counts streamed bytes and validates Content-Length; 2 MiB maximum including chunked requests. Nginx ingress limit preserved; 413 verified. |
| 22 | CSV import | Existing 1 MiB /1000-row /100-preview limits and confirmation binding preserved. Invalid UTF-8/NUL/header/quote/limit inputs tested. Header indexes computed once to keep wide-row parsing linear. |
| 23 | Formula export | Formula prefixes after Unicode whitespace/control characters escaped with apostrophe; tab/CR/LF leading strings escaped; numeric values unchanged. Eleven cases tested. |
| 24 | SQL injection | ORM bound parameters and membership predicates retained; hostile SQL strings treated literally; wildcard search still restricted to own tenant. No string-built customer SQL. |
| 25 | Code execution | No customer-driven shell/eval/exec path found in registered operations. Build-only tooling uses fixed targets/artifacts; no new application execution feature. |
| 26 | Traversal | Import uses bytes, not customer filesystem paths; static serving fixed-root. No new customer file-write/upload-directory path. |
| 27 | Redirects | No customer-supplied server redirect target found; frontend route navigation remains local. |
| 28 | XSS | React escaping retained; malicious script CSV value rendered as text and never executed in Chromium. No customer HTML rendering introduced. |
| 29 | CSP | default/script/font/connect self; styles self plus unsafe-inline for existing React styles; images self/data; object none; base/form self; frame ancestors none. No script unsafe-inline/eval. |
| 30 | Headers | nosniff, DENY, strict-origin-when-cross-origin, camera/microphone/geolocation disabled; Nginx consistent includes and backend outer ASGI coverage even errors. No HSTS on local HTTP. |
| 31 | Cache | API successes/errors no-store; SPA no-cache; content-hashed assets immutable. No authenticated Nginx proxy cache. |
| 32 | CORS | Explicit configured origins and credentials; GET/POST/PATCH methods; no wildcard credential origin. Browser no blocking CORS errors. |
| 33 | Proxy | Backend does not trust forwarded client identities. Nginx overwrites forwarding fields and strips Forwarded/forwarded Host. Limiter intentionally sees shared proxy peer. |
| 34 | Host | Exactly one valid authority required; hostnames derived from configured origins plus loopback. Malformed/foreign Host returns 400; spoofed forwarding cannot bypass it. |
| 35 | Methods | Nginx allows GET/HEAD/POST/PATCH/OPTIONS; unsupported method returns 405. Existing route contracts preserved. |
| 36 | Docs | Production disables OpenAPI, Swagger and ReDoc; development remains usable. Isolated production import test passed. |
| 37 | Disclosure | Generic public failures, request correlation, no SQL/DSN/traceback/password in public error bodies; server identification disabled at backend. |
| 38 | Database | Internal-only PostgreSQL; application membership scoping remains essential. Local fixture role is superuser with create-role/create-db/replication privileges: unsuitable for production. Separate migration owner and runtime least-privilege grants documented, not claimed provisioned. |
| 39 | DB failures | Controlled outage gave liveness 200/readiness 503 with generic correlated response, then recovery 200. Migration credential failure exited nonzero without secret disclosure. |
| 40 | Python audit | Initial host 92 packages: four advisories in two packages. Post-remediation host zero known advisories; final Linux image audit also zero (81 audited packages). |
| 41 | Python fixes | langgraph-sdk 0.4.2 → 0.4.4 (GHSA-fvww-7h3r-vfhp); urllib3 2.7.0 → 2.8.0 (GHSA-vxq7-64xx-v4gw, GHSA-gh4c-6fx4-qh6g, GHSA-8988-9cw3-xx77). Removed unused SlowAPI. |
| 42 | npm audit | Initial one HIGH; final project audit zero info/low/moderate/high/critical. |
| 43 | Exact npm HIGH | source-map-js GHSA-68fv-2mgg-jv7q / CVE-2026-93749: indexed source-map CPU exhaustion, Vite/PostCSS build path; compatible fixed 1.2.2 applied. Build-only exposure still remediated. |
| 44 | npm changes | Lockfile source-map-js 1.2.1 → 1.2.2. Container Node 22.22.2, integrity-checked npm 12.2.0; compatible bundled brace-expansion 5.0.12 and undici 6.28.1 patches. No project dependency major upgrade or audit force. |
| 45 | Image findings | Final inventory: backend 69, frontend 2, PostgreSQL 105, Node build tools 7 =183 package/CVE records; includes residual HIGH and two CRITICAL. Full inventory linked above. |
| 46 | Remediation | OS upgrades; updated Node patch; removed unused Yarn/Corepack and Nginx modules; Nginx same-upstream security package revision r7; checksum verified compatible npm bundle patches. Residual findings individually assessed, not suppressed or downgraded. |
| 47 | Pins | Python, Node, Nginx and PostgreSQL base images pinned by digest; npm/download patches pinned by version and SHA-512. Exact values in Dockerfiles and patch helper. |
| 48 | Privileges | Backend/migrate UID10001, frontend UID101, read-only root, all caps dropped/no-new-privileges. PostgreSQL root entrypoint has only setup caps, then server UID999/CapEff0; read-only root with data volume and bounded tmpfs. No socket/bind/privileged mount. |
| 49 | Secrets | No private .env contents read; repository/docs/assets/image history/config/logs checked with external synthetic sentinel. Runtime environment inspection by authorized Docker admin inherently exposes injected secrets; no claim otherwise. |
| 50 | Scan | Gitleaks 8.30.1: 340 staged nonprivate source files, local redacted working tree and all seven reachable commits. One working-tree false positive: tests/test_auth_migration.py AUTH Alembic revision constant; no historical findings. Supplemental scan: 340 repository files /444 historical blobs, zero credential-pattern findings. |
| 51 | Browser storage | No session/CSRF/password/provider key in local/session storage. Existing workspace preference only; cookies carry opaque session. |
| 52 | Frontend dependencies | Project audit clean; build tools absent from final Nginx artifact. Remaining npm CLI cache advisory is build-only and classified separately. |
| 53 | Abuse exercise | Actual proxy bad logins with varying spoofed X-Forwarded-For/Forwarded reach 429, bounded Retry-After, then 401 after window expiry; privacy passed. Unit saturation/recovery cases passed. |
| 54 | CSV matrix | Seven malformed/oversized import cases, 11 export formula cases, inert HTML and wide ignored headers tested; preview remains nonmutating, confirmation bound to user/org/session/file. |
| 55 | Logs | Synthetic password/email/CSV/session/CSRF/cookie/query/authorization values absent; one structured completion/request correlation preserved. Final production sentinel startup/shutdown and invalid-config logs redacted; 15004 backend and 625 frontend files plus metadata/history/assets checked. |
| 56 | Header tests | API success/rejection/errors no-store and safety headers; Host/method/body checks; no local HSTS; production docs disabled. Passed. |
| 57 | Browser | Chromium seven product routes, login/workspace/reload/logout, escaped malicious CSV preview, CSV download; no page errors or blocking CSP/CORS/cookie/CSRF failures. Official pinned Playwright image, synthetic fixtures. |
| 58 | Config regression | 45 database/production configuration tests passed; valid production network-none dry-run and invalid CORS rejection verified. |
| 59 | Observability | Ten isolated observability tests passed plus runtime privacy and controlled outage/restart/process termination/migration failure recovery. |
| 60 | SQLite | 216 passed, 2099 warnings, 78.12 seconds; 179 baseline plus 37 new security cases. No failures/errors/skips. |
| 61 | PostgreSQL | Five passed, 82 warnings, 3.59 seconds; real separate test databases, no skips. No customer/original DB touched. |
| 62 | pip check | Host and final Linux image passed: no broken requirements. |
| 63 | Install | Clean npm ci passed. |
| 64 | Lint | Passed, zero errors; eight existing warnings retained. |
| 65 | Build | Vite production build passed, including case-sensitive imports in Linux image. |
| 66 | No-cache | Final backend, frontend and PostgreSQL no-cache builds passed. Backend final build includes the CSV index optimization. |
| 67 | Startup | Final images deployed successfully; local runtime healthy after controlled failure restoration. |
| 68 | Compose ps | Final snapshot: backend/frontend/PostgreSQL healthy; migrate exited 0. |
| 69 | Ports | Only runtime 127.0.0.1:8080 published; backend and runtime PG internal. Existing separate 5A fixture PG at loopback 55432 retained. |
| 70 | Non-root | Running backend/frontend/PG identities 10001/101/999; PostgreSQL effective capabilities zero. Verified by runtime inspection. |
| 71 | Original DB | Immutable read-only PRAGMA integrity_check returned ok; verified unchanged SHA-256 217E5D8A5128936BE5FB5FEE8FE1F54036F9106E318514DA5E6E98D485221A4A. |
| 72 | Diff check | git diff --check passed; only existing line-ending conversion warnings. Unrelated dirty-tree work preserved. |
| 73 | Created files | Fourteen files listed below. |
| 74 | Modified files | Twenty-two existing files listed below; other existing dirty files belong to prior work and remain preserved. |
| 75 | New tests | Four security test modules, 37 cases, plus guarded runtime and browser smoke scripts. |
| 76 | Fixed advisories | Four Python advisories, project source-map-js HIGH, Node/base and Nginx/OS security updates, bundled npm brace-expansion/undici advisories. See image before/final ledger for exact package CVEs. |
| 77 | Unresolved | All 183 image records retained in inventory. HIGH/CRITICAL current-path nonapplicability includes privileged utilities, unused native/DTLS/POD/XML paths, Gosu startup-only Go features, and anonymous npm build cache. This is not a vulnerability-free claim. |
| 78 | Limits | Shared proxy-peer limiter can throttle unrelated users; process-local budget resets on restart; no distributed limiter, perfect timing equalization or account lockout; local DB superuser; no production HTTPS/grants proof. Future features invalidate affected-path assumptions. |
| 79 | Deferred | CI enforcement, backup/restore, staging/TLS deployment, real-provider security/load testing, distributed abuse controls, secret rotation infrastructure and release operations remain later phases; no 5F implementation started. |
| 80 | Audit commands | Exact command forms and artifacts below. |
| 81 | Start | Synthetic local password environment plus docker compose --env-file deploy/compose.env -f compose.runtime.yml up -d --wait. |
| 82 | Stop | docker compose --env-file deploy/compose.env -f compose.runtime.yml down; never add -v for preserved fixture data. |
| 83 | Troubleshooting | Wait Retry-After for shared login budget; validate canonical Host/origin and CSRF cookie pairing; inspect correlated sanitized logs and migration exit; do not disable production checks, expose DB, paste secrets or remove volumes. See SECURITY.md. |
| 84 | Recommendation | Accept Step 5E within the mock/local boundary. Preserve residual advisory monitoring and finish later deployment gates before production release. |

## Files created

`docs/SECURITY.md`, `docs/STEP_5E_VERIFICATION.md`, `docs/STEP_5E_IMAGE_FINDINGS.md`; `backend/core/request_security.py`, `backend/core/csv_security.py`; `deploy/postgres.Dockerfile`, `deploy/security-headers.conf`, `deploy/patch-npm.mjs`; `tests/security/test_http_security.py`, `tests/security/test_session_security.py`, `tests/security/test_tenant_attack_matrix.py`, `tests/security/test_csv_security.py`; `scripts/security_smoke.py`, `scripts/security_browser_smoke.mjs`.

## Files modified

`README.md`, `docs/API_CONTRACTS.md`, `requirements.txt`, `Dockerfile`, `compose.runtime.yml`, `frontend/Dockerfile`, `frontend/package-lock.json`, `backend/main.py`; `backend/core/passwords.py`, `backend/core/rate_limit.py`, `backend/core/session_tokens.py`, `backend/core/security_headers.py`, `backend/core/error_handlers.py`; `backend/schemas/auth_schema.py`, `backend/schemas/lead_schema.py`, `backend/schemas/lead_lifecycle_schema.py`; `backend/services/authentication_service.py`, `backend/services/lead_import_service.py`; `backend/api/routes/auth_routes.py`, `backend/api/routes/lead_routes.py`, `backend/api/routes/report_routes.py`; `scripts/container_smoke.py`.

## Reproducible command forms

Run from repository root in PowerShell. Audit executables and redacted output paths are temporary, outside the repository. No private dotenv file is required. The password below is the known synthetic local fixture identity, not a production credential.

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
$env:LEADFORGE_POSTGRES_ADMIN_URL='postgresql+psycopg://leadforge_dev:leadforge_dev_only@127.0.0.1:55432/leadforge_dev'
.\venv\Scripts\python.exe -m pytest tests_postgres -q
.\venv\Scripts\python.exe -m pip check
& "$env:TEMP\leadforge-5e-audit-venv\Scripts\python.exe" -m pip_audit --path venv/Lib/site-packages --format json --output "$env:TEMP\leadforge-5e-pip-after.json"
# Final Linux freeze captured as UTF-8 via Python subprocess, then:
& "$env:TEMP\leadforge-5e-audit-venv\Scripts\python.exe" -m pip_audit -r "$env:TEMP\leadforge-5e-image-freeze.txt" --no-deps --disable-pip --format json --output "$env:TEMP\leadforge-5e-image-python-audit.json"
Set-Location frontend
npm ci
npm audit --json
npm run lint
npm run build
Set-Location ..
$env:LEADFORGE_RUNTIME_DB_PASSWORD='leadforge_dev_only'
docker compose --env-file deploy/compose.env -f compose.runtime.yml config --quiet
docker compose --env-file deploy/compose.env -f compose.runtime.yml build --no-cache backend frontend postgres
docker compose --env-file deploy/compose.env -f compose.runtime.yml up -d --wait
docker compose --env-file deploy/compose.env -f compose.runtime.yml ps -a
docker exec leadforge-runtime-local-backend-1 python -m pip check
Get-Content scripts/container_smoke.py -Raw | docker exec -i leadforge-runtime-local-backend-1 python -
.\venv\Scripts\python.exe scripts/security_smoke.py
.\venv\Scripts\python.exe scripts/observability_smoke.py
.\venv\Scripts\python.exe scripts/observability_faults.py
# Browser script piped to Node in the pinned Playwright smoke container.
# Docker Scout SARIF scans were local only, for each built image:
docker scout cves --format sarif local://leadforge-backend:5b-local
docker scout cves --format sarif local://leadforge-frontend:5b-local
docker scout cves --format sarif local://leadforge-postgres:16.15-local
docker scout cves --format sarif local://leadforge-node-build:5e
# Gitleaks ran on a staged nonprivate source + copied Git history in its tool container:
docker exec leadforge-5e-gitleaks gitleaks dir /audit --redact=100 --report-format json --report-path /tmp/working.json --exit-code 1
docker exec leadforge-5e-gitleaks gitleaks git /audit --log-opts=--all --redact=100 --report-format json --report-path /tmp/history.json --exit-code 1
Get-FileHash -Algorithm SHA256 -LiteralPath leadforge.db
& 'C:\Users\USER\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' diff --check
docker compose --env-file deploy/compose.env -f compose.runtime.yml down
```

Checks were executed in separate batches as code changed, not as one shell chain. Initial test parameter IDs exceeded the Windows environment limit; explicit short IDs corrected that test harness issue and the full suite was rerun. npm self-upgrade and a whole-root npm reinstall were rejected by actual module/registry failures; the final integrity-checked compatible bootstrap/bundle patch approach passed clean install/lint/build. Internal smoke transport needed the canonical public Host after intentional Host enforcement. These corrected attempts are not hidden successes. Warnings from the existing dependency/test stack and eight existing frontend lint warnings remain; no required failing check is accepted.

## Verified final artifacts

| Artifact | Local image ID |
| --- | --- |
| `leadforge-backend:5b-local` | `sha256:1f84ef498d0bba32ec6d6964b0fa172e96bd8b0c226be3a2362acbd9f66ac5d5` |
| `leadforge-frontend:5b-local` | `sha256:3016e09aad35883bc84c7b7aae4e4471b9a90e37967a9cc19429e814ac00ed1a` |
| `leadforge-postgres:16.15-local` | `sha256:df0f42fa31d4cc6ec4d8379f961514301f1159394fcbdb0f8ad442bc5fc5699d` |
| `leadforge-node-build:5e` | `sha256:e79fbd5610523b27b6eb42f91d58fec8c22d10aae57069932ace9ea1da46d269` |

The final backend was deployed and rescanned after the CSV header-index change. Actual functional, observability privacy, Chromium and rate-limit recovery checks were rerun against it. Final Linux pip audit: 81 audited packages, zero known advisories; pip check passed. The externally injected sentinel was removed after the audit. Disposable scan/browser/build-tool containers are removed; the healthy application runtime and both existing synthetic database volumes are preserved.
