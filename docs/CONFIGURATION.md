# Configuration and secrets — Step 5C

`backend/core/config.py::Settings` is the only application settings boundary.
Startup imports validate it before constructing the application or database engine.
This configuration contract does not establish production deployment readiness.

## Environment and precedence

`ENVIRONMENT` is required and case-sensitive: exactly `development`, `test`, or
`production`. Missing values, capitalization differences and typos fail closed.
There is no staging mode. Precedence is constructor values > process environment >
explicit development dotenv > defaults. `.env` is never loaded automatically.
Set `ENVIRONMENT=development` in the invoking shell and `LEADFORGE_ENV_FILE=.env`
to opt in. The file cannot select the environment. Test/production reject any
explicit dotenv source before reading it. Private existing env files were not read
or modified during 5C. `.env.example` is a safe development template, not a secret store.

Step 5H uses `ENVIRONMENT=production` with explicit `LEADFORGE_STAGING=true`
and `AI_PROVIDER=mock`. This opt-in permits only synthetic staging mock processing;
it does not relax database, HTTPS origin, Secure cookie, logging or rate-limit
validation. The flag rejects development/test and real providers. Production
mock processing remains refused without it. Settings truthfully labels it
Staging Mock. See [staging runbook](STAGING.md); no remote deployment is implied.

## Canonical matrix

Classes: **A** required secret (conditional where stated), **B** required production
non-secret, **C** optional non-secret, **D** development-only, **E** test-only,
**F** inactive future integration/provider. `No` means a safe default is available;
`selected` means required only when that provider is selected. All names are exact.
Secret examples describe formats, never usable credentials.

