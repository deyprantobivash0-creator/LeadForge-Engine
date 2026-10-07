# Security contract

Step 5E covers the registered first-party application, its local single-instance
runtime, dependencies and images. It is not a production release approval.
The repository and verified runtime behavior are the source of truth.

## Threat model and trust boundaries

| Asset/boundary | Attacker and threat | Controls and limits |
| --- | --- | --- |
| Browser to Nginx | Unauthenticated caller, stolen credentials, hostile Origin/Host, large bodies, XSS | Bounded login and bodies; server session authorization; CSRF; CSP; explicit CORS; backend Host validation; loopback-only published port. |
| Session to workspace | Authenticated customer substitutes another organization's ID, lead ID, analysis ID, or import token | Active membership derived from the session; organization predicates in repositories; session/user/organization/file-bound preview signatures; no client-selected ownership fields. |
| CSV and JSON to services | Overposting, malformed CSV, resource exhaustion, SQL/formula injection | Explicit schemas and bounds; operation transactions; bound SQL parameters; inert CSV export; preview does not write. |
| Backend to database | Compromised app credential or container | Internal network; no published DB port; read-only non-root app. Local fixture role is a superuser: see privilege limits below. |
| Configuration/build/logs | Credential leakage through assets, images, exceptions, request logs or history | Explicit canonical settings, no implicit dotenv; image context exclusions; SecretStr and redaction; event-field allowlist; local secret scans. Docker administrators remain trusted. |
| Dependencies | Vulnerable transitive library or OS package | Patch constraints, npm lock, digest-pinned bases, OS security updates, final scans and explicit reachability review. |

Priorities are tenant data disclosure, session theft/CSRF, credential guessing,
untrusted-input resource exhaustion and exploitable dependency vulnerabilities.
An operator with Docker/host/DB administrative access is inside the trust boundary.
Distributed attackers, compromised endpoints, denial of service at transport level,
backup recovery and full production infrastructure are not proven by these checks.

## Authentication and sessions

Passwords use Argon2id: 64 MiB memory, three iterations, parallelism four,
16-byte random salt and 32-byte hash. Login retains compatibility with existing
passwords: 1–1024 characters, email at most 254. No password reset, registration,
change-password or account-lockout workflow is added. Successful login upgrades
older hash parameters in the same commit as issuance. Failed/unknown/inactive
accounts share a generic 401; unknown accounts perform a dummy hash verification.
This reduces enumeration, without claiming perfect constant-time HTTP behavior.

Session and CSRF identifiers are independently generated from 32 random bytes;
only SHA-256 digests are stored. Login always issues fresh identifiers and ignores
caller-provided session IDs. The default absolute expiry is seven days, with no
sliding extension. Logout revokes the current session server-side and clears both
cookies; expired/revoked sessions and disabled users fail. Old independent sessions
remain valid until their own expiry/revocation. Session cleanup and account-wide
revocation remain future account operations.

Cookies are host-only with path `/`, SameSite Lax (or Strict), Max-Age matching
expiry; session is HttpOnly, CSRF cookie is browser-readable. Production enforces
Secure. The explicit local HTTP runtime uses Secure=false. Credentials and session
IDs are absent from localStorage/sessionStorage; localStorage holds only a per-user
workspace preference that the server reauthorizes. Do not put tokens in URLs.

Every authenticated write requires the current session's CSRF header and cookie:
lead create/lifecycle/process, import preview/confirm and logout. Both must hash to
the session's CSRF digest, preventing cross-session substitution. Login validates
an Origin when supplied; missing Origin is allowed for non-browser clients. CSRF
and Origin checks supplement authorization rather than grant workspace access.

## Abuse and input limits

Login allows ten attempts per 60-second window per socket-peer hash bucket.
Storage is exactly 1024 buckets under a lock, uses monotonic time, expires without
timers and returns 429 with Retry-After. Hash collisions conservatively share a
budget. It is process-local and resets on restart. Uvicorn ignores proxy headers;
Nginx overwrites X-Forwarded-For/Proto and strips Forwarded/X-Forwarded-Host.
Thus all clients through the current Nginx share a backend budget. This is a
deliberate conservative local-runtime limitation, not a distributed account
lockout or scalable per-client protection. A deployment must choose an explicit
trusted proxy/per-client edge budget before expanding traffic; never key on an
arbitrary forwarded header. Repeated invalid sessions/CSRF have cheap bounded
token verification and privacy-safe 401/403 events; no global API throttle is added.

Nginx and the direct backend enforce 2 MiB request bodies, including streams with
no Content-Length. CSV retains its narrower 1 MiB, 1000-row, 100-preview-row bounds,
strict UTF-8/CSV parsing and field bounds. NUL bytes are rejected before DB writes.
Company/source/email and lifecycle notes are bounded; extra write fields are
forbidden. Lead IDs are positive signed 64-bit values. Page size is at most 100,
page at most 1,000,000 and history offset at
most 100,000,000. Reports have allowlisted presets and at most 365-day custom ranges.
Large valid datasets still need later performance/capacity work.

