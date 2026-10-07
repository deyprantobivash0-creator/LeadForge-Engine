# Development workflow

Step 5F adds GitHub Actions and cross-platform local checks. See [CI.md](CI.md)
for fast checks, the full disposable quality gate, security policy and failure
diagnosis. The [5F verification report](STEP_5F_VERIFICATION.md) distinguishes
local command validation from a hosted workflow run.

For the Step 5B frontend/backend/database stack requiring no host Python or
Node runtime, see [local container runtime](CONTAINERS.md). The 5A workflow
below remains independent and unchanged.

## Step 5A verification ? October 6, 2026

Use `127.0.0.1` for this IPv4-only Compose binding. On the verified Windows
host, `localhost` resolved to both `::1` and `127.0.0.1`; IPv6 TCP timed out,
and psycopg took 5.05 seconds with a five-second connect timeout before IPv4
succeeded. Direct IPv4 connections plus a query took 15?31 milliseconds.
This demonstrates an address fallback delay; the historical BrokenBarrierError
and 407-second run were not reproduced, so their exact cause is unconfirmed.

The import race now synchronizes only the shared email at the repository write
boundary, proves two PostgreSQL backend connections and the exact tenant/email
unique violation, and collects both worker exceptions. Test-local lock and
statement timeouts bound database waits. PostgreSQL duplicate handling checks
SQLSTATE 23505 and `uq_leads_organization_email`; unrelated errors propagate.
The race proves savepoint recovery, subsequent row insertion, commit, and
single-row uniqueness. A real NOT NULL violation also verifies error propagation
and operation rollback. SQLite keeps its existing duplicate handling.

Final verification: three isolated races passed in 2.84, 2.88, and 3.02 seconds;
all five PostgreSQL tests passed without skips/errors in 4.14 seconds; all 127
SQLite tests passed in 61.42 seconds with `ENVIRONMENT=development` (required by
the development-bootstrap test). Dependency checking, frontend lint/build,
and diff/edited-file whitespace checks passed. Existing lint and deprecation
warnings remain. Compose down/up and reset/recreate passed after confirming
the named development volume contained no application data (the leftover test
database had no application tables). Fresh base-to-head migration succeeded;
heads/current both reported `e5d4c3b2a1f0`. `leadforge.db` retained its original
SHA-256 hash. AI remained mock. No historical migration changes, commits, or
pushes were made. Step 5A verification is complete; Step 5B remains unstarted.

## Step 5A disposable PostgreSQL baseline

The default isolated `tests/` suite and the existing `sqlite:///./leadforge.db`
development URL remain supported. PostgreSQL uses psycopg 3. The Compose file
starts only a local database, bound to `127.0.0.1:55432`, with deliberately
non-production credentials. It does not contain customer data or an app image.
Run these commands from the repository root after installing Docker Desktop:

```powershell
docker compose config
docker compose up -d --wait postgres
docker compose ps
$env:ENVIRONMENT = "development"
$env:AI_PROVIDER = "mock"
$env:DATABASE_URL = "postgresql+psycopg://leadforge_dev:leadforge_dev_only@127.0.0.1:55432/leadforge_dev"
./venv/Scripts/python.exe -B -m alembic upgrade head
./venv/Scripts/python.exe -B -m alembic current
$env:LEADFORGE_POSTGRES_ADMIN_URL = $env:DATABASE_URL
./venv/Scripts/python.exe -B -m pytest -q tests_postgres
Remove-Item Env:LEADFORGE_POSTGRES_ADMIN_URL
docker compose down
```

The PostgreSQL tests create a random `leadforge_test_*` database, migrate it
from base to head, and drop it after the run. They require the exact local
Compose host, port, database, and user; without the URL they skip. Run the
default SQLite suite separately with `./venv/Scripts/python.exe -B -m pytest -q
tests`. The root `pytest.ini` collects only `tests/` by default. Use
`./venv/Scripts/python.exe -B -m pip check` for dependency consistency.
The pinned runtime requirements were also installed successfully into a clean
temporary Windows virtual environment on October 5, 2026; `pip check` and a
mock-AI application import passed there. This does not replace the live
PostgreSQL migration and integration checks.

