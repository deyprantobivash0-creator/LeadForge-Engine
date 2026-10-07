# Step 5F verification report

Verified October 7, 2026. **5F locally COMPLETE, remote CI execution pending.**
This is a locally validated CI workflow. No hosted workflow was executed and
no repository publication, commit, push, deployment or Step 5G work occurred.
The substantial original dirty tree was preserved. No private .env was read or
modified, no customer data or real AI was used, and no historical migration was
changed. Canonical commands/policies are in [CI.md](CI.md).

The table covers all 67 requested report items.

| # | Requested item | Result/evidence |
| --- | --- | --- |
| 1 | Status | LOCALLY COMPLETE REMOTE RUN PENDING; all applicable local mandatory gates passed. |
| 2 | Platform | GitHub Actions; one canonical workflow. |
| 3 | Existing CI | None found; no Git remote configured, no alternate-host metadata. |
| 4 | Architecture after 5F | Five independent mandatory jobs -> always-evaluated aggregate quality-gate. Shared cross-platform wrapper; existing test/service architecture reused. |
| 5 | Workflow files | `.github/workflows/quality.yml`. |
| 6 | Triggers | All push/PR; manual dispatch; weekly Monday 03:17 UTC schedule. No branch guesses or path filters. |
| 7 | Permissions | contents read only; checkout does not persist token credentials. |
| 8 | Python | Exact 3.12.14, fresh workspace virtual environment; hosted ubuntu-24.04. |
| 9 | Node | Exact 22.22.2, matching production build; local fresh distribution checksum verified, npm 10.9.7. Docker retains established integrity-verified npm 12.2.0 bootstrap. |
| 10 | PostgreSQL | postgres:16.15 for test service; server query proved 16.15. Runtime image retains established digest and OS update recipe. |
| 11 | Cache | Official pip/npm download caches keyed by requirements/lock; no venv/node_modules/DB/build/secret cache. |
| 12 | Backend job | Canonical requirements-dev install, pip check, full tests with explicit CI plugin, hygiene. |
| 13 | SQLite result | 220 passed, zero failures/errors/skips, 2098 existing deprecation warnings, 70.12 seconds. Includes all 216 baseline tests plus four CI guard cases. |
| 14 | PostgreSQL job | Healthy ephemeral service; authenticated TCP readiness; fresh migration DB; then existing tests_postgres in a separate disposable DB. |
| 15 | PostgreSQL result | 5 passed, zero failures/errors/skips, 81 deprecation warnings, 3.28 seconds. |
| 16 | Skip protection | Missing/wrong URL fails before collection; existing strict fixture URL contract; explicit plugin forces skipped integration suite to failure. Positive/negative skip probes passed. |
| 17 | Migration gate | Import every revision, reject unexpected/multiple heads, create fresh disposable PostgreSQL DB, base -> head, query stored revision, drop only generated DB. |
| 18 | Head result | Exactly e5d4c3b2a1f0; module imports, fresh migration and stored revision passed. No historical changes. |
| 19 | Configuration | Existing production/config tests included and passed; no real provider credentials or weakened validation. |
| 20 | Observability | Full existing request-ID/health/log-privacy suite passed; container normal-log and HTTP secret sentinel checks passed. |
| 21 | Security regressions | Existing authentication/session/CSRF/tenant/IDOR/limits/CORS/header/CSV/rate tests all passed in full suite. |
| 22 | pip check | Passed after clean install and again with security gate; Linux backend no-cache build also ran pip check successfully. |
| 23 | Python audit design | pip-audit 2.9.0 audits installed resolved environment incl. transitives/tools; conservatively fail on every known advisory; no ignore list. |
| 24 | Python audit result | No known vulnerabilities after disposable pip update to 26.2.1. First audit found six records solely in bundled pip 25.0.1; remedied rather than ignored. |
| 25 | npm ci | Passed clean host install (30 packages) and fresh Linux Docker install (33 platform-specific packages); lock unchanged. |
| 26 | Frontend lint | Passed host and Linux build; eight established warnings retained; thresholds unchanged. |
| 27 | Frontend build | Passed clean Node environment and fresh Linux build; Linux catches case-sensitive import issues. |
| 28 | npm audit policy | HIGH/CRITICAL fail including build dependencies; lower severity reported; no audit fix or mutation; network/tool failure blocks. |
| 29 | npm/image findings | Project audit zero findings. Fixed 5E source-map-js advisory is not an exemption. Existing 183 image records retain original severity/disposition ledger; deep Scout review is manual, not a PR/fork account requirement. |
| 30 | Secret scanning | Established Gitleaks 8.30.1; native and exact digest-pinned Docker paths both passed against staged nonprivate source, zero leaks. Exact AUTH revision/value/path rule exception; negative control requires a different synthetic secret in the same file to block. Current-tree scanning, not a new history scan. |
| 31 | Static scanner | No dedicated SAST scanner selected in 5E; no unvalidated redundant tool added. Existing security regressions and migration importability automated and passed; no claim of Bandit/SAST success. |
| 32 | Container job | Production backend/frontend plus PostgreSQL runtime image, no registry login/push; validation + no-cache build + private smoke + finally cleanup. |
| 33 | No-cache result | All three images built successfully: backend 55c7d68ab199, frontend caefbb49bcf4, PostgreSQL 3ca7f5238fd6 (unique namespace leadforge-ci-fcbd3a38110e). Existing baseline image tags preserved. |
| 34 | Compose result | docker-compose.yml and runtime + CI override validation passed using explicit empty deploy/compose.env and synthetic shell values. Final TCP health override validated. |
| 35 | Runtime smoke | Passed /, /frontend-health, /health, /ready from private backend-to-frontend HTTP with canonical Host; frontend assets and ready database proved. No additional published runtime ports. |
| 36 | AI isolation | Mock forced, credentials/tracing removed in child env, Gemini/Ollama adapters fail closed with LEADFORGE_CI, test sockets blocked externally. Synthetic-credential subprocess guard tests passed. |
| 37 | Synthetic values | Ephemeral fixture DB password only; random synthetic per-stack runtime password; no production/repository secrets or paid provider keys. |
| 38 | Secret leak result | Generated runtime password absent from smoke bodies and captured service logs. Existing isolated privacy/config regression tests passed; no raw env/config/log upload. |
| 39 | Action pinning | Three official release SHAs verified via read-only upstream tag lookup. Gitleaks image registry digest recorded and pinned; native release checksum verified. |
| 40 | Injection review | No untrusted event text inside run scripts. Needs JSON and base SHA transported through env; SHA validated and passed to Git argv; no eval or shell-built source commands. |
| 41 | Fork/PR review | Ordinary pull_request, no pull_request_target, production secrets, persisted checkout credentials, write permission, deployment or uploads. |
| 42 | Timeouts | Backend/PG/security 15m, frontend 10m, container 30m, aggregate 2m; wrapper subprocess limits, PG connect 5s, TCP wait 60s, Compose wait 180s. |
| 43 | Concurrency | Event + PR/ref groups; only superseded pull_request runs cancel. Main push verification is not cancelled by a newer commit. |
| 44 | Aggregate | Requires success from all five mandatory jobs, runs always; exact inline command probed with success/failure/skipped/cancelled and behaved correctly. No branch protection changes. |
| 45 | Schedule | Same canonical workflow weekly; repeats dependency audits and quality checks. No deployment or production credential dependency. |
| 46 | Local scripts | scripts/ci.py plus scripts/ci_pytest.py; portable argument/subprocess calls, named gates and full sequence; exact Windows/Linux setup and commands in CI.md. |
| 47 | Clean Python | New .venv-ci created with bundled Python 3.12.14; canonical requirements installed from index; full suite/check/audit passed. Existing venv's missing interpreter was not repaired or used. |
| 48 | Clean frontend | Checksum-verified local Node 22.22.2; npm ci reinstalls from lock; lint/build/audit passed, no copied node_modules. |
| 49 | Disposable PostgreSQL | Newly created --rm container, exact synthetic fixture identity, random migration and integration DBs; cleanup passed. No persistent developer data or SQLite fallback. |
| 50 | Full equivalent | Every mandatory underlying gate passed in local batches: backend, PostgreSQL+migrations, frontend, dependency security, native/container Gitleaks, clean image+smoke, Compose and hygiene. Does not claim one hosted run or one uninterrupted full wrapper invocation. |
| 51 | Workflow syntax | actionlint 1.7.7 passed; optional ShellCheck/Pyflakes absent and disabled. PyYAML structural checks passed; all timeouts, permissions/jobs inspected. |
| 52 | Hosted execution | Pending; repository intentionally not committed/pushed. Scheduler/fork/cache/aggregate runner behavior awaits actual GitHub execution. |
| 53 | Database integrity | Before/after SHA-256 unchanged: 217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a. |
| 54 | Diff check | Initial and final git diff --check passed. New CI-file whitespace/LF checked; no unrelated formatting. Existing old HEAD whitespace is not rewritten or retroactively gated. |
| 55 | Files created | .github/workflows/quality.yml; .gitleaks.toml; requirements-ci.txt; scripts/ci.py; scripts/ci_pytest.py; deploy/compose.ci.yml; tests/test_ci_guards.py; docs/CI.md; this report. |
| 56 | Files modified | .gitignore/.dockerignore add local CI tools/venv exclusions; README/DEVELOPMENT link CI; Gemini/Ollama add CI guard; two fake-SDK test bodies clear guard only under fake client. Other pre-existing changes preserved. |
| 57 | Documentation | New canonical CI.md and this 67-item report; concise README and DEVELOPMENT links. Existing security/image/config/observability docs retained. |
| 58 | Limitations | Hosted run pending; Python transitives and OS packages not fully locked; image deep scans/manual history review not automated PR gates; no browser E2E/SAST/deployment certification; warnings retained. |
| 59 | Security carry-forward | All 5E residual image findings remain documented, none silently resolved; manual applicability review must address new HIGH/CRITICAL on image change. No blanket image advisory suppression. |
| 60 | Login budget | Shared proxy-peer login budget remains; CI does not fix or silently disable it. |
| 61 | Database role | Local superuser-style role remains excessive for production; tests require CREATE DATABASE. Production identity separation remains future work. |
| 62 | Fast commands | `python scripts/ci.py backend`; `python scripts/ci.py hygiene`; frontend work: `python scripts/ci.py frontend`. Use installed clean environment as documented. |
| 63 | Full commands | Create unique --rm postgres:16.15 fixture on loopback55432; set LEADFORGE_POSTGRES_ADMIN_URL; `python scripts/ci.py full`; finally stop only that created container. Exact PowerShell/Linux blocks in CI.md. |
| 64 | Job sequence | Install -> backend/full isolated tests+hygiene; service+install -> migration+PG tests; npm ci -> lint -> build; install -> Python/npm audit -> secrets; Compose -> no-cache images -> private stack -> HTTP/log smoke -> cleanup. All five -> quality-gate. |
| 65 | Troubleshooting | CI.md covers install/conflict/SQLite/PG health/migration/skips/npm/lint/build/container/advisory/secret/aggregate failures. Never weaken production, tenant or secret controls to pass. |
| 66 | Deferred 5G+ | Backup/recovery, production role deployment, staging/cloud/DNS/TLS, registry publication, browser E2E, real provider validation, remote branch protection. None started. |
| 67 | Recommendation | Keep changes uncommitted for review; when publication is separately authorized, run first hosted Quality workflow and inspect aggregate before enforcing branch protection. Stop after 5F. |

