# Release preparation — Step 5H-A

October 7, 2026. **RELEASE PREPARED — COMMIT APPROVAL REQUIRED.**
Branch `main`, original HEAD `2236c247b558e2ea61e9a58665155100a6c61aa0`.
No remote or upstream is configured; GitHub CLI is unavailable on the inspected
PATH and usual installation locations. No commit, index change, push, remote branch,
repository-setting change, cloud/DNS operation or deployment has occurred.
The [verification report](STEP_5H_A_VERIFICATION.md) contains all requested results.

## Reviewed source scope

[RELEASE_SCOPE.csv](RELEASE_SCOPE.csv) lists every changed/untracked path,
its Git status, category, inclusion decision and reason. Categories follow the
user's A–P inventory contract. Include the legitimate Phase 3–5H implementation,
tests, four previously untracked revisions, build/deployment/CI inputs and docs.
The one existing deletion replaces `backend/ai/providers/base_provider.py` with
the canonical `base.py`; no remaining references to the deleted module were found.
Retain unused legacy modules/manual root tests; do not run those tests in CI.

Exclude root `package.json` and `package-lock.json`: they are the old local Node
setup with no application scripts. The complete frontend manifests/lock already
declare the required dependencies and passed independent clean installation/build.
Both excluded root files remain untouched and untracked. This does not add broad
ignore patterns for source files or delete work.

The ignored local audit directory `.staging-artifacts/release-prep/` contains
`initial-inventory.json`, `inventory-summary.json`, the complete per-file
`excluded-ignored.csv`, `safety-audit.json`, `source-review.json`, the reviewed
`release-paths.nul` and final `release-source.json`. These local files are excluded
from the commit. Ignored inventory is metadata only: private env, DB/backups,
dependencies, build output and TLS material are never copied to the release.
Source fingerprint covers the complete proposed checkout, not merely dirty files.
Deleted entries have explicit deletion records. The verification report itself is
included; final per-file hashes are kept outside source to avoid circular hashing.

The private root and frontend `.env` contents remain unread after automatic approval
review rejected that access. Metadata proves both are ignored and untracked; neither
is present in the candidate set or clean verification copies. The safe `.env.example` contains
empty provider/integration secrets and documented disposable local configuration.
`deploy/compose.env` contains comments only. No frontend dotenv or staging private
env/key is included. Public Vite configuration remains same-origin `/`.

## Validation and limitations

Full backend: 259 passed, zero skipped; PostgreSQL: 5 passed, zero skipped,
fresh base-to-head `e5d4c3b2a1f0`. Production configuration, privacy, tenant/security,
backup safety and staging policy regressions are included. Dependency consistency
and Python/npm audits passed with zero known project findings. Gitleaks 8.30.1 and
its negative control passed; actionlint 1.7.7 passed. Clean frontend npm ci/lint/build
passed, retaining eight established warnings. Three no-cache Linux images built
from the source-only release copy; private Compose startup/readiness/assets/log
privacy smoke passed and the owned project/volume were removed.

The existing loopback runtime also passed functional and observability/security
smoke. Original SQLite remains unchanged. Tests never collect root manual scripts,
call a real provider or use customer data. AI remains mock. Runtime source/scripts
have no hardcoded developer-machine paths after the audit helper portability fix.
Historical migrations were not changed. Requirements and frontend lock are included;
Python transitives and OS upgrades remain only partially locked, as documented in CI.
Existing image advisory ledger and manual deep-scan policy are retained; successful
builds do not mean vulnerability-free images or production approval.

## Commit authorization gate

Proposed message:

```text
feat: production-engineer LeadForge through staging readiness
```

Before staging, revalidate the frozen manifest against HEAD, the empty index,
current changed-path set, every included file hash, deletion and exclusion.
Any source/scope change requires fresh review and approval. Do not stage now.
After **explicit approval of this exact inventory**, use the literal reviewed
NUL-delimited path set, including the one approved deletion:

Git's complete author identity is not configured. The user must supply the release
author name/email; apply them to this one commit using `-c`, without changing global
Git settings. The placeholders below are pending user input, never invented identities.

