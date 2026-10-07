# Step 5H verification report

October 7, 2026. **READY FOR DEPLOYMENT AUTHORIZATION.** No real remote staging
environment exists from this work. No provider, VM, account access, real hostname
or DNS authorization was supplied. Local preparation and verification passed;
public HTTPS, trusted public/browser certificate, external browser/network and
remote operational checks remain pending. Do not report 5H COMPLETE.

The user's Step 5H sections 3, 54 and 89 require approval before paid resources,
account access, DNS or Git/registry pushes. No such action occurred. No production
deployment, customer data, real AI, Step 5I, commit, push, historical migration
rewrite or destructive Git operation occurred. Existing dirty-tree work and
original SQLite were preserved. [STAGING.md](STAGING.md) contains the complete
reviewable deployment procedure, roles, TLS, secrets, smoke, recovery and teardown.

All 97 requested report items follow. **Local** results are explicitly distinguished
from pending remote results; this is not a green remote CI/deployment claim.

| # | Requested item | Result/evidence |
| --- | --- | --- |
| 1 | Status | READY FOR DEPLOYMENT AUTHORIZATION; local gates passed, remote target/access/authorization absent. |
| 2 | Model | Dedicated single Linux VM/VPS with Docker Compose. |
| 3 | Provider | Unselected; use existing approved VM or approve a specific provider/region/size/price. No surprise resource choice. |
| 4 | Rationale | Fits existing multi-container stack, native PostgreSQL, one-shot migration gate, direct same-origin Nginx and 5G backup clients. No registry/Kubernetes/Terraform required. |
| 5 | Architecture | Public HTTP80 redirect/HTTPS443 Nginx frontend -> private FastAPI8000 -> private PostgreSQL5432; dedicated volume/project; internal-only business network. |
| 6 | URL | No real staging URL. `staging.leadforge.test` was a disposable local-test hostname only, not a deployed/fake production domain. |
| 7 | TLS/certificate | Local TLS1.2/1.3 with explicit trusted local-test CA and hostname validation passed. Public CA/browser trust/DNS checks pending; no self-signed final validation claim. |
| 8 | Source/build fingerprint | SHA-256 `8032005d373ca1a45d655eac4172e8d067b4e3601a08d8ecd5a98b48ea9b7826`; release `5h-8032005d373ca1a4`. Safe archive/per-file manifest in `.staging-artifacts/release-5h/`; archive SHA `8c4fa0b8b5b94f062080abe74b640765611e72acf23c097d1d60a932b9229e20`. Git HEAD `2236c247b558e2ea61e9a58665155100a6c61aa0` plus dirty=true; not a committed-release claim. |
| 9 | Dirty state | Significant tracked/untracked legitimate work preserved; Git HEAD alone does not represent deployed inputs. Snapshot records HEAD plus dirty=true, source digest, archive SHA and timestamp. |
| 10 | Build/deploy strategy | On approved VM, build from verified source archive; tag with digest release. Initial staging does not depend on nonexistent registry/green remote CI pipeline. |
| 11 | Image IDs | Local final no-cache IDs recorded below. Remote image IDs pending on-host build; retain prior images/config for rollback. |
| 12 | Configuration | ENVIRONMENT=production, LEADFORGE_STAGING=true, AI_PROVIDER=mock, exact HTTPS origin, Secure cookies, INFO, rate limit enabled, release VERSION. Unsafe production checks unchanged. |
| 13 | Secrets | Five independent staging-only random admin/migrator/app/backup/QA password files; file-backed Compose secrets outside source, protected parent. Wrapper injects scoped URL without argv. Server-side session/CSRF tokens need no invented signing secret. |
| 14 | Secret audit | Gitleaks source scan/negative control passed. Local HTTP body/health/log sentinel checks passed; all exported backend/frontend/PostgreSQL image entries/layers (compressed and uncompressed) contained none of the generated credentials/test keys, including frontend assets. Remote audit pending. No values printed. |
| 15 | PostgreSQL | Exact 16.15, existing digest-pinned base and OS update recipe; private synthetic cluster. |
| 16 | DB exposure | No PostgreSQL port published; one internal Docker IPv4 network, SCRAM TCP. Remote external-port/managed-TLS validation pending; selected model uses private same-host DB. |
| 17 | Role model | Dedicated administrator, migrator DB/schema owner, runtime DML identity and SELECT backup identity implemented. All three non-admin roles verified non-superuser/no CREATEDB/CREATEROLE/BYPASSRLS. |
| 18 | Migration role | leadforge_stage_migrator; owner/DDL only in staging DB, not cluster admin. |
| 19 | Runtime role | leadforge_stage_app; business data DML/sequence use, no public-schema CREATE or Alembic write access. Privilege queries passed locally. Local development superuser role remains untouched. |
| 20 | Migrations | Fresh staging rehearsal base -> head passed using unchanged historical migrations. Remote migration pending. |
| 21 | Head | e5d4c3b2a1f0 in local staging, source/restore and fresh PostgreSQL regression. |
| 22 | Startup gate | PostgreSQL TCP health -> role provisioning -> migration success -> backend readiness -> frontend. Invalid migration identity in separate disposable project exited nonzero and backend did not run. |
| 23 | Liveness | Local HTTPS200 including DB outage; remote pending. |
| 24 | Readiness | Local HTTPS200 with DB/head usable; DB outage503 then recovery200. Remote pending. |
| 25 | Cookies | Local real HTTPS login: Secure, HttpOnly session, SameSite=Lax, Path=/, host-only; browser-readable Secure CSRF; no insecure fallback. Remote/browser pending. |
| 26 | Same origin | Local HTTPS same-origin assets/API and relative frontend base passed; proxy redirects preserve HTTPS. Remote mixed-content/browser proof pending. |
| 27 | CORS | Exact canonical HTTPS origin; allowed credentialed response passed, malicious Origin login denied403. No wildcard. Remote pending. |
| 28 | Proxy trust | Nginx terminates TLS itself, overwrites X-Forwarded-For/Proto from socket/scheme, strips Forwarded/X-Forwarded-Host. Uvicorn ignores proxy headers. Local forged-header/valid request passed; shared socket-peer rate budget retained. |
| 29 | Host | Local canonical name passed; invalid Host returned400. Internal readiness loopback remains supported by backend; frontend health bound only inside container loopback. Remote pending. |
| 30 | Headers | Local TLS responses passed CSP, nosniff, DENY framing, Referrer/Permissions policy, request ID, HSTS and noindex. Existing canonical policy reused. Remote pending. |
| 31 | CSP | Header policy present; no unsafe-eval/script relaxation. Rendered browser/console/CSP failures pending remotely. HTTP smoke alone is not browser proof. |
| 32 | HSTS | max-age=86400, HTTPS only; no includeSubDomains/preload. Separate production policy review required. |
| 33 | API docs | Local edge /docs, /redoc, /openapi.json returned404; backend production policy unchanged. Remote pending. |
| 34 | Indexing | robots Disallow:/ and X-Robots-Tag noindex,nofollow,noarchive passed locally. Not an access boundary. |
| 35 | Logs | Local backend/migration structured JSON and Nginx coarse-path JSON preserved; logs sentinel-free. PostgreSQL/provision native/fixed diagnostics separate. Remote operator access pending. |
| 36 | Request IDs | Local success and controlled failure IDs found in logs captured before redeploy; response correlation passed for every smoke request. Remote pending. |
| 37 | Rotation | Docker json-file 10 MiB x3 per container; bounded size, no fixed-days promise. Recreating containers can remove old logs; capture safe evidence first. |
| 38 | Login | Local HTTPS synthetic login passed; invalid password401 and malicious Origin403. Remote/browser pending. |
| 39 | Logout/revocation | Local logout and reuse of revoked old cookie returned401. Remote pending. |
| 40 | Workspace | Independent synthetic user saw only its authorized organization; explicit selection worked locally. Remote pending. |
| 41 | Tenant checks | Local HTTPS foreign Lead/Intelligence404 and foreign Reports export403; no cross-tenant CSV rows. Remote pending. |
| 42 | Dashboard | Local current pipeline count matched actual Lead count, opportunities unique by Lead; no analysis-event double count. Remote pending. |
| 43 | Leads | Local list/detail/current-analysis and tenant checks passed; synthetic Unicode/IDs persisted across restarts/redeploy. Remote pending. |
| 44 | CSV preview | Local CSRF enforcement passed; preview left Lead response unchanged, ready count1. Remote pending. |
| 45 | CSV import | Local confirmation imported1; repeat preview detected duplicate. No customer CSV. Remote pending. |
| 46 | CSV export | Local HTTPS export passed and excluded foreign tenant rows; existing formula-security regressions passed. Remote pending. |
| 47 | Intelligence | Local strict-production staging mock process and current/history selection by timestamp/highest-ID passed. No real provider keys/calls; private backend network. |
| 48 | Reports | Local historical analysis_events>=4/unique_analyzed_leads>=2 plus export passed. Remote pending. |
| 49 | Settings | Local endpoint passed; Staging Mock truthful availability/detail added under explicit flag, integration capabilities remain unavailable, no connectivity fiction. Remote/browser pending. |
| 50 | SPA | Local HTTP content checks passed /,/leads,/imports,/ai,/ai/1,/reports,/settings. Rendered direct navigation/refresh/assets checks pending in real external browser. |
| 51 | Console | Real staging browser console not tested; pending trusted public endpoint. |
| 52 | Synthetic fixture | Two labeled staging orgs, two users, one membership each, four Leads, eight historical analyses, Unicode/tie timestamps; smoke added one known import and one mock analysis. No customer identifiers/data. |
| 53 | Restart persistence | Local full logical fingerprints matched after backend/frontend restart; remote pending. |
| 54 | Redeploy | Local force-recreate of full project preserved full fingerprints and readiness; repeat provisioning/migration exited0, no loops. Remote pending. |
| 55 | Host reboot | Not performed on developer host/Docker daemon; remote dedicated-host reboot remains pending, not N/A for proposed VM. |
| 56 | DB outage/recovery | Local controlled PostgreSQL stop gave liveness200/readiness503; start recovered200. No data destruction. Remote pending. |
| 57 | Migration failure | Local invalid role configuration in separate fresh disposable project blocked backend startup. No migration-history corruption. Remote pending. |
| 58 | Backup | Local staging backup with dedicated SELECT-only role passed: 33,478 bytes, SHA b7db64b51a338bd247e0aacb7fa28954b26be967e07dbb75c2fa6bfe3da4dd01. Remote staging backup pending. |
| 59 | Restore drill | Local separate fresh restore DB passed 5G atomic restore/head plus full source/restored fingerprints; no active DB overwrite. Existing 5G application-level two-restore proof retained. Remote staging drill pending. |
| 60 | Rollback | Retain previous manifest/release/images/config; check schema compatibility; recreate app/frontend only from previous retained tag, no rebuild over rollback tag. Exact procedure in runbook. |
| 61 | DB rollback | Forward fix preferred; no automatic downgrade. Backup before risky migration; genuine disaster recovery into fresh fenced target, validate/grant/revoke sessions before authorized cutover. |
| 62 | Ports/services | Proposed remote 80/443 plus admin-IP SSH; no published DB/backend/Docker. Local rehearsal used only loopback58080/58443 and removed them; original8080 preserved. External remote scan pending. |
| 63 | Disclosure | Local Nginx header contained no version; backend server header disabled, docs blocked. No stronger fingerprinting claim. |
| 64 | Login budget | Local repeated invalid attempts produced429/Retry-After. Shared proxy peer, process-local/reset on restart; suitable for limited QA, distributed/production enforcement unresolved. |
| 65 | Advisories | Existing 183-record historical image ledger/manual scan policy carried forward. OS package version sets unchanged against established images; no blanket remediation claim or new deep advisory scan. |
| 66 | Remote CI | Pending. Local equivalents passed; no registry/hosted pipeline success implied. |
| 67 | Authorization | Pending provider/account/host/hostname access and explicit paid/DNS/remote action approvals under user sections3/54/89. No action bypassed. |
| 68 | Resources | Zero cloud/provider resources created, zero registry/Git push, no DNS changes. Only disposable local Docker projects/volumes, all removed. |
| 69 | Cost | No new recurring charges; provider quote/budget pending. Provisional VM capacity, not priced/recommended paid product. |
| 70 | Backend count | 259 passed, zero failures/errors/skips, 2098 existing deprecation warnings, 78.56s. 5G239 baseline plus20 staging policy tests. |
| 71 | PostgreSQL count | 5 passed, zero failed/skipped, 81 existing warnings, 3.15s; fresh migration and single-head checks passed. |
| 72 | Configuration | Full existing 5C regressions plus strict staging negative cases passed; flag cannot permit SQLite/insecure cookies/HTTP origin/debug/no-rate-limit or real AI. |
| 73 | Observability | Existing 5D regressions and local real proxy/backend log privacy/correlation passed. Remote pending. |
| 74 | Security | Existing tenant/CSRF/security tests, dependency audits (zero known project findings), Gitleaks plus negative control passed; local HTTPS body-size/Origin/Host/docs/header/cookie/rate tests passed. |
| 75 | Backup regression | Existing19 helper safety tests passed within full suite; read-only staging-role backup and separate restore fingerprint passed; 5G scripts unchanged. |
| 76 | CI | actionlint passed; existing workflow unchanged. Remote run pending. |
| 77 | Frontend install | Clean npm ci passed; zero known project audit findings. |
| 78 | Frontend lint | Passed with eight established warnings; no new frontend behavior/code change. |
| 79 | Frontend build | Production build passed; also no-cache image lint/build passed. |
| 80 | Containers | All three final no-cache images built; exact final images used in passing rehearsal. Secrets/test keys absent from all saved image layers/metadata. |
| 81 | Local runtime | Original backend/frontend/PostgreSQL healthy; normal :8080 HTTP/app smoke passed. No staging replacement of local project/volume. |
| 82 | SQLite SHA | Before/after unchanged 217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a. |
| 83 | Diff | git diff --check passed; meaningful code/config diff inspected, untracked staging files syntax/whitespace checked. Existing dirty work preserved. |
| 84 | Created | compose.staging.yml; deploy/staging/{db_roles.py,run_backend.py,seed.py}; scripts/{staging.py,staging_smoke.py,verify_staging.py}; tests/test_staging.py; docs/STAGING.md; this report. |
| 85 | Modified | backend/core/config.py, backend/ai/providers/router.py, backend/services/settings_service.py, .gitignore, .dockerignore, README.md, docs/{CONFIGURATION,AI_ARCHITECTURE,ARCHITECTURE,DEVELOPMENT}.md. No historical migration/Dockerfile/requirements changes. |
| 86 | Helpers | Small preparation/source archive/trusted HTTPS health helper, external synthetic smoke and isolated local verifier; fixed scoped role/bootstrap/seed entrypoints. No cloud orchestration framework or remote destructive teardown. |
| 87 | Documentation | Canonical STAGING.md and 97-item report, plus existing architecture/config/AI/development links clarified. |
| 88 | Staging limits | No real remote target/certificate/browser/firewall/reboot yet; single host, brief downtime, manual renewal/provider provisioning, process-local shared budget, trusted Docker admins, synthetic scale only. |
| 89 | Production unresolved | Real AI, capacity/HA/PITR, distributed abuse budgets, image advisory/manual deep review, offsite encryption/lifecycle/alerts, remote CI, production domain/TLS policy, release approval. No production readiness claim. |
| 90 | Deploy command | Runbook: trusted archive -> explicit release/host/private dir -> prepare/certificate -> compose config --quiet/build/up -d --wait; no Git push/registry required. Exact shell commands below/in runbook. |
| 91 | Health commands | Python trusted-HTTPS health helper and curl --fail /health,/ready; no insecure certificate bypass. |
| 92 | Logs commands | Compose logs --tail100 --no-color backend frontend migrate provision; follow backend only when needed; no env/raw payload dump. |
| 93 | Redeploy command | Same project/private directory/volume, reviewed new release: compose up -d --force-recreate --wait --wait-timeout180; check fingerprints/readiness. |
| 94 | Rollback command | Previous compatible release/tag/config: compose up -d --no-deps --force-recreate backend frontend; health/smoke. No downgrade or DB image/volume rollback. |
| 95 | Backup command | Existing 5G CLI backup on explicit staging container/DB, SELECT-only role, private directory, externally injected password; exact invocation below. |
| 96 | Teardown | compose down retains DB volume; separate explicit authorization for exact volume/backup/secrets/certs and paid provider/DNS resources. No automated destructive remote removal. |
| 97 | Recommendation | Authorize a concrete dedicated VM/hostname/access/cost/DNS plan, then execute remote deployment and all pending mandatory checks. Until then remain READY FOR DEPLOYMENT AUTHORIZATION and stop after5H. |

