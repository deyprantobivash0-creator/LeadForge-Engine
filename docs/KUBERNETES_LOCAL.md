# Local Kubernetes rehearsal (Step 5H-L)

This additive Docker Desktop path preserves all existing Compose files. It is a
synthetic production-configuration rehearsal, not remote staging or production
readiness. Remote Step 5H is **DEFERRED — NO DROPLET CREATED** because cloud
billing/provider deployment was intentionally postponed. **REAL REMOTE STAGING
NOT YET EXECUTED.** Step 5I remains **BLOCKED** by remote Step 5H.

## Scope and safety gate

Use only the current `docker-desktop` context, its loopback control-plane endpoint
and Ready local nodes. Node names need not match context names. The operation
helper checks all three before mutations and pins every Kubernetes command to
`--context=docker-desktop`. It refuses another current context rather than
switching contexts. Never apply these resources to a cloud cluster.

Namespace: `leadforge-local`. Configuration explicitly selects `production`,
`LEADFORGE_STAGING=true`, `AI_PROVIDER=mock`, Secure session cookies and the exact
synthetic HTTPS origin `https://staging.leadforge.test`. No real AI, customer data,
cloud resources, image publication or Step 5I operation is part of this runbook.

```text
Browser -> local HTTPS ingress -> frontend/Nginx -> same-origin /api
        -> backend ClusterIP -> FastAPI -> PostgreSQL ClusterIP
        -> PostgreSQL 16.15 StatefulSet -> 2 GiB PVC

Separate provisioning Job -> Alembic migration Job -> application startup
```

## Deployment files and gates

`deploy/kubernetes/kustomization.yaml` deliberately contains infrastructure only.
`namespace.yaml` is applied first, followed by runtime Secrets and the
infrastructure Kustomization. `provision.yaml`, `migrate.yaml`, `backend.yaml`,
`frontend.yaml` and `seed.yaml` are applied in that order only after each required
Job/rollout succeeds. JSON syntax in these `.yaml` manifests is valid YAML and
works with kubectl/Kustomize without a new deployment templating dependency.

The backend image derives from the existing Dockerfile and packages the existing
`deploy/staging` role provisioning, Alembic runner and explicitly manual synthetic
seed. No second application/provider/database architecture is introduced.
The application uses the non-superuser app role; only the migrator owns schema
DDL. App writes to `alembic_version` are revoked. The backup role has read-only
access. No application schema is created outside Alembic.

`check_schema.py` is a read-only init-container gate. It accepts exactly the
release's `LEADFORGE_SCHEMA_HEAD`, currently `e5d4c3b2a1f0`. Missing/mismatched
schema or database errors prevent application startup. The operation helper also
requires migration Job completion before it applies the backend. For a later
release, review its image identity, expected schema head and migration Job
identity together; do not reuse a completed Job as evidence of a new migration.

Services are all ClusterIP, including the ingress controller. No host networking,
host ports, NodePort, LoadBalancer or database publication is used. All containers
have requests/limits, non-root identities, RuntimeDefault seccomp, read-only root
filesystems, dropped capabilities and no privilege escalation. Writable paths are
bounded by container memory limits and ephemeral volumes. PostgreSQL runs as UID
999 with fsGroup 999 and a nested PGDATA directory on persistent storage. Backend
probes use `/health` for liveness and `/ready` for dependency readiness. The Host
header on app/frontend probes matches the configured synthetic hostname.

Traefik has namespace-scoped RBAC only and watches `leadforge-local`, with
cluster-scope lookup disabled and dashboard disabled. It watches namespace
Secrets to resolve ingress TLS; it is therefore a trusted local namespace
component. Database/application pods do not mount service-account tokens.
Frontend ingress routing uses the stable ClusterIP for pod replacement. Nginx
uses Kubernetes DNS and the backend's fully qualified Service name, preserves
request IDs and existing security/log privacy policy, overwrites forwarded
headers and fixes the external HTTPS scheme for this HTTPS-only ingress path.
This is not a general-purpose trusted-forwarded-header policy.

## Prepare and deploy

Use Python 3.12.14 with the existing development/CI requirements, Docker Desktop,
kubectl 1.36 and Node 22.22.2 for frontend checks. Commands below are from the repo
root in PowerShell. Check each exit status before the next operation.

```powershell
kubectl config current-context
kubectl --context=docker-desktop cluster-info
kubectl --context=docker-desktop get nodes
python -B scripts/kubernetes_local.py safety

docker build -t leadforge-backend:5h-l-base -f Dockerfile .
docker build -t leadforge-backend:5h-l-local -f deploy/kubernetes/backend.Dockerfile .
docker build -t leadforge-frontend:5h-l-local -f frontend/Dockerfile .
docker build -t leadforge-postgres:5h-l-local -f deploy/postgres.Dockerfile .
docker build -t leadforge-ingress:5h-l-local -f deploy/kubernetes/ingress.Dockerfile deploy/kubernetes

kubectl kustomize deploy/kubernetes
python -B scripts/kubernetes_local.py deploy
kubectl --context=docker-desktop -n leadforge-local get pods,pvc,services,ingress
```

The helper discovers CLI tools through PATH, then checks the current Windows
user's Docker Desktop install and the Program Files install. Verified workstation
binaries are under `C:\Users\USER\AppData\Local\Programs\DockerDesktop\resources\bin`;
the earlier supplied Program Files Docker path is not the active installation.
Git is available at `C:\Program Files\Git\cmd\git.exe`. No global PATH changes
or tool reinstalls are required.