To destroy and recreate **only this disposable PostgreSQL Compose volume**,
first check that it contains no data you need, then run `docker compose down
-v` followed by `docker compose up -d --wait postgres`. `down -v` irreversibly
deletes the Compose database volume. It does not touch `leadforge.db`. To
return to local SQLite, set `$env:DATABASE_URL =
"sqlite:///./leadforge.db"` and remove `LEADFORGE_POSTGRES_ADMIN_URL` from
the current shell. Never point the PostgreSQL test fixture at a shared or
production database.

This baseline does not define production deployment. Before Step 5B, review
connection pool sizing/lifetime, statement and idle transaction timeouts,
migration coordination, backups/restore drills, and report/export load. The
current timestamp columns store naive UTC and should keep that convention
until an explicit migration is designed. The local Compose password must be
replaced by secret-managed production credentials.

Step 4G release-surface QA keeps the backend suite isolated in `tests/` and
uses mock AI. The active frontend paths are `/`, `/leads`, `/imports`, `/ai`,
`/ai/:leadId`, `/reports`, and `/settings`; an authenticated unknown path shows
a not-found view. The shell remounts on workspace change. Saved analysis times
are displayed as UTC. Manual viewport checks at 1440, 1024, 768, and 390 px
remain necessary before release; a passing build is not visual verification.

For Step 4F, `/settings` uses `GET /api/settings/overview` with the selected
workspace header. Browser verification should check account email, workspace
name and role, read-only AI configuration status, Import and Reports links,
planned integration labels, workspace switching, retry on failure, and the
existing sign-out flow. Tests use the isolated SQLite fixture and mock provider;
Settings status itself makes no provider call or development database write.

Step 4E Reports checks: run isolated `tests/api/test_reports_v2.py`, then the
full `tests/` suite with `AI_PROVIDER=mock` (set by `tests/conftest.py`). The
Reports page is `/reports`; select Today, 7 days, 30 days, or a custom UTC
date range, inspect event and unique Lead counts, then export CSV. A workspace
with no events correctly shows an empty state. Automated checks use disposable
SQLite and must not update `leadforge.db`.

Repository root on the current Windows workspace: `C:\Agency Products\LeadForge-Engine`. Commands below run from that root unless noted. First inspect the local tool availability; do not install packages or contact providers as an incidental verification step.

## Before coding

1. Read root `AGENTS.md` and the relevant domain document.
2. Inspect the existing route, service, repository, model, schema, frontend caller, and tests along the affected path.
3. Search for duplicate responsibilities, particularly ingestion and AI workflows.
4. For substantial changes, state an implementation plan and the contract or migration decisions it depends on.
5. Inspect `git status --short` so pre-existing work is not overwritten.

## Backend workflow

Use `backend/main.py` as the registered FastAPI entry point. Keep new customer operations tenant scoped through an authenticated organization dependency; services own business transactions and repositories own SQL queries. Root `pytest.ini` limits normal collection to `tests/`, excluding root-level executable `test_*.py` scripts that may call Gemini or write the development database. `tests/conftest.py` sets a disposable SQLite URL and mock AI provider before test imports and supplies an isolated `client` fixture. The older empty `tests/confest.py` remains unused. Explicitly naming a legacy root script on the pytest command line bypasses this protection; do not do that.

Supported test command from the repository root (with the existing local virtual environment):

```powershell
./venv/Scripts/python.exe -B -m pytest -q
```

This safe collection baseline does not mean every existing assertion is current. Diagnose failures against the actual API contract before changing product code or historical tests.

Read-only inspection examples:

```powershell
git status --short
git diff --stat
rg --files backend frontend/src alembic tests
rg -n 'organization_id|SessionLocal|create_all|AIOrchestrator' backend
```

Run selected isolated tests against the disposable database. Never run `backend/database/init_db.py` or legacy root scripts as a verification shortcut; `init_db.py` calls `create_all()`.

## Frontend workflow

The Vite app is under `frontend/`. `frontend/src/services/api.js` returns parsed JSON directly. Match API fields and vocabulary to `docs/API_CONTRACTS.md`; use real data or visibly marked fixtures. On the current installation, the local linter was run read-only with:

