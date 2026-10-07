# Step 5B local container runtime

This is a production-like local development runtime, not a production
deployment. It uses production Vite assets, Nginx and Uvicorn, but explicitly
keeps `ENVIRONMENT=development`, `AI_PROVIDER=mock` and non-secure cookies for
loopback HTTP. Mock remains prohibited outside development/test. Production
configuration, TLS and the later Phase 5 operating controls remain deferred.

## Architecture

Browser `http://127.0.0.1:8080` → Nginx frontend → FastAPI backend → PostgreSQL.
Frontend joins an ingress bridge and the internal runtime network. Backend,
migration and PostgreSQL join only the internal network. Only frontend port
8080 is published, bound to host IPv4 loopback. Backend and PostgreSQL have no
host port publication. The original `docker-compose.yml` and 5A volume remain
independent and unchanged.

| Connection | Address |
| --- | --- |
| Browser frontend/API | `http://127.0.0.1:8080`, `/api/...` |
| Nginx to backend | `backend:8000` using Docker DNS |
| Backend/migration to PostgreSQL | `postgres:5432` |
| Existing 5A host development/tests | `127.0.0.1:55432` |

Backend uses a digest-pinned Python 3.12 slim Bookworm base, cached installation
of the existing requirements, explicit source/migration copies and UID/GID
10001. One Uvicorn worker runs without reload, directly as PID 1. This also
preserves the current in-process login limiter's behavior. Uvicorn ignores
forwarded headers and has a 30-second graceful shutdown timeout; Compose
allows 40 seconds. Logs go to stdout/stderr.

Frontend builds with digest-pinned Node 22, `npm ci`, lint and Vite production
build. The final digest-pinned Nginx image contains static assets without Node
or its dependencies. Nginx runs as UID/GID 101 on port 8080. Both application
containers are read-only, use writable `/tmp` tmpfs, drop capabilities and
enable `no-new-privileges`. Build contexts exclude local environments,
databases, Git metadata, caches, build output and host dependencies.

## Build, start and stop

From the repository root, with Docker Desktop running:

```powershell
# Existing disposable development placeholder; never production credentials.
$env:LEADFORGE_RUNTIME_DB_PASSWORD = "leadforge_dev_only"
$runtimeCompose = @("--env-file", "deploy/compose.env", "-f", "compose.runtime.yml")
docker compose @runtimeCompose config --quiet
docker compose @runtimeCompose build --no-cache
docker compose @runtimeCompose build
docker compose @runtimeCompose up -d --wait
docker compose @runtimeCompose ps -a
docker compose @runtimeCompose logs --tail 100 postgres migrate backend frontend
docker compose @runtimeCompose down
```

No host Python or Node installation is required for building or starting.
Open `http://127.0.0.1:8080`. A fresh database has no users or memberships.
There is no automatic account creation, default workspace or AI invocation.

`deploy/compose.env` is intentionally empty. Always supply `--env-file` as shown
so Compose does not load the repository's private `.env`. The password comes
from shell injection, not image build arguments or image environment. For
this local workflow use the existing URL-safe development placeholder.
Changing initialization variables does not rotate an existing database's
credentials. `VITE_*` values are public; only a relative API base is built.

## Migrations and readiness

`migrate` uses the backend image and the same injected `DATABASE_URL`. It waits
for healthy PostgreSQL, runs `python -m alembic upgrade head` and exits. Backend
startup depends on successful completion; frontend startup depends on backend
readiness. Migration failure exits nonzero and prevents backend/frontend
startup. Do not bypass this ordering by starting dependencies manually.

For an explicit migration after building:

```powershell
docker compose @runtimeCompose up -d --wait postgres
docker compose @runtimeCompose run --rm migrate
docker compose @runtimeCompose up -d --wait
```

`/health` preserves process liveness. `/ready` checks database access and matches
database revisions against the shipped Alembic heads. HTTP 503 indicates an
inaccessible/uninitialized database or outdated schema; 200 means ready.
Repository checks close their sessions. PostgreSQL connections have a
five-second timeout. Application pools use pre-ping and a five-second
acquisition timeout with SQLAlchemy's default pool size/overflow. Migration
connections are bounded too.