Docker Desktop's verified node is `desktop-control-plane`, image
`kindest/node:v1.36.1`, with a separate containerd store. The helper exports images
locally, copies them into `/root` of that exact verified node and imports only
`linux/amd64`. Docker copying into the node's private `/tmp` mount does not make
files visible to `docker exec`; `/root` avoids that problem. All four local images use
`imagePullPolicy: Never`; nothing is pushed to a registry. The local ingress Dockerfile
pins the official Traefik 3.7.14 image digest and patches Alpine zlib. Another Desktop node/version needs an
explicitly reviewed image-loading update; never silently use a different node.

## Secrets and local TLS

`secret.example.yaml` is a placeholder example, excluded from Kustomize. Never
apply or commit real Secret values. The helper generates separate random local
passwords in ignored `secrets/leadforge-kubernetes-local/`, sends Secret JSON on
stdin and captures output without displaying values. Existing Secrets must match
local credentials; mismatches fail rather than rotate an initialized database.
Never run `kubectl get secret -o yaml`, print private files, or put secrets in argv.
Retain local password files together with the PVC; losing them is not a recovery
procedure. Kubernetes Secrets are base64 transport, not an encryption-at-rest
claim. The Docker/Kubernetes administrator remains trusted.

TLS uses an explicitly local, one-day synthetic certificate for
`staging.leadforge.test`, stored only in ignored local secret files and a runtime
TLS Secret. It is not a publicly trusted certificate and no public DNS, hosts-file
or global trust-store changes are made. An expired local certificate must be
renewed deliberately and its TLS Secret updated without rotating DB credentials.

The verifier binds ingress forwarding only to `127.0.0.1:58443`, resolves the
synthetic origin to that port in-process and validates the exact local certificate
and hostname. It retains the public origin without a port in cookies/CORS. An
interactive workstation browser needs an explicit local hostname mapping and
loopback HTTPS port 443 forwarding, with local-certificate trust/exception;
opening `https://localhost:58443` is not the configured origin.

## Repeatable validation

```powershell
python -B scripts/verify_kubernetes_local.py
# Prepare browser tools separately, with no credential mounts:
docker build -t leadforge-browser-tool:5h-l-local -f deploy/kubernetes/browser.Dockerfile deploy/kubernetes
python -B scripts/kubernetes_browser.py
```

The browser image pins Microsoft's existing Playwright image digest. Package
installation happens in that separate image build with lifecycle scripts disabled.
The runner verifies the lock's npm integrity against the official package registry
before mounting only the synthetic QA password, never DB/TLS private keys. There
are no runtime installs. Browser HTTP requests are restricted to the local
synthetic origin, with only the exact local certificate's SPKI exception; no broad
`ignoreHTTPSErrors` or global certificate trust change. The disposable test
container shares the verified local node's network namespace to reach ingress.

The infrastructure verifier reuses the existing HTTPS/auth/tenant/mock/CSV smoke
and backup archive/checksum/fresh-target policies. The shared smoke's default
Compose upload check is unchanged; Kubernetes supplies a curl streaming checker
because urllib can receive a connection reset while sending an already rejected
oversized body. The actual 2 MiB+1 upload must return HTTP 413 with request ID.

Drills compare logical table hashes, relationships, constraints and current
analysis selection after backend/frontend/PostgreSQL pod recreation, verify PVC
UID/PV identity, rolling restarts and a safe VERSION ConfigMap update/revert.
A failed migration Job plus a mismatched required head must leave a test backend
in its init gate with no ready application container. Test workload identities are
separate from healthy application Services. Recovery dumps use the backup role,
restore only into a freshly created disposable database, compare fingerprints,
reject a repeated restore into a populated target, then drop only that test DB.
The backup-client Pod and port-forward are removed when validation finishes.

Evidence: ignored `.staging-artifacts/5h-l/` and synthetic recovery archives under
ignored `backups/leadforge-kubernetes-local/`. Browser screenshots contain only
synthetic fixtures. Dumps/session/password data never enter source or the report.

Run the established gates as documented in `docs/CI.md`: isolated backend tests,
PostgreSQL integration with zero skips and fresh migration, frontend npm ci/lint/
build, pip check/audit, npm audit, Gitleaks plus negative control, actionlint,
source hygiene and the disposable Compose clean-build regression. Keep all tests
away from `leadforge.db` and private dotenv. Offline image security scans use
public DB downloads separately from private archive access, then `--network=none`
with Trivy `--offline-scan --skip-db-update --skip-java-db-update`, vulnerability
scanner only, telemetry/version checks disabled. Compare app findings against the
accepted images using the same DB; a new ingress must have no high/critical findings.
See the verification report for actual results and residual baseline findings.

## Restart, update and retention

```powershell
kubectl --context=docker-desktop -n leadforge-local rollout restart deployment/backend deployment/frontend
kubectl --context=docker-desktop -n leadforge-local rollout status deployment/backend
kubectl --context=docker-desktop -n leadforge-local rollout status deployment/frontend
```

ConfigMaps referenced by environment variables require a reviewed rollout;
Nginx's subPath configuration also requires a rollout. Retain PVC and local
credentials across normal restarts. Never delete the namespace, PVC or PV, run
Docker prune, or remove database volumes as a routine reset. Do not use historical
migrations/downgrades for rollback. Leave cloud/remote staging and Step 5I deferred.
A successful local rehearsal alone does not establish production readiness.
