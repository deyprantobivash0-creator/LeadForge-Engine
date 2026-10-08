# Step 5H-L pre-commit verification

October 8, 2026. **STEP 5H-L — COMPLETE (local synthetic rehearsal).**
**No commit or push performed.** Main/history remain at
`6f8b1f1dbbb919078581e829357d692af18b4091`; index is empty.
This report records executed checks, not inferred product capability.

Remote Step 5H remains **DEFERRED — NO DROPLET CREATED**.
**REAL REMOTE STAGING NOT YET EXECUTED.** Cloud billing/provider deployment was
intentionally postponed, not an application failure. Step 5I remains **BLOCKED**
by remote Step 5H. LeadForge is not declared production-ready.

## Executed gates

| Gate | Final result |
| --- | --- |
| Kubernetes safety | PASS: current context `docker-desktop`; control plane `https://127.0.0.1:49175`; `desktop-control-plane` Ready, Kubernetes v1.36.1. Node name/context mismatch is allowed. |
| Baseline preservation | PASS: main SHA preserved, no history rewrite, no commit/push, root tooling left untracked, prior staging documentation preserved. |
| Namespace / Kustomize | PASS: `leadforge-local`; infrastructure Kustomization and ordered provisioning/migration/application phase manifests accepted by the live API. Restricted Pod Security enforced. |
| Local images | PASS: existing backend/frontend/PostgreSQL Dockerfiles reused; role scripts packaged in local backend derivative; four local tags imported into the verified node containerd store. No image publication. |
| PostgreSQL | PASS: server 16.15; StatefulSet; 2 GiB `data-postgres-0` PVC Bound on Desktop `standard` storage; original PVC UID/PV retained across PostgreSQL recreation. |
| Internal Services / ingress | PASS: backend 8000, frontend 8080, postgres 5432, local-ingress 8443, all ClusterIP; HTTPS Ingress for `staging.leadforge.test`. No NodePort, LoadBalancer, hostPort, host network, public database or cloud resource. |
| Database roles | PASS: non-superuser migrator/app/backup identities; app has no schema CREATE and no Alembic UPDATE; role privilege audit passed. |
| Migration Job | PASS: explicit provisioning then Alembic base-to-head, required/stored head `e5d4c3b2a1f0`; backend applied only after Job success and read-only init gate passes. |
| Probes / resources / securityContext | PASS: backend liveness `/health`, readiness `/ready`, startup probe; frontend and ingress health probes; requests/limits; non-root, RuntimeDefault seccomp, read-only root, dropped capabilities, no privilege escalation; no app/DB service-account tokens. |
| HTTPS application smoke | PASS: health/readiness, all SPA routes, security/indexing headers, canonical host/origin, Secure/HttpOnly/SameSite cookies, auth, explicit workspace, Dashboard, Leads, Intelligence/current history, Reports, Settings, logout and server-side revocation. Exact local cert/hostname validated; no public TLS claim. |
| CSRF / tenant / mock AI / CSV | PASS: absent CSRF rejected, foreign membership/lead/intelligence/export rejected, mock processing persisted, preview made no writes, confirmation imported one row, repeat preview detected duplicate, tenant-safe CSV export. No paid provider call. |
| Body / login limits | PASS: actual 2 MiB+1 upload returns HTTP 413 with correlation ID via curl; shared login budget returns 429 with Retry-After. |
| Browser product checks | PASS: Chromium login/workspace, seven product routes including Lead intelligence detail, reload, secure cookies/storage, inert script-like CSV preview, report download, logout; zero page errors and zero CSP/CORS violations. Exact synthetic cert SPKI exception only. |
| Structured logging / request IDs | PASS: each smoke request ID found in credential-checked logs; existing structured event/privacy policy retained. |
| Pod recreation / persistence | PASS: backend, frontend and PostgreSQL pod UIDs changed; logical table/constraint/current-analysis fingerprints unchanged after each; PVC identity unchanged. |
| Rolling restart | PASS: backend/frontend rolled successfully; HTTPS readiness and database fingerprint preserved. |
| Safe ConfigMap update | PASS: VERSION updated, backend rolled and value observed; original ConfigMap reapplied and backend rolled; fingerprints unchanged. |
| Migration failure | PASS: deliberate invalid-role migrator Job failed; separate backend with mismatched required head remained in failing init gate with no ready app container; healthy app unchanged; drill workloads removed. |
| Kubernetes backup / recovery | PASS: read-only backup role, PostgreSQL custom archive with existing manifest/checksum policy, fresh disposable restore, equal logical fingerprints/constraints/current analysis, populated-target restore rejected; test database removed. |
| Compose regression | PASS: `scripts/ci.py containers`: own disposable project, configuration, no-cache image builds, coordinated migration startup, private HTTP smoke/log privacy, cleanup. Existing runtime/development volumes preserved. |
| Backend regression | **264 passed, 0 skipped**, 2098 existing warnings. Includes 259 baseline tests plus five context/endpoint/node/secret-rotation safety tests. `pip check` passed. |
| PostgreSQL integration | **5 passed, 0 skipped**, 81 existing warnings. Exact 16.15 server, all migration modules/single head imported, separate fresh database migrated/stored head verified. |
| Frontend | PASS: Node 22.22.2, npm ci, lint, build; clean Linux Docker frontend build also passed. Eight existing lint warnings remain; no new build/import error. |
| Dependency audits | PASS: resolved Python `pip-audit` reports no known vulnerabilities; npm audit reports zero vulnerabilities; pip check passes. No automatic dependency fix or unrelated app refactor. |
| Image security | PASS for the requested **no-new-regression** criterion; same-DB comparison and final new-ingress findings are detailed below. This is not a zero-CVE claim for existing application OS layers. |
| Secret audit | PASS: final Gitleaks 8.30.1 scan and negative control; exact generated local password strings absent from eligible source; private dotenv not read; runtime Secret values/cert keys/dumps excluded from source. |
| actionlint / source hygiene | PASS: actionlint with established optional tool settings, diff/source hygiene, final diff --check. |
| Original SQLite | PASS: unchanged SHA-256 `217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a`. No tests/migrations targeted `leadforge.db`. |