## Exact final local image identifiers

These are `docker image inspect --format '{{.Id}}'` values for the local final
no-cache images actually exercised; not remote registry digests:

| Image tag | Local identifier |
| --- | --- |
| leadforge-backend:5h-local-verification | sha256:8d8bb69dd17adacf0e9ba763e4490b8ae2f1dafef9831afd66017ac03b306be0 |
| leadforge-frontend:5h-local-verification | sha256:cf6ecc16cc39a686f6a8c182e34c33127171692b29deaf071dbd2eea75087831 |
| leadforge-postgres:5h-local-verification | sha256:d3cee6ca2044e069f0605f921518d20a2667802435d7e1613ea6ad33da79dbd5 |

## Exact deployment, operations and rollback commands

These are templates for the **later authorized remote host**, not remotely executed
commands. Set the three non-secret shell variables from the approved hostname,
private directory and verified manifest release. Full host/DNS/certificate/source
transfer instructions are in STAGING.md. No password values appear in argv.

```sh
export LEADFORGE_STAGE_HOST='<real-staging-hostname>'
export LEADFORGE_STAGE_PRIVATE_DIR='/opt/leadforge-staging/private'
export LEADFORGE_STAGE_RELEASE='<release-from-verified-manifest>'
python3 -B scripts/staging.py prepare --hostname "$LEADFORGE_STAGE_HOST" --private-dir "$LEADFORGE_STAGE_PRIVATE_DIR"
# Supply trusted fullchain.pem/privkey.pem per runbook, then:
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging config --quiet
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging build
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging up -d --wait --wait-timeout 180
python3 -B scripts/staging.py health --hostname "$LEADFORGE_STAGE_HOST"
curl --fail --silent --show-error "https://$LEADFORGE_STAGE_HOST/health"
curl --fail --silent --show-error "https://$LEADFORGE_STAGE_HOST/ready"
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging logs --tail 100 --no-color backend frontend migrate provision
# Normal redeploy, same volume/project and reviewed release inputs:
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging up -d --force-recreate --wait --wait-timeout 180
# Rollback: cd to retained previous release directory/config, confirm DB compatibility,
# set previous retained tag, never rebuild it or downgrade schema:
export LEADFORGE_STAGE_RELEASE='<previous-retained-release>'
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging up -d --no-deps --force-recreate backend frontend
python3 -B scripts/staging.py health --hostname "$LEADFORGE_STAGE_HOST"
# Backup; only from explicit staging DB, no tracing or stdout secret prints:
export LEADFORGE_BACKUP_PASSWORD="$(cat "$LEADFORGE_STAGE_PRIVATE_DIR/backup_password")"
python3 -B scripts/postgres_backup.py backup --container leadforge-staging-postgres-1 --database leadforge_stage --user leadforge_stage_backup --environment production --output-dir /opt/leadforge-staging/backups
unset LEADFORGE_BACKUP_PASSWORD
# Safe container/network teardown retaining database volume:
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging down
```

