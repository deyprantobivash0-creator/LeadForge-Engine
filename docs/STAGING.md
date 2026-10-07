# Staging deployment

Step 5H is **prepared for deployment authorization**, not remotely complete.
No provider, VM, cloud account, hostname or DNS authorization has been supplied.
No paid resources, registry push, Git push or remote changes were made. See
[verification report](STEP_5H_VERIFICATION.md) for the exact local evidence and
pending remote checks. Stop after 5H; this is not production deployment.

## Model and authorization

Use one dedicated Linux VM/VPS with Docker Compose, building the existing images
on that host from an explicit verified source archive. Provider remains unselected:
use an existing authorized VM or obtain approval for a specific provider, region,
size and recurring price first. A provisional starting size is 2 vCPU/4 GiB RAM/
40 GiB disk, subject to image-build and restore-capacity measurement. No price or
resource purchase is implied. No Kubernetes, Terraform, registry or remote green
CI pipeline is required. Remote 5F CI remains pending.

```text
Internet :80 -> canonical-host HTTPS redirect
Internet :443 -> Nginx TLS + production frontend -> same-origin /api
                                                -> FastAPI :8000 (private)
                                                -> PostgreSQL 16.15 (private)
```

`compose.staging.yml` is a separate project, never merged with local runtime
Compose. It reuses the existing Dockerfiles, proxy renderer and header policy.
A separate file avoids inheriting local development credentials, insecure cookies,
port bindings, project name or database volume. Frontend joins edge/runtime;
backend, database and one-shot utilities use only an internal network. No backend,
PostgreSQL or Docker daemon port is published. SSH is administrative access only.
This single VM is not HA; host loss needs a replacement plus trusted DB backup,
source archive/config and secret/key recovery. Brief deployment downtime is expected.

Authorization section 89 of the user's Step 5H request requires stopping before
unapproved account access, resource creation, DNS modification, Git/registry push.
Provide the chosen target/access method and hostname, approve the quoted costs
if new resources are needed, and authorize the specific remote/DNS actions. All
remote execution below is a procedure for that later authorized action.

## Host baseline and hostname