## Corrected local validation attempts

The initial shell PATH lacked tools; read-only discovery found bundled Python,
Git and later the existing Docker Desktop install. Sandbox-restricted downloads
were retried with authorized network access, without exposing private files.
Docker's engine was stopped; it was started in the background, restoring the
existing local runtime. The CI overlay uses no host ports and unique image tags
so that runtime/volume was not replaced. Its original three containers remain.

An initial blanket provider monkeypatch incorrectly blocked fake-SDK regressions.
It was replaced with adapter guards plus socket restrictions; two existing test
bodies explicitly retain fake-SDK coverage. Windows asyncio required loopback
TCP; the final guard permits loopback and blocks external addresses. An early
YAML parse caught an unquoted SQLite colon; corrected and actionlint passed.
Gitleaks' absolute staged paths required a suffix path rule for the already
reviewed exact revision. A negative control exposed global path prefiltering;
moving the exact exception to generic-api-key's rule-specific allowlist restored
detection of other values in the same file. This negative control is automated
in both scanner paths. A fresh venv bundled
pip 25.0.1 triggered six advisories; pinned pip 26.2.1 removed them. The initial
PostgreSQL startup probe saw the entrypoint's temporary socket listener too
early; TCP health plus bounded authenticated TCP readiness corrected it. Final
successful results above replace those failed attempts; failures were not
suppressed, tests were not skipped, and prior verification counts were not
reused as current evidence.