## Security evidence and applicability

Trivy 0.75.0 was digest-pinned to
`sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa`.
The public vulnerability DB was downloaded with no app/credential mounts.
Private image archives were scanned afterward with `--network=none`, offline
mode, DB updates/Java DB updates, telemetry and version checks disabled. No
private image/SBOM was uploaded. The same database scanned baseline and new images.

| Image | Critical | High | Medium | Low | Unscored | New findings versus baseline |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Backend | 2 | 53 | 112 | 102 | 1 | **0**; identical finding identities/package versions to accepted `5b-local`. |
| Frontend | 0 | 0 | 0 | 0 | 0 | **0**; baseline had one medium, absent from this build. |
| PostgreSQL | 2 | 82 | 120 | 134 | 7 | **0**; identical finding identities/package versions to accepted `16.15-local`. |
| Final local ingress | 0 | 0 | 0 | 0 | 1 | Only module-level GO-2026-5932; scoped non-applicable assessment below. |

Existing backend/PostgreSQL findings remain visible in raw offline reports;
this local task did not broaden the accepted production scope, add blanket
waivers or assert all residual packages are safe. Their ongoing patch/reachability
work remains part of the existing security debt. All new ingress critical/high
findings from the first candidate were fixed by upgrading to official Traefik
3.7.14. Its Alpine zlib finding CVE-2026-85091 was fixed with `1.3.2-r1` in the
local derivative; none of that candidate's scored findings remain.