Use a supported Linux distribution such as Ubuntu 24.04 LTS. Follow the
[official Docker installation](https://docs.docker.com/engine/install/ubuntu/)
with Engine/Compose plugin, Python 3.12, supported security updates and controlled
reboot windows. Deploy as a named non-root operator using SSH keys; restrict SSH
to intended admin IPs, disable password SSH/root login after confirming alternate
access. Docker membership is root-equivalent, not an unprivileged boundary.
Do not expose the Docker TCP API. Verify Docker starts at boot.

Provider firewall/security group: allow 80/443, SSH only from admin IPs; deny
5432/8000/2375/2376. Verify from another machine. Docker published ports can bypass
ordinary UFW rules; use provider rules and the appropriate Docker filtering chain,
as described by [Docker firewall guidance](https://docs.docker.com/engine/network/packet-filtering-firewalls/).
No host firewall changes or reboot were performed here.

Choose one real staging DNS name you control; no committed fake deployment domain.
Approve any A/AAAA record modifications first; publish IPv6 only if actually served.
A provider-issued HTTPS name is acceptable only when it can route this deployment
and supply a trusted certificate under the intended proxy boundary. This VM plan
terminates TLS directly in Nginx; an additional CDN/provider proxy needs a separate
review rather than blindly trusting its headers.

## Source identity and transfer

For the Step 5H-A release, [release preparation](RELEASE_PREP.md) supersedes
the dirty-tree transfer procedure below: obtain separate commit and push approvals,
then require the remote Quality workflow's aggregate gate for that exact commit.
Deploy only a clean checkout or `git archive` of that same verified SHA. The earlier
5H source archive remains historical local evidence and must not be reused as the
new release identity. Post-commit evidence edits are outside that verified release.
Provider, hostname, access, DNS/cost and remote deployment approvals still apply.

The repository has substantial legitimate uncommitted work. Git HEAD alone does
not represent the application being deployed. `scripts/staging.py snapshot`
creates a source archive and per-file SHA-256 manifest, plus an aggregate digest,
Git HEAD, dirty flag, UTC time and archive SHA. It includes allowlisted build,
application, migration, frontend, deployment, test and documentation sources.
Private dotenv, secrets, DB/dumps, node_modules, dist, caches and generated
artifacts are excluded. The 5H evidence report is excluded because it records
the digest itself and is not a build/runtime input. Non-source originals stay local.
The archive contents are rehashed against the manifest before completion. A
snapshot failure is nonzero; discard its incomplete output, never deploy it.

Local PowerShell (Git must be in PATH):

```powershell
& .venv-ci/Scripts/python.exe -B scripts/staging.py snapshot --output-dir .staging-artifacts/release-5h
if ($LASTEXITCODE -ne 0) { throw 'Source snapshot failed' }
```

Run dependency/source-secret gates before packaging, verify the reviewed manifest
contains only intended files, then transfer **only** `source.tar.gz` and
`manifest.json` to the approved VM via authenticated SSH/SCP. No automatic push or
transfer is performed by the helper. Never upload the repository wholesale.
Checksum is an integrity check, not adversarial authenticity; obtain the expected
SHA through your trusted administrative channel.

On the host, use a new release directory (do not extract over unknown files):

```sh
python3 - <<'PY'
import hashlib,json,pathlib
m=json.loads(pathlib.Path('manifest.json').read_text())
assert hashlib.sha256(pathlib.Path('source.tar.gz').read_bytes()).hexdigest()==m['archive_sha256']
print(m['release'])
PY
mkdir '<new-release-directory>'
tar -xzf source.tar.gz -C '<new-release-directory>'
cd '<new-release-directory>'
export LEADFORGE_STAGE_RELEASE='<release-value-from-manifest>'
export LEADFORGE_STAGE_HOST='<real-staging-hostname>'
export LEADFORGE_STAGE_PRIVATE_DIR='/opt/leadforge-staging/private'
```

Only extract the trusted helper-generated archive; do not extract arbitrary
untrusted archives. Retain manifest, previous release/config and image IDs for
rollback. Repeat packaging if build/runtime inputs change; do not label a changed
tree using a stale release digest. No commit is made by this workflow.

## Secrets, strict configuration and roles

```sh
umask 077
python3 -B scripts/staging.py prepare --hostname "$LEADFORGE_STAGE_HOST" --private-dir "$LEADFORGE_STAGE_PRIVATE_DIR"
```

The helper generates independent random admin/migrator/app/backup/QA passwords
only when their files are absent. It never prints them or rotates an initialized
database accidentally. LF encoding is explicit for portability. The private
parent must remain operator-owned 0700. File-backed Compose secrets are read by
non-root container users; files use 0444 inside the protected parent. On Windows,
POSIX mode is not an ACL guarantee: restrict the directory's actual NTFS ACL.
Verify real host/container access rather than assuming file mode emulation.
Do not commit these files, use real production credentials, pass values in argv,
render secret-bearing environments or enable shell tracing. Docker/host admins
remain trusted. Credential rotation requires coordinated ALTER ROLE + secret
update + restart; `prepare` is deliberately not a rotation tool.

The wrapper reads only its scoped secret, URL-encodes it, injects DATABASE_URL,
then executes the canonical entrypoint. Staging uses ENVIRONMENT=production,
LEADFORGE_STAGING=true, AI_PROVIDER=mock, one explicit HTTPS CORS origin,
SESSION_COOKIE_SECURE=true, INFO logs, active rate limiting and fingerprint VERSION.
No provider/API/CRM/email secret is installed. The staging flag permits mock
processing under strict production configuration only; it rejects other modes
and real providers. Without the flag, production mock processing still fails.
No session signing secret exists in this server-side opaque-session design;
session/CSRF randomness is generated per login and only digests are persisted.

| Identity | Privileges and lifecycle |
| --- | --- |
| leadforge_stage_admin | Dedicated cluster administrator for initialization/provisioning; secret only mounted in PostgreSQL/provision utility. Never application identity. |
| leadforge_stage_migrator | Non-superuser DB/public-schema owner, DDL for Alembic; no create-role/create-db/replication/bypass-RLS. Secret only migration service. |
| leadforge_stage_app | Non-superuser business-table SELECT/INSERT/UPDATE/DELETE, sequence USAGE/SELECT, DB CONNECT/schema USAGE; no schema CREATE or role administration. Alembic table is SELECT-only after migration. |
| leadforge_stage_backup | Non-superuser SELECT tables/sequences, DB CONNECT/schema USAGE; no customer mutations. Used by existing 5G CLI. |

Provisioning creates only roles/database and grants, not application tables.
Existing unexpected elevated roles or wrong database owner are rejected. Default
grants cover future migrator-created objects; post-migration reconciliation removes
app write privileges from alembic_version. A matching empty UTF8 DB is migrated
through the unchanged historical Alembic chain to e5d4c3b2a1f0. PostgreSQL TCP uses
SCRAM on the private same-host network; no managed DB or remote plaintext DB path
is introduced. Managed PostgreSQL adaptation must explicitly validate DB TLS.

## Trusted TLS and exact deployment

Supply a real trusted certificate for the canonical hostname. Local rehearsal's
self-signed test CA is **not** final staging TLS. Nginx uses TLS1.2/1.3, no session
tickets, strict canonical Host and HTTP308 to the fixed HTTPS name. See
[Nginx HTTPS documentation](https://nginx.org/en/docs/http/configuring_https_servers.html).
HSTS is one day, no includeSubDomains/preload; it applies only to staging HTTPS.
Production HSTS expansion needs separate domain ownership/HTTPS policy review.

One possible certificate workflow, after DNS/host authorization and installing
Certbot per its [official guide](https://eff-certbot.readthedocs.io/en/stable/using.html):

```sh
# Initial certificate: port 80 must be free/reachable. Approval covers CA/DNS actions.
sudo certbot certonly --standalone --cert-name "$LEADFORGE_STAGE_HOST" -d "$LEADFORGE_STAGE_HOST" --email '<operator-email>' --agree-tos
sudo install -m 0444 -o '<deployment-user>' -g '<deployment-group>' "/etc/letsencrypt/live/$LEADFORGE_STAGE_HOST/fullchain.pem" "$LEADFORGE_STAGE_PRIVATE_DIR/fullchain.pem"
sudo install -m 0444 -o '<deployment-user>' -g '<deployment-group>' "/etc/letsencrypt/live/$LEADFORGE_STAGE_HOST/privkey.pem" "$LEADFORGE_STAGE_PRIVATE_DIR/privkey.pem"
```

Certificate files remain outside the source, images and web root. Track expiration;
renew before expiry, recopy the chain/key and recreate frontend to refresh bind
mounts. Standalone renewal temporarily needs frontend stopped to free port 80;
this is brief staging downtime, not zero downtime. Test `certbot renew --dry-run`
and the approved renewal/recreation process remotely. No renewal timer/hook was
installed locally or on any remote host in 5H preparation.

Exact deployment commands from the approved release directory:

```sh
# --env-file /dev/null prevents accidental implicit private .env loading.
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging config --quiet
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging build
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging up -d --wait --wait-timeout 180
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging images
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging ps -a
```

`postgres healthy -> provision successful -> migrate successful -> backend ready
-> frontend`. One-shot failures stop dependent startup, according to
[Compose dependency semantics](https://docs.docker.com/compose/how-tos/startup-order).
Long-running services restart unless-stopped; one-shot utilities never loop.
Docker daemon restart does not itself reapply Compose dependency ordering, so an
existing stack may briefly be unready until DB recovers. After host reboot prove
readiness and persistence; after image/schema changes use the full deployment
gate, not a bare backend restart.

Images are built on-host and tagged by source digest. No registry is necessary.
Record actual image IDs/versions after building; OS update steps mean a later
build from the same source can have different package/image IDs. Retain previous
images; don't prune them during verification. No claim that source hashing alone
is bit-for-bit image reproducibility. Docker construction recipes are unchanged.

## Synthetic seed, external validation and logs

Manual seed, only in this staging project:

```sh
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging --profile qa run --rm seed > '<private-fixture-manifest.json>'
```

The JSON has only synthetic email/org/Lead IDs; no passwords. It seeds two labeled
organizations, independent users/memberships, four representative Leads and eight
historical analyses with Unicode and timestamp/ID tie ordering. QA password stays
in the private file; no customer contents copied. Repeated seed checks existing
fixture identity/password/membership and refuses unexpected partial fixtures.
It is not automatic startup registration. Synthetic QA data may remain for review.

From an external machine, use a separately protected QA password file, never argv:

```sh
python3 -B scripts/staging.py health --hostname '<real-staging-hostname>'
python3 -B scripts/staging_smoke.py --hostname '<real-staging-hostname>' --fixture-manifest '<private-fixture-manifest.json>' --password-file '<private-qa-password-file>'
curl --fail --silent --show-error "https://<real-staging-hostname>/health"
curl --fail --silent --show-error "https://<real-staging-hostname>/ready"
curl --head --silent --show-error "https://<real-staging-hostname>/"
```

Never disable certificate validation for final staging. Smoke covers Secure/
HttpOnly/session/CSRF, CORS, wrong Origin, tenant Lead/Intelligence/export denials,
Dashboard, Leads, non-mutating CSV preview/import/duplicates/export, mock processing,
Reports, Settings, logout/revoked-cookie denial, headers/indexing, oversized body
and shared login budget. It writes only synthetic import rows and analyses, and
uses bounded attempts. Wait Retry-After before repeating login tests; don't disable
the limiter. All proxied clients still share a process-local budget because
Uvicorn rejects proxy headers; this is acceptable for limited staging QA, not
scalable production or multi-instance protection.

Nginx directly terminates TLS, overwrites X-Forwarded-For/Proto with socket/scheme,
strips Forwarded/X-Forwarded-Host, validates canonical Host, and rewrites any
backend HTTP absolute redirect to HTTPS. Uvicorn retains --no-proxy-headers;
authorization/CSRF and Secure cookies do not depend on untrusted forwarded values.
SPA/docs behavior is deployment-sensitive: static production routes work; docs,
redoc and openapi.json explicitly return404 at the edge and remain disabled in
backend production mode. robots.txt and X-Robots-Tag discourage indexing, not access.
Application auth is the access boundary; optionally restrict provider firewall IPs
for private QA. No conflicting Basic Auth or public signup is added.

Actual browser validation is still required remotely: login/workspace/logout,
all routes and `/ai/<id>` refresh, asset cache headers, no mixed content, no CSP
blocks/JavaScript errors and trusted browser certificate. HTTP smoke is not proof
of rendered UI. From another machine validate HTTP redirect, invalid Host and
forged forwarded headers, and scan **only the approved VM** for the listed ports.
No real email/webhook integration is registered; CRM/automation remain unavailable.
The backend's internal network plus absent provider keys prevents real AI traffic.

```sh
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging logs --tail 100 --no-color backend frontend migrate provision
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging logs --follow --tail 50 backend
```

Backend JSON/request IDs and Nginx coarse-path JSON retain existing privacy rules.
Do not log raw CSV/DSN/cookies/query values, print `env` or share raw logs publicly.
Docker json-file rotation is 10 MiB x3 per container (bounded disk retention, not
a fixed number of days). No ELK/APM installed. Recreated containers may lose local
logs; retain safe incident evidence privately before recreation.

## Restart, redeploy, outage and rollback

```sh
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging restart backend frontend
python3 -B scripts/staging.py health --hostname "$LEADFORGE_STAGE_HOST"
# Normal redeploy: same project/private directory/volume, new reviewed release dir/tag.
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging up -d --force-recreate --wait --wait-timeout 180
```

Named volume persists account/org/membership/Lead/history. Validate row fingerprints
before/after restart/redeploy. Remotely test a backend process crash and a controlled
DB stop/start: liveness200, readiness503 then200. Reboot the dedicated approved VM
once if safe, verify Docker/service recovery, data, TLS and frontend; do not restart
the developer Docker daemon or host. A separate disposable failure project can
override the migration role to invalid: migration must exit nonzero and backend
must not run. Do not corrupt history or sabotage the live schema for this test.

Application rollback: preserve previous release directory, proxy configuration,
source manifest and image IDs. First confirm previous app is compatible with
current stored DB revision. Set LEADFORGE_STAGE_RELEASE to the previous retained
tag from that release directory, verify images still exist, and recreate **only**
backend/frontend with `up -d --no-deps --force-recreate backend frontend`. Check
trusted HTTPS readiness/smoke. Never build over the retained rollback tag. Do not
roll back PostgreSQL image/volume casually. App rollback does not reverse schema.
Prefer reviewed forward fixes; no automatic Alembic downgrade. Take a backup before
risky migration. Genuine disaster recovery restores into a fresh fenced DB via
5G, validates data, revokes sessions, then authorizes cutover separately.

## Backup, restore and protected artifacts

Use [5G recovery controls](BACKUP_RECOVERY.md), private VM storage outside web root,
minimum rolling 30-day successful retention and production encryption/offsite
requirements. No backup schedule/upload is installed during preparation. A future
approved staging timer would inject only backup-role credentials, call this CLI,
check exit/checksum and run a periodic separate-target restore; never mark a file
successful because a timer ran. Do not claim automated retention here.

```sh
umask 077
export LEADFORGE_BACKUP_PASSWORD="$(cat "$LEADFORGE_STAGE_PRIVATE_DIR/backup_password")"
python3 -B scripts/postgres_backup.py backup --container leadforge-staging-postgres-1 --database leadforge_stage --user leadforge_stage_backup --environment production --output-dir /opt/leadforge-staging/backups
unset LEADFORGE_BACKUP_PASSWORD
python3 -B scripts/postgres_backup.py inspect --artifact '<trusted-completed.dump>'
```

No shell tracing. Obtain the actual container name from Compose if defaults differ.
Restore admin must explicitly create a new template0 UTF8 DB with recorded locale;
never restore over leadforge_stage. Use external admin secret and exact confirmation:

```sh
export LEADFORGE_BACKUP_PASSWORD="$(cat "$LEADFORGE_STAGE_PRIVATE_DIR/admin_password")"
python3 -B scripts/postgres_backup.py restore --container leadforge-staging-postgres-1 --database '<fresh-disposable-recovery-db>' --user leadforge_stage_admin --environment production --artifact '<trusted-completed.dump>' --confirm-target 'leadforge-staging-postgres-1/<fresh-disposable-recovery-db>'
unset LEADFORGE_BACKUP_PASSWORD
```

Compare head/counts/relations/logical fingerprints, then perform isolated app checks
per 5G before any cutover. Restore omits original ownership/ACLs: reconcile roles
before starting the target app. An old snapshot can revive sessions; revoke restored
sessions while fenced. Delete only exact synthetic drill artifacts once evidence is
recorded, preserving protected operational copies. No public download endpoint.

## Local rehearsal and troubleshooting

```powershell
docker build -t leadforge-backend:5h-local-verification -f Dockerfile .
docker build -t leadforge-postgres:5h-local-verification -f deploy/postgres.Dockerfile .
docker build -t leadforge-frontend:5h-local-verification -f frontend/Dockerfile .
& .venv-ci/Scripts/python.exe -B scripts/verify_staging.py --output-dir .staging-artifacts/new-rehearsal
```

Requires the canonical dev environment (including cryptography); no dependencies
are added. The local helper generates only a test CA and five synthetic passwords,
binds loopback58080/58443 in a unique project, runs real roles/migration/TLS/app/
persistence/crash/outage/backup checks, proves invalid migration gating in another
owned disposable project, and removes only those project containers/volumes. It
does not accept a remote target or serve as a production deployer. Local secrets,
test certs and dumps require explicit recorded cleanup; safe JSON evidence remains
ignored. Existing :8080 runtime and SQLite stay separate.

| Symptom | Operator response |
| --- | --- |
| PostgreSQL unhealthy | Verify TCP readiness, LF secret file, dedicated volume/identity; don't wipe data or switch to trust. |
| Provision fails | Check intended role/DB ownership, separate strong private secrets; do not grant app superuser to bypass it. |
| Migration fails | Backend must remain blocked; use safe failure logs/config/privileges, not manual schema creation. |
| TLS failure | Verify real DNS, chain/key permissions, hostname/SNI, expiry and renewal/recreation; no insecure curl/browser bypass. |
| 400 Host | Use the exact approved hostname; invalid Host is expected to fail. |
| 401/403/429 | Check session/membership/CSRF/Origin or honor shared Retry-After. No credential logging or protection disablement. |
| Readiness503 | Check private DB reachability and exact revision; liveness alone is insufficient. |
| SPA/CSP/mixed content | Confirm same-origin assets/API and explicit headers/redirect; inspect browser, do not weaken CSP broadly. |
| Backup/restore failure | Use 5G runbook: checksum/TOC, fresh target, nonzero failure, atomic rollback and post-load business checks. |

## Safe teardown and remaining work

Stop/remove application containers and networks while retaining DB data:

```sh
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging down
```

This does not delete the named DB volume. **Do not add --volumes casually.** Delete
the exact verified staging volume only after explicit data-destruction authorization,
checking its name/mounts and retained backup/recovery requirements. Backup files,
private secrets/certificates and provider VM/disks/IP/DNS/billing resources are
separate lifecycles; removing containers does not remove any of those. Each requires
its own reviewed cleanup/retention decision. No destructive remote teardown helper.

Pending: provider/account/hostname authorization, real host provisioning and costs,
trusted public TLS/DNS, firewall/external browser validation, real remote persistence/
reboot/redeploy/outage/migration-failure/log/privacy/backup checks, renewal operation,
remote CI and production-specific security/capacity/release approval. Image advisory
ledger/manual deep scans and shared login budget remain; local superuser architecture
is unchanged, while proposed staging runtime uses separated non-superuser roles.