`/frontend-health` checks only the static server. `/health` and `/ready` through
Nginx check the backend. With backend unavailable, API/readiness requests fail
with 502, never SPA HTML. Dependency loss does not itself trigger automatic
migration/restart: inspect readiness and restore the dependency.

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/frontend-health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/ready
docker compose @runtimeCompose exec backend id
docker compose @runtimeCompose exec frontend id
docker compose @runtimeCompose exec backend python -m alembic current
```

## Browser/API boundary

The browser uses same-origin `/api` URLs. Proxying preserves complete paths,
queries, cookies, CSRF and organization headers. Host development retains the
wrapper's `http://localhost:8000` default; explicit build configuration `/`
activates relative URLs. JSON shapes and credential inclusion remain unchanged.

Local HTTP cookie settings are explicit development settings. Sessions remain
HttpOnly; CSRF cookies remain readable; both retain SameSite and root path.
CORS/login-origin checks allow only `http://127.0.0.1:8080` and
`http://localhost:8080`, never wildcard credentialed origins. Uvicorn does not
trust forwarded headers in this local setup. TLS and trusted client-address
forwarding require a later deployment design.

Nginx provides history fallback for `/`, `/leads`, `/imports`, `/ai`,
`/ai/:leadId`, `/reports` and `/settings`. Missing assets return 404. API errors
never fall back to `index.html`. Docker DNS is re-resolved after backend
replacement. Proxy read timeout accommodates the current bounded synchronous
AI workflow; no real provider is enabled.

## Disposable smoke data and persistence

The optional script must be explicitly piped into the runtime backend. It
refuses other database hosts, modes, providers and unmarked runtimes. It creates
only `runtime-smoke@example.com`, two `runtime-smoke-*` workspaces and a
synthetic imported Lead. Its fixture password is `container fixture password`,
solely for this disposable workflow. Never use it for customers or deployment.

```powershell
Get-Content scripts/container_smoke.py | docker compose @runtimeCompose exec -T backend python -
docker compose @runtimeCompose down
docker compose @runtimeCompose up -d --wait
Get-Content scripts/container_smoke.py | docker compose @runtimeCompose exec -T backend python - --check-persistence
```

The script checks the real Nginx/API boundary: health, SPA paths, sessions,
cookie attributes, explicit CORS, CSRF rejection/success, workspace membership,
cross-tenant denial, Dashboard, Leads, non-mutating preview and CSV confirmation,
Intelligence, Reports/CSV and Settings. Ordinary `down` preserves
`leadforge-runtime-local_leadforge_postgres_runtime_local`.

Before reset, inspect the exact project/volume and verify it contains only
disposable data you do not need. Then, only for this runtime file:

```powershell
docker volume inspect leadforge-runtime-local_leadforge_postgres_runtime_local
docker compose @runtimeCompose down -v
docker compose @runtimeCompose up -d --wait
```

This destroys this runtime's named volume. Never reset customer/shared data.
It neither removes the 5A volume nor touches `leadforge.db`.

## Troubleshooting and deferred scope

- Missing password: Compose fails configuration before creating services.
  Supply it in the invoking shell; do not put credentials in images.
- Failed migration: inspect `logs migrate`, correct runtime configuration and
  rerun normal `up -d --wait`. Never rewrite historical migrations.
- 503 readiness: check PostgreSQL and revision; restore dependencies first.
- 502 API: check backend logs/readiness and DNS. Static-server health alone
  does not prove application readiness.
- Unreachable frontend: check the free loopback port and ingress bridge.
  An internal-only network cannot publish the browser port on the verified
  Docker Desktop engine.
- No account: explicitly create disposable smoke fixtures as above.
- Existing lint/deprecation and dependency-audit warnings remain for later
  scoped work. Do not run audit fixes as routine startup.

Full production secrets/configuration, TLS, observability, security audits,
CI/CD, backup/recovery, deployment, real provider validation, load/browser E2E
and release readiness remain deferred. This milestone is not production readiness.

## Verification evidence — October 6, 2026

Step 5B is complete for the local runtime. Final inspection showed PostgreSQL,
backend and frontend healthy, migration exited 0, and application restart counts
zero. Only `127.0.0.1:8080` is published. PostgreSQL remains version 16.15 and
its process runs as UID 999; application UIDs are 10001 and 101.