```sh
git --literal-pathspecs add --pathspec-from-file=.staging-artifacts/release-prep/release-paths.nul --pathspec-file-nul
git diff --cached --check
git status --short
git diff --cached --stat
# Recheck staged blobs against the reviewed manifest, exclusions and redacted scanner.
git -c user.name="<approved-author-name>" -c user.email="<approved-author-email>" commit -m "feat: production-engineer LeadForge through staging readiness"
git rev-parse HEAD
git show --stat --oneline HEAD
git status --short
```

No `git add .`, reset, restore, clean, force push or history rewrite. Index validation
and staged secret scan must pass before commit. The final SHA, not this original
dirty HEAD or a local test image tag, becomes the candidate release identity.

## Push and remote CI gate

User must identify the intended GitHub owner/repository and approve any remote setup
and push separately. No remote URL, branch creation or credentials are invented.
Use an existing secure credential manager/authentication method; never paste tokens
or private SSH keys into source/chat. Inspect auth status without printing tokens.
Before asking for push approval, identify target URL/branch, exact new SHA, upstream
and fast-forward result using a read-only remote lookup. Propose the minimum normal
push command for that verified state; do not assume `origin` exists here.

After authorized push, locate the `Quality` run for the **exact pushed SHA** and
verify backend, postgres, frontend, security, containers and always-evaluated
quality-gate all succeed. Ordinary push triggers the existing workflow; no deploy,
registry publication or real AI credentials are involved. Any required failure
blocks staging. Fix a repository defect locally, rerun relevant gates and request
new commit and push approvals. Never bypass CI or modify branch protection.

Only after a real successful aggregate gate may 5F become COMPLETE. Record run URL/ID,
commit and all job results. Any evidence-document edits afterward are uncommitted
and outside that release until separately approved/verified. 5H remains READY FOR
DEPLOYMENT AUTHORIZATION until actual remote deployment and verification pass.

## Exact staging handoff once prerequisites are satisfied

Choose an existing approved dedicated Linux Docker/Compose host, or separately
approve a provider/region/VM size and quoted recurring cost. The proven single-host
stack needs no new Kubernetes, managed DB, load balancer or registry. No paid
provider recommendation/purchase is implied by this preparation.

Supply the host, deployment user and secure SSH/agent access method; real hostname
and DNS authority; trusted certificate/renewal plan; approved admin source IPs;
resource/billing/DNS permission where needed; explicit remote deployment approval.
If using a provider-issued name, first establish that it supports this stack and a
trusted certificate under the direct Nginx TLS boundary. No fake endpoint is valid.

From a new clean release checkout on the approved host, verify:

```sh
git rev-parse HEAD                 # Must equal the remote-CI-verified release SHA.
git status --porcelain             # Must be empty before private files are supplied.
export LEADFORGE_STAGE_RELEASE="<exact-verified-commit-SHA>"
export LEADFORGE_STAGE_HOST="<approved-real-hostname>"
export LEADFORGE_STAGE_PRIVATE_DIR="<approved-protected-absolute-directory>"
python3 -B scripts/staging.py prepare --hostname "$LEADFORGE_STAGE_HOST" --private-dir "$LEADFORGE_STAGE_PRIVATE_DIR"
# Provision trusted TLS outside source according to STAGING.md, after authorization.
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging config --quiet
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging build
docker compose --env-file /dev/null -f compose.staging.yml -p leadforge-staging up -d --wait --wait-timeout 180
```

Alternatively transfer a trusted `git archive` of that exact SHA with authenticated
checksum/provenance, never a newer dirty checkout or the earlier 5H rehearsal archive.
Record actual image IDs because build-time package updates can change images even
for identical source. Follow [STAGING.md](STAGING.md) for provisioning/grants, TLS,
synthetic QA, external trusted HTTPS/browser/port checks, logs/privacy, persistence,
reboot/redeploy/outage/failure gates, backup/restore and rollback. Stop on any required
failure. Real remote checks are still pending. **Step 5I remains BLOCKED.**