| Name / class | Purpose and consumer | Secret | Required dev / test / prod | Default / safe format and validation |
| --- | --- | --- | --- | --- |
| ENVIRONMENT / B | Settings, provider router, bootstrap, Settings API | No | Yes / Yes / Yes | No default; development, test, production only |
| DATABASE_URL / A | SQLAlchemy session and Alembic | Yes | No / fixture / Yes | Dev SQLite `sqlite:///./leadforge.db`; prod externally injected `postgresql+psycopg://USER:URL_ENCODED_PASSWORD@DB_HOST:5432/DB_NAME` |
| AI_PROVIDER / B | Router, workflow, Settings API | No | No / mock fixture / Yes | mock; exact mock, gemini, ollama; deepseek unavailable |
| LEADFORGE_STAGING / C | Explicit synthetic staging mock opt-in | No | No / No / staging only | false; true requires ENVIRONMENT=production and AI_PROVIDER=mock, all production validation retained |
| CORS_ORIGINS / B | CORS middleware and login Origin check | No | No / No / Yes | Dev localhost:5173 and 127.0.0.1:5173 HTTP; comma-separated origins; prod `https://app.example.com` |
| APP_NAME / C | FastAPI title/root | No | No / No / No | LeadForge Engine |
| VERSION / C | FastAPI metadata | No | No / No / No | 1.0.0 |
| AI_TIMEOUT_SECONDS / C | Workflow/providers | No | No / No / No | 20; integer 1–120 |
| AI_MAX_ATTEMPTS / C | Workflow | No | No / No / No | 2; integer 1–3 |
| GEMINI_API_KEY / A | Gemini adapter, safe configuration summary | Yes | selected / pure validation only / selected | Empty; nonempty when gemini selected; external injection only |
| GEMINI_MODEL / C | Gemini adapter | No | No / No / No | gemini-2.5-flash; nonempty when selected; connectivity unverified |
| OLLAMA_HOST / C,B when selected | Ollama adapter | No | No / No / selected | http://localhost:11434; selected URL must be HTTP(S), no credentials/path/query/fragment; prod explicit non-local host |
| OLLAMA_MODEL / C,B when selected | Ollama adapter | No | No / No / selected | llama3.1; selected nonempty; prod explicit |
| DEEPSEEK_API_KEY / F | Declared, no active consumer | Yes | No / No / No | Empty; retained inactive; DeepSeek selection rejected |
| HUBSPOT_ACCESS_TOKEN / F | Declared, no active consumer | Yes | No / No / No | Empty; retained inactive; CRM unavailable |
| LOG_LEVEL / C | Existing application logger | No | No / No / No | INFO; DEBUG, INFO, WARNING, ERROR, CRITICAL; production forbids DEBUG |
| SLOW_REQUEST_MS / C | HTTP completion warning threshold | No | No / No / No | 2000; integer 1?600000 milliseconds |
| RATE_LIMIT_ENABLED / C | Existing SlowAPI limiter | No | No / No / No | true; production false rejected |
| SESSION_COOKIE_NAME / C | Auth routes/dependencies | No | No / No / No | leadforge_session; HTTP token; must differ from CSRF cookie |
| CSRF_COOKIE_NAME / C | Auth routes/dependencies | No | No / No / No | leadforge_csrf; HTTP token |
| CSRF_HEADER_NAME / C | Auth dependencies/CORS | No | No / No / No | X-CSRF-Token; HTTP token; frontend public build setting must match |
| SESSION_TTL_SECONDS / C | Session service/cookie Max-Age | No | No / No / No | 604800; integer >=60 |
| SESSION_COOKIE_SECURE / C | Both auth cookies | No | No / No / No | true; false only development/test; prod true required |
| SESSION_COOKIE_SAMESITE / C | Both auth cookies | No | No / No / No | lax; lax or strict |
| LEADFORGE_ENV_FILE / D | Explicit settings loader | No | No / forbidden / forbidden | Unset; local file path only with external development selection |
| VITE_API_BASE_URL / C | Public frontend API wrapper | No | No / No / build | Dev http://localhost:8000; container build `/` means same-origin; no secret/credential-bearing URL |
| VITE_CSRF_COOKIE_NAME / C | Public frontend cookie lookup | No | No / No / No | leadforge_csrf; must match backend |
| VITE_CSRF_HEADER_NAME / C | Public frontend request header | No | No / No / No | X-CSRF-Token; must match backend |
| LEADFORGE_RUNTIME_DB_PASSWORD / A,D | Local Compose interpolation into PostgreSQL and shared backend/migrate URL | Yes | local runtime / No / not production Compose | Required externally; local URL-safe development placeholder only |
| LEADFORGE_RUNTIME_LOCAL / D | Synthetic container smoke guard | No | smoke only / No / forbidden use | Compose true; development/mock/disposable DB additionally checked |
| LEADFORGE_POSTGRES_ADMIN_URL / E | PostgreSQL test fixture | Yes | No / PG tests / forbidden use | Exact disposable localhost/127.0.0.1:55432 leadforge_dev identity; random test DB created/dropped |
| POSTGRES_USER / D | PostgreSQL image, Compose | No | runtime / No / separate deployment | Local leadforge_dev |
| POSTGRES_DB / D | PostgreSQL image, Compose | No | runtime / No / separate deployment | Local leadforge_dev |
| POSTGRES_PASSWORD / A,D | PostgreSQL image | Yes | runtime / No / separate deployment | Comes from externally injected local runtime password |

Docker image build controls `PYTHONDONTWRITEBYTECODE`, `PYTHONUNBUFFERED` and
`PIP_DISABLE_PIP_VERSION_CHECK` are non-secret build/runtime constants, not operator
application settings. Nginx uses Docker DNS, fixed internal backend:8000, and one
public local 8080 listener. Uvicorn has one worker, no reload, and no proxy-header
trust. There is no competing dotenv loader or session signing key.

## Production policy

Externally supply ENVIRONMENT, DATABASE_URL, AI_PROVIDER and CORS_ORIGINS.
Production requires PostgreSQL+psycopg with host/user/database/password, password
at least 16 characters, no known development placeholders, no leadforge_dev
user/database, and no loopback host. URL-encode reserved password characters;
Alembic escapes percent signs for ConfigParser and consumes the same canonical URL.
Production query parameters cannot override host/hostaddr/port/user/password/database
identity (TLS options such as sslmode remain supported).
These checks catch accidental development configuration; length is not proof of
credential entropy. PostgreSQL TLS/deployment policy remains a later deployment task.