| Gate | Observed result |
| --- | --- |
| Clean full-stack `build --no-cache` | Passed |
| Subsequent cached builds | Passed; dependency and frontend build layers cached |
| Backend / frontend image sizes | 612,091,538 / 93,512,349 bytes |
| Startup and `/ready` | Healthy; HTTP 200 with database `ok` |
| SPA direct navigation and browser refresh | All seven paths rendered |
| Rendered login, workspace selection, logout | Passed; no JavaScript page errors |
| Real Nginx/API synthetic smoke | Passed, including CSRF/CORS and tenant denial |
| Ordinary down/up persistence | Account, memberships and imported Lead retained |
| Safe disposable reset/recreate | Passed; fresh migration and smoke passed |
| PostgreSQL stopped | `/health` 200; `/ready` 503; recovery passed |
| Migration nonexistent database | Migration exit 1; backend/frontend unstarted |
| Backend stopped | API/readiness 502; static health 200; recovery passed |
| Missing injected password | Compose configuration failed clearly |
| SQLite regression | 129 passed in 60.46s: original 127 plus two readiness tests |
| PostgreSQL regression | 5 passed, no skips/errors, in 4.14s |
| Host and backend-image dependency checks | No broken requirements |
| Clean Linux frontend lint / build | Passed; eight existing lint warnings |
| Alembic current after fresh recreation | `e5d4c3b2a1f0 (head)` |
| Image content and runtime inspection | No private env, local DB, Git, host environments/dependencies, development bind mounts or privileged application containers |
| Git diff and edited-file whitespace checks | Passed |
| `leadforge.db` | Original SHA-256 retained: `217E5D8A5128936BE5FB5FEE8FE1F54036F9106E318514DA5E6E98D485221A4A` |

Clean installation exposed a missing manifest dependency: `main.jsx` imported
Inter from a host ancestor dependency directory. The frontend now declares
`@fontsource/inter==5.3.0` (the existing host font version) in its manifest and
lockfile. Existing npm audit output reports one high-severity advisory; full
dependency/security review is deferred, with no blind audit fix. Existing
datetime/Starlette warnings and the read-only user's pip-cache warning remain
non-blocking. A temporary official browser-test container was removed after
verification. Application builds and startup require only Docker.

No private `.env` contents were printed or edited, historical migration files
rewritten, customer data used, real AI providers called, destructive Git
operations performed, commits created or changes pushed. Step 5C was not started.

## Step 5B file inventory

Created:

- `Dockerfile`, `.dockerignore`, `frontend/Dockerfile`, `compose.runtime.yml`
- `deploy/compose.env`, `deploy/nginx.conf`
- `backend/repositories/runtime_readiness_repository.py`
- `backend/services/runtime_readiness_service.py`
- `tests/api/test_runtime_readiness.py`, `scripts/container_smoke.py`
- `docs/CONTAINERS.md`

Modified (preserving existing work):

- `README.md`, `alembic/env.py`, `backend/main.py`
- `backend/api/routes/system_routes.py`, `backend/database/session.py`
- `frontend/src/services/api.js`, `frontend/package.json`, `frontend/package-lock.json`
- `docs/ARCHITECTURE.md`, `docs/API_CONTRACTS.md`, `docs/DATABASE.md`
- `docs/DEVELOPMENT.md`, `docs/PRODUCTION_ROADMAP.md`

The original `docker-compose.yml`, private `.env`, `leadforge.db`, historical
migration revisions and unrelated worktree changes were not edited.

Implementation references: [Compose startup dependency conditions](https://docs.docker.com/compose/how-tos/startup-order),
[Nginx proxy routing](https://nginx.org/en/docs/http/ngx_http_proxy_module.html),
and [Uvicorn runtime settings](https://www.uvicorn.org/settings/).

## Step 5C configuration boundary

See [Configuration and secrets](CONFIGURATION.md) for strict environment selection,
explicit development dotenv opt-in, startup validation and the production matrix.
No `.env` is loaded automatically. Existing runtime Compose explicitly selects
`development`, mock AI and local HTTP cookies. It remains a local demonstration.

## Step 5D operational diagnostics

See [Observability](OBSERVABILITY.md) for JSON log fields, stable event names,
request IDs, stdout/stderr commands and reversible local failure diagnostics.
The image disables Uvicorn access logs; backend middleware owns completion
events. Nginx emits query-free access events and critical-only native errors.
Both runtime components remain non-root and read-only.
