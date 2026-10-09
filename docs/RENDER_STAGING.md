# Render Free staging preparation

Preparation only, October 8, 2026. No resource, account connection, billing action,
commit, push or remote deployment is performed by this milestone. Product baseline:
`8bef8ce1f2b47e2318806a56a6f2244d8b82fd03`, verified Quality run 37775894213.
The user selected deployment of the subsequently approved preparation commit after
its exact-SHA CI passes. Do not deploy the older SHA with paths absent from that tree.
LOCAL RELEASE CANDIDATE remains VERIFIED AND PUBLISHED for its defined local scope.

## Topology and limits

Browser HTTPS -> Free frontend/Nginx web service -> verified HTTPS -> Free backend
web service -> internal TLS -> Free PostgreSQL, all in Singapore. The browser uses
frontend-origin `/api`; it never receives the backend hostname as a Vite variable.
Both app services are public because Free services cannot receive private traffic.
Publicly routable does not mean publicly authorized: customer endpoints still need
valid opaque sessions, active organization membership, tenant ownership and CSRF.
The temporary backend URL is infrastructure, not the normal customer entry point.

Current official [Free limits](https://render.com/docs/free): services sleep after
15 idle minutes and cold starts take roughly a minute; 750 running instance hours
are shared monthly. No app disks, shell access, one-off jobs or scaling. Free Postgres
is one per workspace, 1 GB and expires after 30 days; no managed backups/pooling.
Do not create keep-alive traffic or run the 1,800-request local load campaign remotely.
Stop on usage/compute limits; no paid upgrade is authorized. Without a payment method,
usage exhaustion can suspend services/builds. If the account already has billing,
review hard spending controls before any later create action; selecting Free alone
must not be treated as a universal zero-overage guarantee.

[Singapore is currently available](https://render.com/docs/regions), suitable to
first evaluate from Bangladesh; actual regional availability must be checked during
creation without switching regions or paid plans automatically. Keep all three there.
Free web services are documented at 512 MB/0.1 CPU; Free PostgreSQL at 256 MB/0.1 CPU
in the [Blueprint specification](https://render.com/docs/blueprint-spec). These are
constraints, not proof of capacity. Argon2 uses 64 MiB per hash; synchronous analysis,
Python dependencies and connection limits need low-rate remote observation.

## Config files and manual first deployment

`render.yaml` explicitly describes two `type: web`, `runtime: docker`, `plan: free`
services and one `plan: free` PostgreSQL 16 database. Every service has
`autoDeployTrigger: 'off'`; no private service, disk, paid plan, cron, preview or
pre-deploy command exists. Never sync the Blueprint during preparation. First use
manual dashboard ordering to allow role provisioning/migration before app readiness,
and to obtain actual hostnames. The Blueprint is a reviewed declarative reference;
manual environments deliberately use a separately provisioned app-role URL rather
than giving the application the database-owner connection string.

Docker contexts are repository root `.` for both. Backend Dockerfile `./Dockerfile`,
command `python deploy/render/runtime.py start`; frontend `./frontend/Dockerfile`,
default command. Backend remains Python 3.12, UID 10001, one Uvicorn worker,
0.0.0.0:$PORT, no reload/access logs/proxy-header trust. Nginx remains UID 101 with
production assets, no Node runtime, 0.0.0.0:$PORT. Render supplies PORT=10000 by
default; the backend consumes that value, with 8000 only when PORT is absent for
local Compose. Valid unprivileged integers only. The image default CMD now selects
the strict Render adapter when RENDER=true or RENDER_EXTERNAL_HOSTNAME is present;
the explicit Blueprint command remains supported. Local frontend 8080/config and
backend 8000 fallback preserve Compose URLs. EXPOSE 8000 10000 documents both paths
and does not choose the listening port.
`.dockerignore` excludes private env, DBs, dumps, dependencies, Git, scripts, docs and
evidence. Explicit COPY packages only required adapter/shared seed code.

## Environment inventory

| Names / value policy | Class | Where / visibility |
| --- | --- | --- |
| ENVIRONMENT=production; LEADFORGE_STAGING=true; AI_PROVIDER=mock | SERVER CONFIG | Backend/operator; no real provider keys |
| DATABASE_URL | SECRET | Backend app-role INTERNAL URL; operator separate EXTERNAL owner/migrator/backup URLs; never bundle/log |
| CORS_ORIGINS=https://ACTUAL-FRONTEND.onrender.com | PUBLIC CONFIG | Backend exact browser origin only; obtain hostname before configuring |
| TRUSTED_HOSTS | SERVER CONFIG | Optional exact transport hosts, no wildcard; canonical settings merge the validated platform hostname |
| RENDER_EXTERNAL_HOSTNAME; PORT | RENDER-PROVIDED | Both runtime services; hostname is public, port server-only |
| LEADFORGE_RENDER=true | SERVER CONFIG | Frontend runtime switch only |
| LEADFORGE_RENDER_BACKEND_ORIGIN=https://ACTUAL-BACKEND.onrender.com | SERVER CONFIG | Nginx runtime only, never VITE; public infrastructure address, not credential |
| LEADFORGE_RENDER_DB_TLS=internal | SERVER CONFIG | Backend; operator explicitly external |
| LEADFORGE_RENDER_DB_CA | SERVER CONFIG | Operator trusted PEM CA path for verified external database connection |
| SESSION_COOKIE_SECURE=true; SESSION_COOKIE_SAMESITE=lax | SERVER CONFIG | Backend; cookies Secure, path /, host-only |
| SESSION_COOKIE_NAME=leadforge_session; CSRF_COOKIE_NAME=leadforge_csrf; CSRF_HEADER_NAME=X-CSRF-Token | PUBLIC CONFIG | Retain defaults; cookie names/header are browser visible |
| SESSION_TTL_SECONDS=604800; RATE_LIMIT_ENABLED=true; LOG_LEVEL=INFO; SLOW_REQUEST_MS=2000 | SERVER CONFIG | Existing defaults; DEBUG and disabled limiter prohibited |
| AI_TIMEOUT_SECONDS=20; AI_MAX_ATTEMPTS=2; APP_NAME; VERSION | SERVER CONFIG | Existing defaults; no operator override needed |
| VITE_API_BASE_URL=/; VITE_CSRF_COOKIE_NAME; VITE_CSRF_HEADER_NAME | PUBLIC CONFIG | Build only; default CSRF names, browser-visible; no backend URL/secret |
| LEADFORGE_RENDER_MIGRATOR_PASSWORD; LEADFORGE_RENDER_APP_PASSWORD; LEADFORGE_RENDER_BACKUP_PASSWORD; LEADFORGE_RENDER_QA_PASSWORD | GENERATED SECRET | Operator only; generate independently, keep out of app service except app DB URL |
| LEADFORGE_STAGE_PROVISION=true; LEADFORGE_STAGE_SEED=synthetic-only | SERVER CONFIG | Explicit operator actions only; never app startup |
| LEADFORGE_ENV_FILE, integration keys, local/CI fixture flags | OMIT | No private dotenv, real model credentials or remote SQLite |

No configurable session-signing or separate CSRF secret exists: the implementation
creates independent random 32-byte opaque session/CSRF tokens and stores hashes in
PostgreSQL. Generate role/QA passwords with Python `secrets.token_urlsafe(36)` in a
private operator process; never print/store them in source/chat. Prompt protected
values via Read-Host -AsSecureString and use process environment injection. Only
public configuration belongs in Blueprint values. Enter actual app credentials
through Render Environment settings; owner/migrator/backup credentials stay local.

## Proxy, TLS, cookies, CORS and headers

### October 9 host/port incident

The user supplied remote logs report port 8000 discovery/network restart followed
by HTTP 400 health probes until timeout. Before the hotfix, direct Docker CMD ignored
PORT and bypassed the adapter's hostname merge. An isolated production reproduction
returned `Invalid host.` from RequestSecurityMiddleware before `/ready` executed.
The Blueprint adapter already handled both correctly; the remote start-command/env
drift remains unverified. See [hotfix evidence](STEP_5H_B_HOST_PORT_HOTFIX.md).

[Render defaults PORT to 10000](https://render.com/docs/web-services) and can detect
alternate listeners, so 8000 explains the network reconfiguration but does not itself
explain HTTP 400. [HTTP probes use the service's onrender.com Host](https://render.com/docs/health-checks)
when no verified custom domain exists. Canonical settings now validate and include
the exact RENDER_EXTERNAL_HOSTNAME even for direct Uvicorn startup. Explicit
TRUSTED_HOSTS are preserved and deduplicated. URLs, paths, userinfo, whitespace,
wildcards and ports are rejected; no `*.onrender.com` trust exists. A verified custom
health-check domain must be explicitly included in TRUSTED_HOSTS. Forwarded Host
never grants trust. Unknown/sibling hosts still receive 400; an originless GET with
valid Host reaches `/ready` and still requires database access and matching heads.
CORS remains exact frontend origins, separate from Host validation.

Application startup still performs no migration. Readiness imports Alembic revisions
and may emit migration logger diagnostics. Explicit `alembic upgrade head` checks
stored revision and applies only missing migrations; retries at the required head
are no-ops. Repeated health restarts do not invoke it in the reviewed source. If an
operator has configured a remote startup migration command, inspect that command
and migration identity before retrying; the supplied logs do not prove it exists.
Free staging retains separate operator migration and role separation. A future
paid pre-deploy command remains a separately reviewed transition.

The frontend launch script validates PORT and exact HTTPS onrender.com upstream and
frontend hosts before substituting fixed placeholders. Hostnames do not exist yet;
none are hardcoded as final deployment addresses. DNS comes from /etc/resolv.conf,
not Docker's 127.0.0.11. Nginx preserves request URI, cookies, Origin, CSRF and selected
organization headers, uses backend Host for Render routing, SNI and CA/hostname
verification. TLS verification stays on. The proxy does not retry mutations and API
errors never become SPA HTML. Existing CSP retains connect-src self and scripts self;
no new browser backend connection or unsafe permission. HSTS max-age=86400 and
noindex headers are included; robots.txt disallows indexing and docs paths return 404.

Render terminates public TLS. Nginx overwrites forwarded scheme with https, replaces
X-Forwarded-For with its socket peer, and strips Forwarded/X-Forwarded-Host. Uvicorn
continues ignoring proxy headers. Secure cookies are explicit and no route uses the
forwarded scheme for redirects or authorization, so no redirect loop is introduced.
Client IP is the proxy peer, not a verified end-user address. The existing process-local
login budget is therefore conservative/shared, may be exhausted by direct backend
traffic and resets on restart. No distributed/per-client abuse protection is claimed;
keep staging temporary, synthetic and non-publicized. Do not trust arbitrary XFF.

Session cookies stay Secure, HttpOnly, SameSite=Lax, path /, no Domain. CSRF cookies
stay Secure and readable, with matching names/header. The proxy does not set a backend
cookie Domain. Direct backend login creates backend-host cookies, which never replace
frontend-host cookies. Exact frontend CORS/login Origin is accepted; backend origin
is not added merely for transport. Missing Origin is still permitted for non-browser
clients and never grants tenant access. Session-bound CSRF is still mandatory on writes.

For [database TLS](https://render.com/docs/postgresql-creating-connecting), internal
Render certificates are self-signed, so `sslmode=require` is the supported encryption
policy with no plaintext fallback; it does not authenticate the server certificate.
External operator connections use full hostname verification with a trusted CA PEM
file (for example the reviewed Debian CA bundle in the operator container). Do not
use resolved IPs, disable TLS, or silently downgrade verify-full on a failure. Record
actual server patch version and TLS status; PostgreSQL 16 compatibility must be proved.

## Provisioning, migration and bootstrap (later authorized execution)

Free services have no shell/one-off jobs; paid pre-deploy migrations are unavailable.
Use a protected local operator process against the EXTERNAL database URL, temporarily
allowlisting the operator IP. Initially select owner credentials for provisioning.
Inject all complete production/mock/origin settings as in the inventory, select
LEADFORGE_RENDER_DB_TLS=external and an existing CA trust file. No URL/password argv.

```powershell
# Variables above are supplied privately, not literal credentials.
$env:LEADFORGE_STAGE_PROVISION = 'true'
.venv-ci/Scripts/python.exe -B deploy/render/provision.py
# Select the separately provisioned migrator EXTERNAL URL privately.
.venv-ci/Scripts/python.exe -B deploy/render/runtime.py migrate
# Select owner EXTERNAL URL privately again; finalize app/backup grants.
.venv-ci/Scripts/python.exe -B deploy/render/provision.py finalize
# Select app-role EXTERNAL URL, strong private QA password, explicit seed guard.
$env:LEADFORGE_STAGE_SEED = 'synthetic-only'
.venv-ci/Scripts/python.exe -B deploy/render/runtime.py seed
```

Before the first migration confirm the selected database is exactly leadforge_stage
and fresh: no application tables/alembic_version. Provisioning uses one transaction,
creates only the three fixed non-superuser roles and their grants in that selected DB,
refuses existing/unexpected roles and never creates/deletes a database. Render's actual
owner CREATEROLE/schema privileges must be verified remotely: if unsupported, STOP;
do not deploy using owner credentials as an application workaround. Migrator owns
public schema, app has DML/sequence privileges without CREATE or Alembic writes, backup
has SELECT. Owner membership in migrator permits controlled administrative grants.
Run fresh base -> e5d4c3b2a1f0, finalize and audit privileges before app deployment.

Startup never runs migrations. `/health` is cheap liveness; `/ready` checks DB and exact
schema head and returns generic 503 for failures. Backend Render health path `/ready`.
Frontend Render health path `/frontend-health` proves only Nginx; using backend /ready
as its platform probe would couple frontend restarts to backend sleep/cold start.
Use frontend `/ready` as a separate bounded application validation gate instead.

On migration failure keep backend unready, inspect safe events/SQLSTATE and actual
version/privileges privately; correct the input or repository defect, rerun reviewed
migration only after inspecting current head. No create_all, historical migration
edits, automatic downgrade or startup-race migration. Do not mark deployment complete.

The existing staging seed is reused, with only its credential input factored into a
shared function. Explicit synthetic-only guard, production mock settings and externally
generated QA password remain required. It creates two separate synthetic users/tenants,
four leads and eight historical synthetic analyses; never runs on app startup and
refuses conflicting fixtures. No registration or default-tenant API is added. Store
returned IDs privately for validation and bootstrap account credentials separately.

## Direct backend and remote application validation

After deployment test actual backend URL: /health 200, /ready 200 only with schema,
/docs, /redoc and /openapi.json 404; unauthenticated customer paths 401. Authenticate
using synthetic accounts, then test missing/foreign organization 400/403, foreign
lead/intelligence/export 404, missing/mismatched CSRF 403, expired/revoked sessions 401,
unknown Host 400, oversized bodies 413, bad Origin 403 and bounded login 429. Health
must not reveal credentials, addresses, paths or exceptions. A spoofed Host is not
authorization; an attacker who can send a legitimate Host still faces all auth gates.

Use frontend HTTPS for normal browser checks: /, /leads, /imports, /ai, actual /ai/ID,
/reports, /settings and refresh; verify assets, no mixed content, CSP/CORS/cookie/page
failures. Verify login failure/success/logout/expiry, workspace selection/persistence,
foreign tenant denial, Dashboard counts, create/duplicate/filter/pagination/lifecycle,
non-mutating CSV preview and small confirmation, mock processing/persistence/current
analysis and prior success after failure, historical UTC Reports and honest Settings.
Safe test-side error interception may exercise fallback/reload without breaking data.
Use existing smoke logic with trusted public TLS, never the local CA/SPKI exception.

Supply a safe X-Request-ID and correlate one proxy and backend completion event;
inspect logs privately for absence of passwords, full URLs, cookies, auth headers,
raw bodies/contact strings and exception driver messages. Structured events are on
stdout/stderr, queries/path parameters are omitted. Native critical Nginx diagnostics
are a residual server-log boundary; do not put credentials in upstream URLs.

Measure one observed idle recovery, first warm request and low-rate warm p50/p95
for health, ready, session, list/detail/dashboard/report/intelligence. Frontend and
backend may sleep independently; a first browser request can exceed its 90-second
client timeout. Refresh/read saved results before retrying a mutation; do not change
budgets or create keep-alive loops. Observe memory, available CPU/restarts, database
storage and connections. No production SLA or 512 MB adequacy claim.

## Free backup, constrained restore and expiry

Existing `scripts/postgres_backup.py` requires an inspected local Docker PostgreSQL
container and exactly server 16.15. It cannot target a Render hostname as-is. Do not
claim that tool remotely passed or weaken its guards. Use the same custom logical
archive format with an explicit PostgreSQL 16 client, separately record actual remote
minor version and compatibility, and inject backup-role EXTERNAL connection settings.
Require verified TLS, pg_dump success, archive SHA256 and native pg_restore --list.
Write binary output using Python subprocess stdout to an exclusive file under ignored
`.staging-artifacts/5h-b/backup/`, never PowerShell text redirection. Use Docker's pinned
16.15 client with PGPASSWORD forwarded by NAME, PGSSLMODE=verify-full, PGSSLROOTCERT
pointing to its trusted CA bundle, PGHOST/PGDATABASE/PGUSER injected, PGCONNECT_TIMEOUT=5.
Capture stderr privately; report fixed failure categories and never credentials.

Native command inside that client: `pg_dump --format=custom --no-owner --no-acl --no-password`.
The following is an operator-only template for Step 5H-B, not executed by preparation.
Supply PGHOST, PGDATABASE=leadforge_stage, PGUSER=leadforge_stage_backup and PGPASSWORD
privately first; confirm the external hostname and current operator allowlist. Python
passes these variables by name and writes binary bytes without shell redirection:

```python
import hashlib, os, subprocess
from pathlib import Path
assert os.environ["PGDATABASE"] == "leadforge_stage"
assert os.environ["PGUSER"] == "leadforge_stage_backup"
assert os.environ["PGHOST"].endswith(".render.com")
assert os.environ.get("PGPASSWORD")
folder = Path(".staging-artifacts/5h-b/backup")
folder.mkdir(parents=True, exist_ok=False)
archive = folder / "render-staging.dump"
client = ["docker", "run", "--rm", "-e", "PGHOST", "-e", "PGDATABASE",
          "-e", "PGUSER", "-e", "PGPASSWORD", "-e", "PGSSLMODE=verify-full",
          "-e", "PGSSLROOTCERT=/etc/ssl/certs/ca-certificates.crt",
          "-e", "PGCONNECT_TIMEOUT=5", "postgres:16.15"]
with archive.open("xb") as output:
    result = subprocess.run([*client, "pg_dump", "--format=custom", "--no-owner",
                             "--no-acl", "--no-password"], stdout=output,
                            stderr=subprocess.PIPE, timeout=300)
if result.returncode:
    raise RuntimeError("Remote backup failed; archive is incomplete, inspect privately")
with archive.open("rb") as source:
    result = subprocess.run(["docker", "run", "--rm", "-i", "--network=none",
                             "postgres:16.15", "pg_restore", "--list"],
                            stdin=source, capture_output=True, timeout=60)
if result.returncode:
    raise RuntimeError("Archive inspection failed")
(folder / "archive.sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+"\n")
# Inspect the captured TOC privately, then build the evidence manifest below.
```

An unexpected hostname/client trust store or remote server major/minor needs review;
never bypass verification. Restrict the folder's Windows ACL to the operator before
writing it. Incomplete archives are not backups and cannot be used for restore.
Inspect offline using `pg_restore --list`; record SHA256, table counts, revision, known
synthetic relationships, constraint inventory and latest successful analysis IDs in
a separate private manifest. Compression is not encryption; restrict ACLs and encrypt
retained artifacts using a separately protected key before off-host retention. No
remote backup schedule/upload is installed, and no managed recovery is assumed.

Only one Free database can be active. Never overwrite it for a restore drill. Restore
the verified archive into a uniquely owned EMPTY local PostgreSQL 16 target, using
`pg_restore --single-transaction --exit-on-error --no-owner --no-acl --no-password`.
Compare logical rows/relationships/constraints/sequences/current analyses, revoke all
restored sessions while fenced, then run the isolated app with mock AI and verify old
cookie denial/fresh login. This proves remote-data portability to a local target;
it does NOT prove a fresh-target restore on Render. Full remote recovery remains an
explicit limitation until a separately authorized suitable target exists. Never use
SQLite, leadforge.db, the development DB or retained Kubernetes PVC as restore targets.

Record creation/expiry dates when resources exist. Review by day 20 and take a verified
backup before day 25; choose separately authorized paid upgrade/migration or stop with
retained backup before day 30. Do not rely on the grace period: expired DB is inaccessible.
No actual expiry date can be stated before creation.

## Failure, restart, rollback and paid transition

Build failure: keep previous artifacts, inspect safe build stage/config, do not update
dependencies blindly. Wrong env/startup: fail closed, correct secret/origin/port settings
privately. Upstream loss: static health stays available, /api and /ready fail with
502/503; no retry mutation or HTML fallback. DB outage: /health remains liveness,
/ready 503; inspect dependency without exposing driver errors. After independent
frontend/backend restarts or exact-SHA redeploy, compare synthetic row fingerprints,
sessions and required head. Distinguish idle spin-down from a crash.

Render currently documents Free rollback to the two recent prior deployments; safest
controlled path is Manual Deploy > Deploy a specific commit, recording actual SHA and
configuration. Auto-deploy remains OFF. Roll back only to an app/config compatible with
the DB head; never downgrade schema. Baseline 8bef8ce does NOT contain Render adapters;
returning to it requires an explicitly reviewed external adapter/config or prior
compatible deployment image. The first known-good Render preparation SHA after CI is
the initial usable rollback target. [Deployment behavior](https://render.com/docs/deploys).

Future paid target: public frontend -> private backend -> paid PostgreSQL, validated
separately. Change proxy upstream/scheme and host/DNS config to the private service,
keep browser API/CSP/cookies unchanged, remove backend public route, assess trusted
internal TLS/network boundaries, add paid pre-deploy migration with separated identity,
continuous monitoring, backup/PITR and appropriate compute. The current free adapter
intentionally only permits public HTTPS onrender upstreams, so private-host transition
requires a small reviewed deployment-config change, not a business-logic rewrite.
PostgreSQL data model stays unchanged; connection/roles/grants and restore compatibility
must be checked, not assumed. No paid transition is authorized now.

| Boundary | Local Kubernetes | Render Free | Future paid target |
| --- | --- | --- | --- |
| Backend | ClusterIP/private | Public HTTPS, app authorization required | Private service, app authorization still required |
| Database | Retained local PVC, separated roles | Temporary managed DB, app-role internal TLS | Paid persistent DB, separated roles/recovery |
| Availability | Local developer-controlled | Sleep/restarts/expiry/shared quotas | Plan-dependent; remote gates required |
| Backups | Verified local fresh-target drill | External logical archive + local restore; remote target unverified | Authorized managed + off-host + fresh-target validation |
| Container controls | Restricted pods, read-only roots/caps | Non-root images; platform controls differ | Reassess platform isolation and resource guarantees |

## Dashboard inputs and exact Step 5H-B order

Private GitHub repo `deyprantobivash0-creator/LeadForge-Engine`; connect via Render's
GitHub integration and grant only this repository; never paste PATs. Branch main,
actual approved preparation SHA after exact CI, Docker contexts `.`, names
leadforge-staging-postgres/backend/frontend, region Singapore, ALL plans Free.
Database name leadforge_stage, owner leadforge_stage_owner, major 16, 1 GB, no HA/pooling.
Backend health /ready, command above; frontend /frontend-health. Environment names are
in the inventory. Actual frontend/backend hostnames and app-role internal DB URL are
pending service creation; never guess them. Manual creation can immediately trigger an
initial build/deploy; no approval to create should be treated as read-only action.

1. After explicit deployment authorization, verify approved prep SHA/CI and dashboard
   Free/usage controls; connect GitHub narrowly. Check no existing Free DB collision.
2. Create Free PostgreSQL 16 in Singapore; record expiry; restrict external access to
   the operator IP for controlled work, do not use default open external access.
3. Create Free backend with auto-deploy OFF and reviewed Docker inputs. Record actual
   hostname. An initial attempt may stay unready until origins/schema are configured.
4. Reserve/create frontend Free service with auto-deploy OFF to obtain its actual URL;
   it may remain unready until upstream env exists. No fabricated hostname placeholder
   is used as an authorized browser origin.
5. Inject exact frontend CORS origin and app-role INTERNAL URL for backend; actual
   backend HTTPS origin for frontend. Provider stays mock, Secure cookies true.
6. Using protected owner EXTERNAL URL/CA/IP allowlist, provision roles; migrate fresh
   schema with migrator; finalize/audit grants; seed with app identity/strong private QA.
7. Manual-deploy the exact approved preparation SHA to backend; require /ready/schema,
   direct protected-route/docs/Host/privacy negatives. Do not bypass a role failure.
8. Configure/deploy frontend same SHA; require Nginx health and separate proxied /ready,
   verified public TLS, no frontend secret/backend URL in assets.
9. Execute small synthetic application smoke and browser route/auth/CSRF/tenant gates.
10. Verify mock processing/persistence and historical intelligence/report semantics.
11. Record cold/warm latency/resource/connection observations at low rate only.
12. Restart/redeploy services individually with same SHA; compare data/session/head.
13. Produce/inspect/checksum external logical backup; test constrained local fresh-target
    restore and accurately record remote restore limitation; tighten DB external access.
14. Record actual SHAs, URLs, region, Free tiers, health/privileges, privacy, expiry and
    unresolved limitations; remote Step 5H completion requires all agreed remote gates.

Do not perform this sequence during 5H-A. Authoritative references:
[Free](https://render.com/docs/free), [Blueprint](https://render.com/docs/blueprint-spec),
[Docker](https://render.com/docs/docker), [ports](https://render.com/docs/web-services),
[health](https://render.com/docs/health-checks), [database/TLS](https://render.com/docs/postgresql-creating-connecting),
[secret configuration](https://render.com/docs/configure-environment-variables),
[private GitHub](https://render.com/docs/github).