GO-2026-5932 flags `golang.org/x/crypto/openpgp` and its subpackages, all versions,
with no known fix ([official Go advisory](https://pkg.go.dev/vuln/GO-2026-5932)).
The scanner detects module `golang.org/x/crypto v0.57.0`; the extracted public
upstream Traefik binary has **zero occurrences** of the affected OpenPGP package
path, while this configured controller consumes ordinary TLS PEM and Kubernetes
Ingress, with no OpenPGP flow. Engineering assessment on October 8, 2026:
**not applicable to this shipped controller**, inferred from the package-specific
advisory and binary/configuration evidence; this is not a complete call-graph
proof or a waiver for future OpenPGP features. No scanner suppression was added.

Automatic approval review rejected the initial combined browser credential mount
and package-install command, and rejected Docker Scout's possible external private
image metadata transmission. Neither rejected action executed. Both were resolved
through safer, approved workflows: separate verified browser-tool preparation with
no runtime installs/local-only browser requests, and network-disabled offline
image archive scans. No permission request remains unresolved.

## Final local identities and retained state

| Image | Local ID |
| --- | --- |
| backend | `sha256:67145eb768210a9267dbae3bc9428d92bdc4fdf5f39cb2466956ed19c87a6c7f` |
| frontend | `sha256:20ffa12c93d27e2452a44c9be23831b5ccbe700b5109d0382932ba971f6a3630` |
| postgres | `sha256:a5b79649b3e5b0b7fecc80ffdedb8b058f175b13bac57161231d05da67bacace` |
| ingress | `sha256:e06c3ebae98447555bb083178ffd4cd7116f7d14ce7f344e7ca3938fc9c54eed` |

Final recovery archive: 34293 bytes;
SHA-256 `0c2a79050d570d4f632179984671723af8805acffc93a1fe5f2a30948a50dea5`. Stored in ignored
`backups/leadforge-kubernetes-local/`, with manifest/checksum sidecars.
No dump, private certificate/key, password or session value is committed.

Namespace, four healthy workloads, successful provision/migrate/seed Jobs, PVC/PV
and runtime Secrets are retained for the authorized local rehearsal. The verifier's
backup-client Pod, port-forward, migration-failure test Job/Deployment and restore
database were removed. Browser/scan test containers were disposable. Local image
tags, ignored image archives/evidence/backup files and ignored local credentials
remain; no unrelated artifact/volume was deleted. No listener from this test is
left published. Existing Compose frontend loopback 8080 and development PostgreSQL
loopback 55432 were present before this task and are preserved.

Single Desktop node/local-path storage is not HA or host-loss recovery. The local
certificate is one-day, synthetic-only. Namespace ingress RBAC watches namespace
Secrets; host/Docker/Kubernetes admins are trusted. The existing shared, process-
local login budget remains. These facts do not change remote release gates.

## Exact proposed commit scope

Add/change these files for Step 5H-L and its directly relevant remote status.
Existing legitimate edits within the three staging documents are preserved and
would be included if this exact file scope is approved. Nothing is staged yet.

- `docs/STAGING.md`
- `docs/STEP_5H_VERIFICATION.md`
- `docs/STAGING_RESOURCE_PLAN.md`
- `docs/KUBERNETES_LOCAL.md`
- `docs/STEP_5H_L_VERIFICATION.md`
- `scripts/staging_smoke.py`
- `scripts/kubernetes_local.py`
- `scripts/verify_kubernetes_local.py`
- `scripts/kubernetes_browser.py`
- `scripts/kubernetes_browser_smoke.mjs`
- `tests/test_kubernetes_local.py`
- `deploy/kubernetes/backend-service.yaml`
- `deploy/kubernetes/backend.Dockerfile`
- `deploy/kubernetes/backend.yaml`
- `deploy/kubernetes/backup-tools.yaml`
- `deploy/kubernetes/browser.Dockerfile`
- `deploy/kubernetes/check_schema.py`
- `deploy/kubernetes/config.yaml`
- `deploy/kubernetes/frontend-service.yaml`
- `deploy/kubernetes/frontend.yaml`
- `deploy/kubernetes/ingress-controller.yaml`
- `deploy/kubernetes/ingress-rbac.yaml`
- `deploy/kubernetes/ingress.Dockerfile`
- `deploy/kubernetes/ingress.yaml`
- `deploy/kubernetes/kustomization.yaml`
- `deploy/kubernetes/local-ingress-service.yaml`
- `deploy/kubernetes/migrate.yaml`
- `deploy/kubernetes/namespace.yaml`
- `deploy/kubernetes/nginx.conf`
- `deploy/kubernetes/postgres-service.yaml`
- `deploy/kubernetes/postgres.yaml`
- `deploy/kubernetes/provision.yaml`
- `deploy/kubernetes/secret.example.yaml`
- `deploy/kubernetes/security-headers.conf`
- `deploy/kubernetes/seed.yaml`

Preserved pre-existing work outside this proposed commit:

- `docs/STEP_5F_VERIFICATION.md`: already modified on entry; untouched by 5H-L.
- `docs/STEP_5H_B_VERIFICATION.md`: already untracked on entry; untouched by 5H-L.
- Root `package.json` and `package-lock.json`: LEGITIMATE LOCAL TOOLING;
  untouched/untracked, excluded from the proposed commit. Do not delete them.

Proposed commit message:

```text
feat(deploy): add verified Docker Desktop Kubernetes rehearsal
```

## Reproduction and evidence

See [local runbook](KUBERNETES_LOCAL.md). Executed command families:
`kubernetes_local.py safety/deploy`, ordered kubectl applies/rollout waits,
`verify_kubernetes_local.py`, `kubernetes_browser.py`, `scripts/ci.py backend`,
`postgres`, `frontend`, `security`, `secrets`, `containers`, `hygiene`, actionlint
and git diff --check. PATH additions were process-local; no global settings changed.

Ignored `.staging-artifacts/5h-l/` contains `verification.json`,
`browser-verification.json`, browser screenshots, credential-checked runtime logs,
`backend-final.log`, `postgres.log`, `frontend.log`, `security.log`,
`gitleaks-final.log`, `compose.log`, `final-images.json`, baseline/current image
vulnerability JSON and final `ingress-final-cves.json`. These are supporting local
artifacts, not release sources. No real AI or customer data was introduced.

Corrected attempts are recorded rather than claimed as successful: sandbox process
creation failed until authorized direct execution; actual Docker CLI installation
was discovered despite the supplied fallback path being absent; image import needed
the visible node `/root` path and a single architecture; trusted Host probe headers
and Nginx fully qualified Service DNS were added; stable ClusterIP ingress routing
and a streaming body-limit checker addressed pod replacement/early HTTP rejection;
new ingress advisories were patched and full affected gates rerun. Final schema-gate
file bytes match the tested image exactly; a transient newline-only source difference
was reconciled after verifying equal code.

**STEP 5H-L: COMPLETE. Remote STEP 5H: DEFERRED — REAL REMOTE STAGING NOT YET EXECUTED.
STEP 5I: BLOCKED.** No production readiness or commit/push is implied.

APPROVE STEP 5H-L COMMIT AND PUSH?
