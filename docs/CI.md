# CI quality gates

Step 5F uses one GitHub Actions workflow, `.github/workflows/quality.yml`.
Discovery found no existing GitHub, GitLab, Azure, Jenkins, Make, tox or nox CI.
The local repository has no remote configured, so there is no contrary hosting
metadata. GitHub Actions is the requested default for future GitHub-compatible
hosting; this step does not configure a remote or publish anything.

## Triggers and aggregate status

Every push, pull request and manual dispatch runs all jobs without branch/path
filters. A weekly Monday 03:17 UTC schedule repeats the same gates, including
dependency audits, to detect advisories without source changes. In Bangladesh
this is Monday 09:17. GitHub schedules run only after publication on the default
branch. Separate scheduled provider/deployment workflows are not introduced.

| Job | Commands after installation | Timeout |
| --- | --- | --- |
| backend | `python scripts/ci.py backend`, then `hygiene` | 15 minutes |
| postgres | PostgreSQL service; `python scripts/ci.py postgres` | 15 minutes |
| frontend | `npm ci`, `npm run lint`, `npm run build` in frontend | 10 minutes |
| security | resolved Python audit, npm HIGH/CRITICAL audit, Gitleaks | 15 minutes |
| containers | Compose validation, no-cache builds, private HTTP/log smoke, cleanup | 30 minutes |
| quality-gate | Always evaluate all five upstream results; require success | 2 minutes |

Independent jobs report their own failures. `quality-gate` fails for failed,
cancelled or skipped dependencies; it is suitable for future branch protection.
No remote branch protection is changed. Superseded PR runs can cancel; push,
manual and scheduled runs are not cancelled by a newer commit. Concurrency
groups include the event type and PR/ref to avoid cross-event cancellation.

## Toolchain and caching

Python is exactly 3.12.14, matching the container language runtime. Node is
22.22.2, matching the production frontend build major and patch. CI uses that
Node distribution's npm; the application Dockerfile retains its existing
integrity-verified npm 12.2.0 bootstrap and bundled patches. Both use `npm ci`
against the same frontend lock. No arbitrary latest Node or broad matrix.

Install pip 26.2.1 before requirements: Python's fresh-venv bundled pip 25.0.1
has known advisories. `requirements-dev.txt` remains canonical for backend
tests; `requirements-ci.txt` pins verification-only pip-audit 2.9.0 and PyYAML
6.0.2. They do not enter application images. Runtime direct Python dependencies
are pinned; transitive Python dependencies and pytest-cov are not fully locked.
OS package security updates resolve at build time. This is reproducible
verification from clean inputs, not a bit-identical dependency/image lock.

Only pip downloads and npm cache are cached, keyed by requirements or frontend
lock content through official setup actions. No venv, node_modules, databases,
secrets or build outputs are cached. Official actions are pinned to verified
release commit SHAs: checkout v4.2.2, setup-python v5.6.0, setup-node v4.4.0.
Review upstream release/support changes and intentionally update the SHAs;
never replace them with moving branches. Gitleaks uses its established 8.30.1
release image pinned to the locally verified registry digest in scripts/ci.py.
Native local verification used a versioned binary checked against upstream
release checksums; the wrapper also verifies its reported version.

## Safe configuration and test boundaries

The workflow and wrapper force `AI_PROVIDER=mock`, disable LangSmith/LangChain
tracing, remove inherited provider/integration credentials and private dotenv
selection from child processes, and initially select in-memory SQLite. The
existing SQLite fixture creates its own temporary database before app imports.
Never collect legacy root `test_*.py` scripts: they are not isolated tests.
Environment remains development for the established bootstrap test; individual
production-configuration tests exercise strict production settings without paid
credentials. The full suite includes configuration, privacy, health, auth,
sessions, CSRF, tenant/IDOR, CSV, transport and rate-limit regressions.