```powershell
Set-Location frontend
./node_modules/.bin/oxlint.cmd src
```

`npm run lint` is the manifest script for that checker. `npm run build` is the frontend production build command; it writes generated `dist/`, so run it only when file creation is allowed and review the result on a case-sensitive environment. Do not treat an exit-0 lint with warnings as a production build.

## Alembic and environment

Step 3B.2A adds Argon2id via `argon2-cffi==25.1.0` and revision `c3b2a1d0e9f8`. `backend/core/passwords.py` is the password API; `backend/core/session_tokens.py` creates 32-byte random bearer tokens and SHA-256 digests. Persist only password hashes and token digests. The isolated migration tests cover clean and populated SQLite upgrades and the new revision's downgrade.

Step 3B.2B implements `/api/auth/login`, `/logout`, `/me`, session validation, and session-bound CSRF for logout. Step 3B.2C requires active Organization membership on Lead routes, uses `X-Organization-ID` only as a selector, and requires CSRF on lead writes. Step 3B.2D applies the same authorization to Dashboard and Report routes and scopes their analysis aggregates, date windows, and top lists in SQL. Analytics count LeadAnalysis rows, including history. Step 3C defines current/history selection. `SESSION_COOKIE_SECURE=true` is the default and mandatory outside development/test. For a local HTTP server, set `SESSION_COOKIE_SECURE=false` explicitly with `ENVIRONMENT=development`; HTTPS tests keep it true. `SESSION_TTL_SECONDS` defaults to seven days. Cookie names and SameSite policy are in `.env.example`. Allowed browser origins are configured through explicit `CORS_ORIGINS`; `*` is rejected. Login uses the existing in-process SlowAPI limiter at 10 attempts per IP per minute. A reverse proxy must provide a trustworthy client address before production; distributed rate limiting remains future work. There is no auto-created development account or registration endpoint.

`alembic.ini`, `alembic/env.py`, and `alembic/versions/` define migration configuration. `alembic history` is a read-only way to inspect revision order. Schema drift and migration checks should target a disposable database whose URL is explicitly set for that check; never run upgrade/downgrade, `create_all()`, or tests that write against `leadforge.db` during an analysis-only task. Validate clean SQLite and PostgreSQL paths when infrastructure exists.

`.env.example` documents expected variable names. `.env` is local and ignored by Git: never print, commit, or casually edit its contents. Avoid commands that log API keys or prompts. Use the mock AI provider for ordinary development and tests. External Gemini, DeepSeek, or Ollama calls require an explicit test purpose and must not occur during safe checks.

## Step 3B.2E local login verification

The frontend now restores `/api/auth/me`, loads `/api/organizations`, and requires an explicit selected workspace before customer pages mount. All customer calls use the selected ID as `X-Organization-ID`; the backend authorizes membership again on every call. A 401 returns to login. A customer-route 403 refreshes available workspaces and clears a selection that is no longer available. The frontend stores only a per-user workspace ID preference, never a session token. The default browser-readable CSRF cookie is `leadforge_csrf`; authenticated writes send it as `X-CSRF-Token`. If backend cookie/header names change, set `VITE_CSRF_COOKIE_NAME` and `VITE_CSRF_HEADER_NAME` to match.

These commands are **manual** and modify the chosen database. They were not run against `leadforge.db` during automated verification. From the repository root, use the same `localhost` host on both ports:

```powershell
$env:ENVIRONMENT = "development"
$env:SESSION_COOKIE_SECURE = "false"
$env:DATABASE_URL = "sqlite:///./leadforge.db"
./venv/Scripts/python.exe -B -m alembic upgrade head
./venv/Scripts/python.exe -B -m scripts.bootstrap_dev_user --database-url "sqlite:///./leadforge.db" --email "you@example.com"
./venv/Scripts/python.exe -B -m uvicorn backend.main:app --reload --host localhost --port 8000
```

The bootstrap prompts for a password, creates or reuses `leadforge-dev` and owner membership, and refuses production mode or password reset. In a second terminal:

```powershell
Set-Location frontend
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev -- --host localhost
```