CSV never supplies file paths, commands or executable code. Exports use csv.writer
quoting plus an apostrophe for formula prefixes after whitespace/control bytes and
leading tab/CR/LF. This mitigation is tested for common spreadsheet import behavior;
an operator removing the apostrophe can reactivate a formula. React renders data
as text; no raw HTML rendering or client-supplied redirect destination exists in
the registered UI. SQLAlchemy binds values; sorting/grouping identifiers are fixed
ORM expressions. Readiness SQL is constant. Legacy manual scripts are unregistered
and are not production entrypoints.

## HTTP and browser policy

Nginx sends CSP on SPA/assets/API/errors: default/script/font/connect self;
style self plus unsafe-inline for existing React style attributes; images self/data;
object none; base/form self; frame-ancestors none. Scripts have no unsafe-inline or
unsafe-eval permission. CSP complements escaped rendering and requires a browser
smoke whenever asset/UI changes are made. It is not enabled on development Swagger
HTML at the direct backend. Production disables docs, Redoc and OpenAPI entirely
through the canonical ENVIRONMENT setting.

Both API and Nginx responses have nosniff, frame DENY, explicit referrer policy and
disabled camera/microphone/geolocation. No HSTS is emitted on local HTTP; the future
TLS ingress must define HSTS only after HTTPS and domain ownership are verified.
Every `/api/` response, including errors, has no-store; SPA has no-cache; content-
hashed assets remain publicly immutable. Nginx header snippets are included at every
location with add_header because Nginx does not inherit parent headers there.

Credentialed CORS uses validated explicit origins, never wildcard. The backend
accepts Host names derived from canonical CORS origins plus internal loopback probes;
`testserver` is non-production only. Invalid/duplicate authorities fail closed.
Nginx serves public static assets independent of Host, but proxies customer APIs to
this validation boundary. External deployment must route only its registered public
domains. CORS permits implemented GET/POST/PATCH; unknown routes/methods fail. Nginx
rejects other verbs except HEAD and preflight OPTIONS. Error responses omit SQL,
credentials and exception details. Request logs omit bodies, query values and headers.

## Containers and database privilege

Backend/migration UID 10001 and Nginx UID 101 run read-only, with bounded tmpfs,
all capabilities dropped and no-new-privileges. No socket, privileged container or
development bind mount is present. Only frontend 127.0.0.1:8080 is published.
PostgreSQL's official entrypoint initializes as root, then the server runs UID 999;
its root filesystem is read-only, with a writable data volume and bounded tmpfs
for temporary files/socket. It drops all capabilities and restores only CHOWN,
DAC_OVERRIDE, FOWNER, SETGID and SETUID for initialization, with no-new-privileges.
Its official initialization privileges
are distinct from the non-root application policy.

The synthetic local `leadforge_dev` role has superuser/create-db/create-role/
replication privileges from the official image. It is excessive for application
traffic and must not be used in production; 5C already rejects that identity.
This step preserves the existing local fixture/migration volume and documents the
deployment requirement rather than silently changing its administrator identity.
Production must have an administrative provisioning identity, a schema-owning
migration identity and an application LOGIN role with NOSUPERUSER NOCREATEDB
NOCREATEROLE NOREPLICATION, database CONNECT, schema USAGE, table SELECT/INSERT/
UPDATE/DELETE and required sequence USAGE. Set matching default privileges for
future migrations; runtime must not have schema CREATE/DDL or owner membership.
Verify these grants with that runtime identity before deployment. The current local
demo does not prove those production grants or encrypted DB transport.

Base images are version/digest pinned. Security package upgrades use their current
distribution repositories at build time; resulting image IDs, not merely the base
digest, identify verified artifacts. This is not a fully reproducible OS package
lock. PostgreSQL stays on major/version 16.15 and its existing volume.

## Dependency, secret and operator policy

Use pip-audit, npm audit and a local image scanner after dependency/image changes.
Patch applicable high/critical findings; do not use force/major upgrades to silence
reports. Record original severity, package, fix availability and runtime reachability
for every residual high/critical finding. No-fix is not an automatic exemption.
Reassess classifications if providers, parsing features, modules or exposure change.

Keep private dotenv files unread and excluded from builds/source staging. Scan
non-private source and Git history locally with redacted reports. A real credential
finding requires rotation and an explicit incident disposition; deleting current
text is insufficient, and history rewriting is not authorized here. Never publish
scan matches or raw environment dumps. The migration revision constant flagged by
Gitleaks is an individually reviewed false positive, not a blanket rule exclusion.
Logging/image/asset sentinel checks supplement detection; scanners cannot prove
that all possible credential formats are absent.

For 429, honor Retry-After and inspect correlated status/count events rather than
logging credentials or disabling protection. For 400 Host, verify registered CORS
origin and actual browser authority. For 403, check active membership and CSRF from
the same current session. For CSP errors, inspect the blocked directive/resource;
do not broadly enable script unsafe-inline/eval. For readiness/migration failures,
use safe categories and fix configuration/dependency before restarting. Share
security reports privately with repository operators using identifiers and safe
reproduction steps; no automatic third-party messages are sent.

CI, backups/recovery, staging/TLS, real AI, capacity/load tests, release approval and
first-client readiness remain later phases. Stop after 5E.