`LEADFORGE_CI=1` blocks Gemini and Ollama adapters before client construction,
including in child processes. DeepSeek and legacy direct Gemini access remain
disabled. The explicit pytest plugin also blocks non-loopback socket connects.
Loopback is needed by PostgreSQL and Windows asyncio's socketpair. Fake-SDK
adapter tests temporarily clear the provider guard only after replacing the
SDK client; the network guard remains active. No tests are excluded or skipped
to achieve mock isolation. Four new guard regressions verify direct subprocess
provider blocking with synthetic credentials and skip failure/success behavior.

PostgreSQL uses ephemeral `postgres:16.15`, role/database `leadforge_dev`,
loopback port 55432 and synthetic `leadforge_dev_only`. These are explicitly
disposable fixture values, not repository/production secrets. The fixture's
existing exact URL contract is preserved. Health probes use TCP 127.0.0.1 to
avoid seeing the official entrypoint's temporary Unix-socket server. The wrapper
also waits up to 60 seconds for authenticated TCP, proves server version 16.15,
creates a random database, verifies migration modules/single expected head,
runs base to head, queries the stored revision, and drops only that database.
The integration fixture then creates and drops a different random database.
Expected head is `e5d4c3b2a1f0`; change the assertion only with a reviewed new
migration. All revision modules import; offline env syntax is parsed and env
imports/config are exercised by real migration. No historical revision changes.

Missing/wrong PostgreSQL URL fails before tests; no SQLite fallback. The explicit
pytest plugin changes a skipped integration run to failure. Test failures,
collection errors and no-tests exit codes also remain failures. Counts may grow;
the gate does not require exactly five tests. `leadforge.db` is hashed before
and after each wrapper command, never used as a test DB, and is not created
when absent (normal hosted CI).

## Security and finding policy

`pip check` detects conflicts; pip-audit audits the installed resolved test/tool
environment, including transitives. Because severity is not reliable for every
Python advisory, this gate conservatively fails on **any** Python finding or
audit/network failure. There are no Python advisory exemptions. npm audit fails
on HIGH/CRITICAL (runtime and build dependencies), reports lower severities and
never runs audit fix. There are no npm exceptions: the 5E source-map-js
GHSA-68fv-2mgg-jv7q finding was fixed by 1.2.2 and must not be re-allowlisted.
Any future exception needs advisory ID, exact package/version, scope,
applicability reason, fix availability, reviewer and review date; no broad ignore
or continue-on-error suppression. Audit changes are reviewed, not auto-upgraded.