Origins are trimmed, scheme/host lowercased, default ports and trailing slash removed,
deduplicated, and validated. Hostnames must be valid DNS names or IP addresses. No wildcard,
credentials, path, query or fragment. Production requires explicit HTTPS non-local
browser origins. Even same-origin login must use the external browser origin here.
Do not use internal Docker names as browser origins. Secure cookies require actual
HTTPS at the eventual public edge; 5C does not install TLS. Local 5B HTTP is explicitly
development with Secure=false. Session cookie remains HttpOnly; CSRF cookie remains
browser-readable; both path `/`, SameSite=lax/strict and TTL Max-Age. Secure-prefixed
cookie names require Secure=true. CSRF cannot be disabled by any configuration knob.
Sessions/CSRF use independent random opaque tokens and persisted SHA-256 hashes;
no configurable signing secret exists. Logout revokes sessions server-side.

Mock needs no provider credentials. Explicit production mock is accepted for offline
configuration dry runs; existing provider router still refuses mock processing in
production. Gemini requires its key/model; Ollama requires valid host/model and
explicit non-local production configuration. Validation makes no provider requests.
DeepSeek and HubSpot fields remain masked inactive placeholders, not implemented
integrations. Real-provider tests in 5C only construct Settings values; global running
application and all integration verification stay mock. Real connectivity belongs 5I.

## Injection and frontend boundary