Open `http://localhost:5173`, sign in, select the returned workspace, then open Leads, Dashboard, Reports, and Import. Open a Lead and save a lifecycle change to verify CSRF; sign out and revisit a protected URL. To test expiration and membership removal, use a disposable account/session: a customer 401 should return to login, and a membership 403 should refresh the available workspace list.

## Step 4D manual CSV verification

Use a development workspace and a synthetic file only; do not run an import against the real development database as part of automated checks. Save this UTF-8 text as `synthetic-import.csv`:

```csv
company,email,source
Example Import One,import-one@example.com,csv-test
Example Import Two,import-two@example.com,csv-test
```

Sign in and select the workspace. Open `/imports`, choose the file, then click Preview. Expect total 2, ready 2, duplicates 0, invalid 0. Check the Leads page before confirmation to verify no new records. Return to Import, preview again, and explicitly confirm. Expect imported 2 and no AI scores. Open Leads and confirm the rows are `New`/`pending` and unanalyzed. Preview the same file again; expect two duplicates and a disabled import button. For validation, try a copy with a malformed email and a repeated email. The browser sends raw `text/csv` through the central API client with cookies, CSRF and selected workspace; the backend accepts at most 1 MiB/1,000 data rows and displays at most 100 preview rows. A preview token expires in 15 minutes; retry preview after expiration or workspace change.

## After coding

1. Run relevant safe, isolated tests; state what was skipped and why.
2. Run the frontend build when frontend code changed and creation of `dist/` is authorized.
3. Verify migrations on disposable databases when schema changed.
4. Inspect `git diff` and `git status --short` for unintended files.
5. Report files changed, verification results, and unresolved issues. Do not claim a capability works solely because code or a placeholder exists.
# Step 3C migration

After reviewing the migration, apply it manually to the development database
with `./venv/Scripts/python.exe -m alembic upgrade head` from the repository
root. Automated migration tests use disposable SQLite files and do not touch
`leadforge.db`. Step 3C does not register a processing route or call an AI
provider. Unlinked historical analysis is retained for review.

## Step 3D development and manual provider check

Step 3D adds migration `e5d4c3b2a1f0`. After review, manually run
`./venv/Scripts/python.exe -m alembic upgrade head` for the development
database. Tests use disposable SQLite and `AI_PROVIDER=mock`; they do not call
external models. The mock is restricted to development/test and returns only
insufficient-evidence assessments. Configure `AI_PROVIDER=gemini` with a
user-supplied `GEMINI_API_KEY`, or `AI_PROVIDER=ollama` with local host/model,
only for an explicit manual smoke test on a safe development Lead. Such a test
may incur provider usage or cost. Start the dev server, sign in, select the
workspace, process that Lead from LeadDetails, then inspect its detail and
analysis history. Never print or log the key. Gemini and Ollama adapters have
not been manually verified here; DeepSeek is unsupported. `AI_TIMEOUT_SECONDS`
and `AI_MAX_ATTEMPTS` bound provider calls. Backend execution remains
synchronous; a future worker can invoke the same service after a claim without
moving scoring or persistence into the route.

-v` followed by `docker compose up -d --wait db`. `down -v` irreversibly
-v` followed by `docker compose up -d --wait postgres`. `down -v` irreversibly

## Step 5C configuration boundary

See [Configuration and secrets](CONFIGURATION.md) for strict environment selection,
explicit development dotenv opt-in, startup validation and the production matrix.
No `.env` is loaded automatically. Existing runtime Compose explicitly selects
`development`, mock AI and local HTTP cookies. It remains a local demonstration.

## Step 5G recovery verification

See [Backup and recovery](BACKUP_RECOVERY.md) for explicit backup/restore commands,
fresh-target safeguards and the repeatable synthetic PostgreSQL recovery drill.
The drill uses its own disposable database and mock-provider backends; never
restore over the normal runtime or `leadforge.db`. See [recorded results](STEP_5G_VERIFICATION.md).

## Step 5H staging preparation

See [staging deployment](STAGING.md) for the separate Compose project, strict
production/mock opt-in, role-separated database, source snapshot, TLS and
authorization gate. Local rehearsal is not remote staging completion. The
existing development runtime remains separate and its behavior is unchanged.