Gitleaks 8.30.1 scans a temporary copy of Git-listed tracked/untracked nonprivate
source. Private dotenv, databases, symlinks and ignored local tools are not copied
or mounted; Docker receives only the staging directory, read-only and with no
network during scanning. Reports/matches are redacted; native failures print
only file/line/rule. The sole exception is the exact `c3b2a1d0e9f8` revision in
`tests/test_auth_migration.py`, reviewed in 5E. Different values and other paths
remain scanned. A rule-specific allowlist follows the [Gitleaks configuration
contract](https://github.com/gitleaks/gitleaks#configuration); a runtime negative
control adds a generated synthetic secret only to that staged file and requires
the scanner to fail, preventing a global path exception from hiding new secrets.
Current-tree scanning catches newly added likely secrets; it is
not a full-history scan. Retain the 5E history result and repeat a separately
redacted history review before publication when history changes warrant it.
Never upload source to scanning SaaS or publish matches. A genuine finding needs
rotation/disposition, not just deletion from the current file.

5E did not select Bandit or another dedicated SAST tool. This step reuses the
existing security regressions, scanner and migration import checks; it does not
introduce redundant unvalidated static scanners or claim a SAST pass.

Image builds are mandatory for each run; deep image scans remain a manual
security review using the established Docker Scout process in SECURITY.md.
Scout database/account availability is not made a secret-dependent fork gate.
No new image vulnerability exception list is invented. The 183 reviewed 5E
package/CVE records, including residual HIGH/CRITICAL labels, remain in
STEP_5E_IMAGE_FINDINGS.md; building successfully does not resolve them. After
base/OS/dependency changes, rerun deep scanning and review any new HIGH/CRITICAL
against that ledger; applicable new findings block release. This workflow does
not claim automated detection of every new image advisory. Dependency scans
run weekly; image rescans, exact OS locking and production risk certification
remain limitations. This is an explicit policy boundary, not a blanket CVE waiver.

## Container smoke and secret privacy

The wrapper validates docker-compose.yml and compose.runtime.yml with an explicit
empty `deploy/compose.env`, so Compose does not load private `.env`. It combines
`deploy/compose.ci.yml` with the runtime definition: unique project/image names,
project-scoped disposable volume, CI provider guard and **no published ports**.
Compose 2.24.4 or newer is required for the `!reset` port override. Runtime HTTP
requests execute inside the private stack with the canonical public Host.
They check frontend assets, frontend health, process liveness and DB readiness.
Response bodies and captured normal service logs must not contain the random
synthetic DB password. No full environments, rendered secret-bearing Compose,
raw logs or artifacts are uploaded. Build inputs exclude local verification
tools and venv as well as existing secret/database exclusions. `finally` removes
only this generated project's containers, networks and disposable volume even
after failure; unique build images may remain in the local Docker cache.

## Permissions and PR behavior

Only `contents: read`; checkout disables credential persistence. No production
secrets, deployments, packages write, id-token, registry login, image pushes or
artifact uploads. Forks run ordinary pull_request with synthetic configuration,
never pull_request_target or privileged reusable code. Event expressions are
used only in concurrency/job environment, never as shell code. The aggregate
parses JSON from an environment variable. Hygiene validates the base SHA and
passes it as an argument to Git; PR/push diffs are checked as well as local
dirty diffs and new CI-file whitespace. A schedule/first push without a base
checks current CI sources rather than imposing new formatting on old commits.

## Local reproduction

Use Python 3.12.14, Node 22.22.2, Git, Docker/Compose on PATH. A local native
Gitleaks 8.30.1 on PATH avoids the Docker scanner; otherwise the wrapper pulls
the release image. Windows PowerShell commands from repository root:

```powershell
python -m venv .venv-ci
$pythonCI = (Resolve-Path .venv-ci/Scripts/python.exe).Path
& $pythonCI -m pip install pip==26.2.1
& $pythonCI -m pip install -r requirements-dev.txt -r requirements-ci.txt
# Fast checks: no Docker stack or dependency audit required.
& $pythonCI scripts/ci.py backend
& $pythonCI scripts/ci.py hygiene
# For frontend work, reproduce its clean job:
& $pythonCI scripts/ci.py frontend
```

Full verification requires the disposable PostgreSQL service. Preserve any
existing service on port 55432; if occupied, identify it rather than stopping it.
Never substitute a shared DB. This command creates a unique ephemeral service,
then the wrapper repeats the underlying jobs sequentially:

```powershell
$pgCI = 'leadforge-ci-pg-' + [guid]::NewGuid().ToString('N').Substring(0,12)
docker run -d --rm --name $pgCI -e POSTGRES_USER=leadforge_dev -e POSTGRES_PASSWORD=leadforge_dev_only -e POSTGRES_DB=leadforge_dev -p 127.0.0.1:55432:5432 --health-cmd 'pg_isready -h 127.0.0.1 -U leadforge_dev -d leadforge_dev' --health-interval 5s --health-timeout 3s --health-retries 12 postgres:16.15
if ($LASTEXITCODE -ne 0) { throw 'CI PostgreSQL start failed' }
try {
    $env:LEADFORGE_POSTGRES_ADMIN_URL = 'postgresql+psycopg://leadforge_dev:leadforge_dev_only@127.0.0.1:55432/leadforge_dev'
    & $pythonCI scripts/ci.py full
    if ($LASTEXITCODE -ne 0) { throw 'Full quality gate failed' }
} finally {
    docker stop $pgCI | Out-Null
    Remove-Item Env:LEADFORGE_POSTGRES_ADMIN_URL -ErrorAction SilentlyContinue
}
```

Linux equivalents (same Python/Node versions):

```sh
python3 -m venv .venv-ci
.venv-ci/bin/python -m pip install pip==26.2.1
.venv-ci/bin/python -m pip install -r requirements-dev.txt -r requirements-ci.txt
.venv-ci/bin/python scripts/ci.py backend
.venv-ci/bin/python scripts/ci.py hygiene
pg_ci="leadforge-ci-pg-$$"
docker run -d --rm --name "$pg_ci" -e POSTGRES_USER=leadforge_dev -e POSTGRES_PASSWORD=leadforge_dev_only -e POSTGRES_DB=leadforge_dev -p 127.0.0.1:55432:5432 --health-cmd 'pg_isready -h 127.0.0.1 -U leadforge_dev -d leadforge_dev' --health-interval 5s --health-timeout 3s --health-retries 12 postgres:16.15 || exit 1
trap 'docker stop "$pg_ci" >/dev/null' EXIT
export LEADFORGE_POSTGRES_ADMIN_URL='postgresql+psycopg://leadforge_dev:leadforge_dev_only@127.0.0.1:55432/leadforge_dev'
.venv-ci/bin/python scripts/ci.py full
```

Individual gates: `backend`, `postgres`, `frontend`, `security`, `secrets`,
`containers`, `hygiene`, `migrations`. `full` runs backend -> postgres -> frontend
-> security -> secrets -> containers -> hygiene. It fails at the first failure;
hosted jobs run independently. No destructive Git operation or remote mutation.
Use `actionlint -shellcheck= -pyflakes= .github/workflows/quality.yml` for local
workflow validation; this disables optional external shell/Python linters only.

## Failure diagnosis

| Failure | Diagnose without weakening the gate |
| --- | --- |
| Python install | Confirm 3.12.14, wheel/index/network availability and canonical requirements; use a fresh venv, never the broken old interpreter path. |
| pip conflict/advisory | Run pip check and pip-audit; inspect exact dependency/advisory, patch/review intentionally. Bundled old pip requires the pinned CI tool update. |
| SQLite/config/privacy/security | Run the named failing test with the CI plugin; retain real auth/CSRF/tenant/production validation. Existing deprecation warnings are not failures. |
| PostgreSQL health | Check loopback port/engine and TCP health; initialization's Unix socket can be misleading. Wrapper has bounded authenticated retry. |
| Migrations/imports/head | Check module import, revision graph and disposable DB; expected single head is explicit. Never rewrite old revisions or bootstrap with create_all. |
| PostgreSQL skips | Set the exact disposable admin URL and run postgres wrapper; missing service/config fails. Do not remove the no-skips plugin. |
| npm ci | Check Node 22.22.2, manifest/lock consistency and registry; npm ci must install from lock. |
| Lint/build | Reproduce in frontend; retain thresholds. Linux container build catches case-sensitive imports. |
| Container/Compose | Verify running engine, Compose >=2.24.4, base registry/package access, and explicit env-file; use unique projects and bounded waits. Never prune/reset local state. |
| Security finding | Review advisory scope/fix and carry the image ledger forward; no audit fix --force, broad ignores or suppressed exit codes. |
| Secret scan | Use redacted file/line/rule, rotate a real secret, and keep the exact migration false-positive exception narrow. |
| Aggregate failure | Inspect every upstream job: skipped/cancelled is a failure, not a pass. |

Shared login budget and the local superuser-style PostgreSQL role remain
documented security limitations. Production role separation, deployment,
staging, backups/recovery and browser E2E belong to later phases. Stop at 5F.