Process environment is the sole production injection mechanism. Constructor values
are for tests. No `_FILE`, Docker secret mount or cloud secret-manager mechanism was
added: there is no current orchestrator requiring it. Compose secrets would require
an explicit mounted-file consumer; [Docker's secrets documentation](https://docs.docker.com/compose/how-tos/use-secrets/)
describes that alternative. Environment injection is adequate for this local milestone.
Authorized Docker/OS administrators can inspect runtime environment and process
memory. Redaction does not protect against those administrators. Never print
`docker compose config` with interpolated credentials; use `config --quiet`.

`deploy/compose.env` stays tracked and intentionally empty except comments. Always
pass `--env-file deploy/compose.env` to prevent Compose loading private `.env`.
The existing local Compose file is deliberately development-only; setting an external
ENVIRONMENT does not override its literal development selection. Do not call it a
production deployment. Both migration/backend share its one environment mapping.
Production operators must inject one identical complete URL into migration and backend.

Everything `VITE_*` is public, compiled into JavaScript. Only API base and CSRF names
are consumed. Container build pins API base `/` and excludes private env files; no
backend host or credential is required in browser assets. Never pass provider keys,
DB URLs or integration tokens to Vite, build args or static Nginx configuration.

`.gitignore` excludes env files, secret directories/private keys, databases and local
artifacts; `.dockerignore` excludes them plus Git/tests/docs/scripts. Explicit image
COPY lists further constrain contents. Do not store secrets in example files. Existing
local private env files were inspected only for ignore/tracking state. Git history is
never rewritten here; any credible historical credential requires rotation/remediation.

## Startup and redaction

Invalid configuration prevents app import, with key/category-only errors. SecretStr
masks credential-bearing DATABASE_URL/provider/integration secrets in repr/JSON.
Validation errors remove inputs, including `.errors()`; loader source failures do not
report source contents. Existing logging filters redact configured secret values,
encoded DB password forms and credential-bearing URL patterns. Exception logging
retains exception category while dropping driver messages/SQL parameters. Migration
SQLAlchemy failures become a fixed key/category error without chained driver output.
This is limited 5C leak prevention, not a new logging architecture. Health/readiness
retain 5B payloads; readiness catches DB failure and returns generic unavailable.

## Exact operator commands

Development without dotenv (does not migrate or write the original database):

```powershell
$env:ENVIRONMENT = 'development'
$env:AI_PROVIDER = 'mock'
$env:DATABASE_URL = 'sqlite:///./leadforge.db'
$env:SESSION_COOKIE_SECURE = 'false'
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Optional local dotenv: set ENVIRONMENT above, copy `.env.example` to an ignored
local `.env` if desired, then `$env:LEADFORGE_ENV_FILE = '.env'`. Shell values win.
Test command: `.\venv\Scripts\python.exe -m pytest tests -q`; fixture selects a
disposable SQLite DB, mock and development explicitly (bootstrap test needs that
mode); pure settings tests separately validate test mode. Do not combine PostgreSQL
and SQLite suites in one Python process.

Local production-asset runtime (documented placeholder is development-only):

```powershell
$env:LEADFORGE_RUNTIME_DB_PASSWORD = 'leadforge_dev_only'
docker compose --env-file deploy/compose.env -f compose.runtime.yml config --quiet
docker compose --env-file deploy/compose.env -f compose.runtime.yml build --no-cache
docker compose --env-file deploy/compose.env -f compose.runtime.yml up -d --wait
# http://127.0.0.1:8080
docker compose --env-file deploy/compose.env -f compose.runtime.yml down
```

Shutdown preserves the named volume. No `down -v` is needed for 5C.
Production configuration-only container dry run using injected placeholder formats
(the placeholder must be replaced by an externally supplied synthetic value):

```powershell
$env:ENVIRONMENT = 'production'
$env:AI_PROVIDER = 'mock'
$env:DATABASE_URL = 'postgresql+psycopg://USER:SYNTHETIC_PASSWORD_16_PLUS@db.example.com:5432/app'
$env:CORS_ORIGINS = 'https://app.example.com'
docker run --rm --read-only --tmpfs /tmp --network none -e ENVIRONMENT -e AI_PROVIDER -e DATABASE_URL -e CORS_ORIGINS leadforge-backend:5b-local python -c 'import backend.main'
```

This initializes without connecting to the DB or any provider, and is not a production
startup recipe. For an actual authorized runtime, apply this same external configuration
to `python -m alembic upgrade head` before the image's Uvicorn command; configure the
HTTPS edge and provider separately in later phases. Never put values on command-line
arguments: `-e NAME` forwards an already externally injected variable.

Troubleshooting: missing ENVIRONMENT means explicitly select a supported mode;
DATABASE_URL errors mean check driver, encoding, required parts and production policy;
origin errors mean use the public HTTPS origin, not a path; secure-cookie failures
mean fix production HTTPS expectations; provider errors mean supply only the selected
provider's requirements. Missing local Compose password fails interpolation before
startup. Migration failure leaves backend/frontend gated. Do not weaken validators
or print settings to diagnose credentials.

## Step 5D logging extension

See [Observability](OBSERVABILITY.md). Canonical JSON logging uses the existing
LOG_LEVEL and 5C redaction utility; SLOW_REQUEST_MS is the only new setting.
Safe stack locations now supplement exception categories without driver messages,
locals or source lines. Configuration validation and external injection stay intact.

## Render free staging adapter (Step 5H-A)

`TRUSTED_HOSTS` optionally adds exact DNS hostnames to transport Host validation,
independently of browser CORS origins. Comma-separated names are normalized and
validated; wildcard hosts, URLs, ports and credentials fail closed. Local defaults
remain empty. Render's server-only `RENDER_EXTERNAL_HOSTNAME` is added by
`deploy/render/runtime.py` before canonical Settings loads. This permits backend
health probes and direct transport tests without granting browser origins or
application authorization.

The Render adapter normalizes `postgres://` or `postgresql://` into the existing
`postgresql+psycopg://` driver contract, preserving encoded credentials and canonical
identity validation. Internal database transport requires TLS (`sslmode=require`)
because Render documents self-signed internal certificates. Operator external
transport requires `verify-full` and an explicit trusted CA file. No URL is logged.
See [Render staging](RENDER_STAGING.md) for the runtime/build/public/secret inventory.
ENVIRONMENT remains production with LEADFORGE_STAGING=true and mock AI; there is no
new environment mode, signing secret, dotenv source or automatic migration.