Check every exit status; readiness after deployment is mandatory. Volume deletion,
secret/key/backup deletion and cloud/DNS/billing removal are independent and need
explicit scoped authorization. No blanket prune/--volumes remote teardown command.

The final actual local verifier command was:

```powershell
& .venv-ci/Scripts/python.exe -B scripts/verify_staging.py --output-dir .staging-artifacts/rehearsal-09
```

Safe final evidence is `.staging-artifacts/rehearsal-09/verification.json` and
the synthetic fixture-ID manifest. Its generated project
`leadforge-5h-check-c3db78b00dfe` and separate migration-failure project were
removed, including their owned DB volumes. Exact local test secret/certificate
directories, synthetic dump directories and failed attempt artifacts were removed
after evidence capture; local final image tags and safe source archive retained.
No unrelated backup, volume, secret or dirty source was removed.

## Verification corrections and remaining remote gates

Early attempts detected a YAML flow-list comma in tmpfs options, Windows CRLF
password initialization mismatch, mounted seed import path, PID1 signal semantics,
manual Docker kill suppressing restart policy, one overlapping local port and log
loss after container recreation. These were corrected in configuration/test
execution; no protection was waived. The successful crash test signaled only the
inspected uniquely named disposable backend PID from an ancestor namespace, so
Docker observed an unexpected exit and restarted it. A short-lived network-none
runner held only CAP_KILL; no developer host/daemon restart occurred. It is a local
test technique, not a deployment requirement.

The final rehearsal passed after corrections, against all three no-cache images.
Local tests cannot replace real external certificate/browser/mixed-content/CSP,
DNS/firewall, VM reboot, provider access/cost and remote incident-operation evidence.
Those remain required before 5H COMPLETE. No technical local mandatory gate is
left failing; the current blocker is remote target/account/authorization.
