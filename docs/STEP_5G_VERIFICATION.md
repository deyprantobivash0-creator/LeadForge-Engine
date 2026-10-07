# Step 5G verification report

Verified October 7, 2026. **5G locally COMPLETE.** Real PostgreSQL custom-format
backup, two independent fresh restores, source/restored fingerprints, restored
application checks and ten failure cases passed. Step 5F remote CI remains
pending. No Step 5H, deployment, production scheduling, external upload, commit
or push occurred. Existing dirty-tree work, historical migrations and the
original SQLite file were preserved. No private `.env` was read or modified;
only synthetic fixtures and mock AI were used.

The [canonical runbook](BACKUP_RECOVERY.md) contains the full commands, storage
policy, recovery sequence and troubleshooting. This table covers all 85 requested
report items. Timings describe the tiny synthetic fixture, not production capacity.

| # | Requested item | Result/evidence |
| --- | --- | --- |
| 1 | Status | LOCALLY COMPLETE; applicable local gates passed. Production automation and remote CI remain deferred. |
| 2 | Existing backup capability | Historical SQLite snapshots exist; no PostgreSQL-native backup/recovery workflow was found. They were preserved, not used as PostgreSQL recovery. |
| 3 | Architecture | One standard-library operator CLI using matching containerized PostgreSQL clients, plus one synthetic drill. No application endpoint/startup backup, duplicate service or schema change. |
| 4 | Backup scope | Full application DB: organizations, users, memberships, sessions, Leads, LeadAnalysis/history, legacy ingestion_jobs, Alembic revision, sequences, indexes and constraints. |
| 5 | Exclusions | Source/build assets, caches, environments, logs, SQLite snapshots, cluster roles/configuration, encryption keys. Registered imports keep no uploaded file store; Settings has no persisted configuration store. Reassess if storage/extensions arrive. |
| 6 | Format | Compressed PostgreSQL custom archive, PGDMP header, native consistent pg_dump snapshot. No manual row export. |
| 7 | Tool version | PostgreSQL server/pg_dump/pg_restore 16.15; digest-pinned image `postgres:16.15@sha256:65b16a8b326e0cfbdf33fa7e783f2a0cb352a61448616ccccfd616ef42aa0f65`. |
| 8 | Execution model | Docker client containers connect to the explicit server's private IPv4 on its single Docker network. Separate client namespace prevents localhost trust from bypassing credentials. Inspect runs offline with network none. |
| 9 | Backup script | `scripts/postgres_backup.py backup`; explicit container/database/user/environment/output. Binary subprocess output, exclusive bundle, partial suffix, fsync, TOC/checksum validation before completion. |
| 10 | Restore script | Same CLI `restore`; inspect operation also provided. No drop/create/clean/reset option. |
| 11 | Credentials | External `LEADFORGE_BACKUP_PASSWORD`; Docker forwards PGPASSWORD by variable name. No password argv, private dotenv, logged URL, token or credential hash. Docker administrators remain trusted. |
| 12 | Local directory | Only ignored `backups/` allowed within repo; explicit external path recommended for production. Output rejects symlink traversal and source/public directories. |
| 13 | Git exclusion | Every actual drill file verified Git-ignored. Added dump/checksum/metadata/backup patterns; backups already ignored. |
| 14 | Docker exclusion | Added corresponding Docker patterns. Both final backend and frontend image file trees verified free of backup directories/archives. Runtime backup URL served only SPA HTML, never a dump. |
| 15 | Artifact | `leadforge-20261007T060053Z-0b41e720eb48.dump`, originally inside `backups/step5g-proof-07/leadforge-20261007T060053Z-0b41e720eb48/`. Removed after evidence capture. |
| 16 | Size | 32,044 bytes. |
| 17 | SHA-256 | `fa73593a20b767e00848e6b3dad17e4df90664d6cc1634101cf808d4c26c6f55`; archive, manifest and checksum sidecar matched. |
| 18 | Metadata | UTC time, custom format/schema version, artifact name, size/SHA, source identity/environment, PostgreSQL version, UTF8/en_US.utf8 locale, plpgsql, stored revision, TOC. No credential material. |
| 19 | Source fingerprint | All eight tables: sorted complete-row logical digests excluding password/session/CSRF hashes; counts, integrity, constraints, current analyses and metadata. Safe source/two-restore manifests retained locally. Constraint SHA `3a7a13e92ddc81e0e5edee170da7ab38d47c64eeb6941a169fe34a30d1270ee6`. |
| 20 | Backup duration | 2.657 seconds. |
| 21 | Inspection | Native pg_restore --list: 85 entries, schema and table data for all eight tables. Offline CLI also passed after source container removal. |
| 22 | Targets | Fresh template0 UTF8 DBs `leadforge_5g_restore_40a0498db4da_1` and `_2`, in only the drill-owned disposable container; no existing volume/runtime target. |
| 23 | Safety controls | Exact container/database confirmation; source/default target refusal; checksums/header/TOC before load; identity/version/empty-object checks; one transaction, exit on error, no owner/ACL restoration. Fence targets from concurrent users. |
| 24 | First restore | PASS: full fingerprints matched before application writes; all restored HTTP checks passed. |
| 25 | First duration | Restore 2.531 seconds; application assertions 3.390 seconds. |
| 26 | Repeat restore | PASS: same archive into a second independent fresh DB; full fingerprint and application assertions passed again. |
| 27 | Repeat duration | Restore 2.547 seconds; application assertions 3.375 seconds. |
| 28 | Alembic | Source and both restored DBs exactly `e5d4c3b2a1f0`; no pre-restore upgrade. Historical migrations untouched. |
| 29 | Counts | Both restores match source: Alembic 1, organizations 2, users 2, memberships 2, sessions 1, Leads 4, analyses 6, ingestion_jobs 1. Counts compared before test login/write mutations. |
| 30 | Relations | Zero orphaned memberships/leads/analyses/sessions/jobs, zero unvalidated constraints; normalized constraint definitions/digest matched. Only two equivalent membership-role cast expressions normalized; changed-role negative test passed. |
| 31 | Tenants | Organization IDs/relationships and row digests preserved; both restored backends returned 404 for foreign-tenant Lead access. |
| 32 | Lead/LeadAnalysis | IDs, associations, New/Meeting/Won/Lost, scores, Hot/Warm/Cold, processing fields, history, nullable legacy analysis and JSON digests matched. Sequence-backed post-restore Lead creation exceeded original maximum ID. |
| 33 | Current analysis | Latest timestamp then highest-ID tie rule matched SQL fingerprints and registered API; lead 1 selected analysis ID 5/score 90. |
| 34 | Unicode | UTF8 Bengali, Japanese, accented text and emoji preserved in logical digests and application/CSV assertions. |
| 35 | Timestamps | Created/updated/contact/follow-up/analysis/session/job timestamps preserved by complete-row comparison; synthetic UTC-naive values match current schema. |
| 36 | Authentication | Fresh login succeeded on each restored hardened backend; membership/session/CSRF path worked; logout returned subsequent 401. No hashes printed. |
| 37 | Workspace | Authenticated workspace response/selection passed on both targets. |
| 38 | Dashboard | Registered Dashboard snapshot checks passed on both targets. |
| 39 | Leads | List/detail and CSRF-protected sequence write passed on both targets. |
| 40 | Intelligence | Registered current-analysis/history behavior passed on both targets, with mock AI and no paid provider. |
| 41 | Reports | Registered report history/analytics checks passed on both targets. |
| 42 | CSV | Export succeeded, preserving Unicode and protecting formula-like synthetic legacy company value. |
| 43 | Session behavior | Session revoked in source after backup became valid after restore, as expected. Revoking all restored sessions blocked that old cookie with 401. Runbook recommends revocation while fenced before recovery access. |
| 44 | Invalid credentials | Real TCP bad-password backup failed exit 1, no completed dump and no leaked credential/URL. |
| 45 | DB unavailable | Missing database and missing container each failed exit 1 safely. |
| 46 | Unwritable output | Real obstructed destination (file in place of directory) failed exit 1 without completed dump. This is an output-write failure test, not a platform ACL simulation. |
| 47 | Corrupt archive | Damaged header with recomputed test-only sidecars rejected exit 1 before restore. Never re-sign real corrupt backups. |
| 48 | Checksum mismatch | Altered archive with original sidecars rejected exit 1 before restore. |
| 49 | Partial restore | Truncated archive passed checksum/header/TOC after test-only re-signing, but real pg_restore failed exit 1. Target proved empty afterward: single transaction rolled back partial work. Source/default/nonempty target cases also failed safely. |
| 50 | RPO | Provisional <=24 hours engineering target, not SLA; daily successful backup required. |
| 51 | RTO | Provisional <=2 hours after recovery decision, not SLA; realistic-volume infrastructure/application drills still required. |
| 52 | Frequency | Daily consistent backup minimum; shorten interval or assess separately authorized WAL/PITR if loss window is unacceptable. |
| 53 | Retention | Minimum rolling 30 days of successful daily backups; retain previous valid copy until replacement verified. Optional weekly/monthly extension; no automatic cleanup implemented. |
| 54 | Commercial retention | Documented 30-day product intent supported by proposed operational policy, not an implemented tier/scheduler/billing guarantee. Contract/deletion review remains. |
| 55 | Encryption | Production encryption at rest mandatory, with separately managed keys and tested recovery. Custom compression is not encryption. Local fixtures unencrypted/synthetic and dumps deleted. |
| 56 | Offsite | Recommend independent restricted, versioned/immutable offsite storage over authenticated encrypted transport. No cloud credentials, upload or connection configured. |
| 57 | Access | Restrict OS/storage/operator access; audit reads/deletes; treat dumps as sensitive because they contain leads and password/session hashes. |
| 58 | Roles | Separate runtime DML, migration/schema owner, backup read identity, and restore/provisioning administrator. Restore omits source ACL/ownership; deliberately provision target grants. Local superuser role remains. |
| 59 | Logs | Allowlisted JSON events, names, sizes, durations, SHA and SQLSTATE/query IDs; subprocess driver stderr suppressed. Failure cases and restored backend logs passed secret/token/CSRF privacy assertions. |
| 60 | SQLite/backend regression | 239 passed, zero failures/errors/skips, 2098 existing deprecation warnings, 76.08 seconds. Includes 19 new safety tests plus existing configuration/observability/security/CI suites. |
| 61 | PostgreSQL regression | 5 passed, zero failures/errors/skips, 81 existing warnings, 4.06 seconds; fresh base -> head and migration module/single-head checks passed in disposable DB. |
| 62 | Configuration | Existing isolated configuration regressions passed within full suite; explicit test/mock CI environments; both Compose configs validated without private dotenv. |
| 63 | Observability/privacy | Existing privacy/logging regressions passed within full suite, plus real restored-backend log checks and all failure-path output checks. No raw credentials/rows logged. |
| 64 | Security | Existing security/tenant/CSRF regressions passed; pip-audit and npm audit reported no known dependency vulnerabilities; Gitleaks scan and deliberate negative control passed. Known image advisories remain separately documented. |
| 65 | CI/actionlint | Existing 5F workflow unchanged; actionlint passed. Remote run still pending; no hosted CI claim. |
| 66 | pip check | No broken requirements. No requirements/lockfile change for 5G. |
| 67 | Frontend | Clean npm ci, lint and production build passed; zero audit vulnerabilities, eight existing lint warnings. No frontend behavior changed. |
| 68 | Docker/runtime | Local backend recovery image and frontend image builds passed (cached rebuilds, not new no-cache claim); image exclusions passed; Compose config and normal runtime HTTP/auth/import/intelligence/report/CSV smoke passed. |
| 69 | Final runtime | Original backend/frontend/PostgreSQL healthy; only frontend bound to 127.0.0.1:8080. Drill/regression/client/app containers removed, their owned ephemeral volumes cleaned. |
| 70 | SQLite SHA | Unchanged `217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a`. |
| 71 | Diff hygiene | git diff --check passed; meaningful 5G changes inspected. Existing unrelated dirty work preserved. |
| 72 | Created | `scripts/postgres_backup.py`, `scripts/verify_backup_recovery.py`, `tests/test_backup_safety.py`, `docs/BACKUP_RECOVERY.md`, this report. |
| 73 | Modified | `.gitignore`, `.dockerignore`, `README.md`, `docs/DEVELOPMENT.md`; only backup exclusions/documentation links added for 5G. |
| 74 | Generated artifacts | Exact drill-created step5g-proof-01 through -07 directories removed after evidence capture, including valid/corrupt/truncated dumps. Four safe JSON result/fingerprint files retained under ignored `backups/step5g-evidence-40a0498db4da/`. Local verification image tags retained. Unrelated backups/volumes preserved. |
| 75 | Limits | PostgreSQL 16.15, one Docker IPv4 network, trusted Docker host/dumps, no cluster-role export/PITR, 300s subprocess and 120s statement defaults, synthetic small-volume proof only. Checksums detect corruption, not adversarial authenticity. Known image advisories, shared login budget and local superuser role persist. |
| 76 | Deferred production | Scheduler, IAM/role provisioning, encryption/key recovery, offsite/immutable lifecycle, monitoring/alerts, capacity drills, remote CI, deployment/cutover, WAL/PITR if needed. No production-readiness claim. |
| 77 | Windows backup | Exact PowerShell template in runbook; see concise invocation below. Externally prompted password and explicit source/output required. |
| 78 | Windows restore | Exact PowerShell template in runbook; invocation below. Provision verified empty target first; exact confirmation required. |
| 79 | Linux backup | Exact portable Python invocation below; matching client containers launched automatically. Password externally injected. |
| 80 | Linux restore | Exact portable invocation below; no duplicate shell implementation. |
| 81 | Checksum command | Exact PowerShell/Get-FileHash and Linux sha256sum commands below; inspect independently checks sidecars/header/TOC. |
| 82 | Inspection command | Exact portable inspect command below, no running source or password required. |
| 83 | Validation sequence | Fence -> trusted backup/checksum/TOC -> new empty target -> atomic restore -> head/count/digest/relations/current/Unicode/timestamps/sequence -> revoke sessions -> mock backend readiness/login/workspace/Dashboard/Leads/Intelligence/Reports/CSV/tenant/logout -> record evidence. Commands and repeatable drill below. |
| 84 | Troubleshooting | Correct explicit readiness/identity/privileges/output; reject checksum/TOC errors; provision fresh target on refusal; verify empty rollback on pg_restore failure; quarantine post-load validation failures; recover schema before reviewed forward migrations. Never print dumps/DSNs or bypass safety controls. |
| 85 | Recommendation | Accept local Step 5G verification and stop here. Review/deploy storage, roles, encryption, scheduling and realistic restore validation only in separately authorized later work. |

## Exact operator invocations

Run from repository root. Replace placeholders explicitly. The runbook provides
secure password prompts and finally-block cleanup; never place passwords in argv.
Target databases must already exist, be empty and be fenced from applications.

```powershell
$pythonRecovery = (Resolve-Path .venv-ci/Scripts/python.exe).Path
# LEADFORGE_BACKUP_PASSWORD must be supplied externally; see runbook prompt.
& $pythonRecovery scripts/postgres_backup.py backup --container '<source-container>' --database '<source-database>' --user '<backup-role>' --environment production --output-dir '<external-backup-directory>'
& $pythonRecovery scripts/postgres_backup.py restore --container '<target-container>' --database '<fresh-recovery-database>' --user '<restore-role>' --environment production --artifact '<completed-backup.dump-path>' --confirm-target '<target-container>/<fresh-recovery-database>'
$artifact = '<completed-backup.dump-path>'
$manifest = Get-Content -LiteralPath ($artifact + '.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLower() -ne $manifest.sha256) { throw 'Checksum mismatch' }
& $pythonRecovery scripts/postgres_backup.py inspect --artifact $artifact
Remove-Item Env:LEADFORGE_BACKUP_PASSWORD -ErrorAction SilentlyContinue
```

Check `$LASTEXITCODE` immediately after each native CLI; runbook templates throw
on any nonzero exit. Do not continue validation/cutover after a failed operation.

```sh
# Externally injected LEADFORGE_BACKUP_PASSWORD; no tracing/private dotenv.
python3 scripts/postgres_backup.py backup --container '<source-container>' --database '<source-database>' --user '<backup-role>' --environment production --output-dir '<external-directory>'
python3 scripts/postgres_backup.py restore --container '<target-container>' --database '<fresh-recovery-database>' --user '<restore-role>' --environment production --artifact '<completed-backup.dump-path>' --confirm-target '<target-container>/<fresh-recovery-database>'
# From the trusted bundle directory:
sha256sum -c '<artifact-name>.dump.sha256'
python3 scripts/postgres_backup.py inspect --artifact '<completed-backup.dump-path>'
unset LEADFORGE_BACKUP_PASSWORD
```

Check each exit status; no production operation was executed with these templates.
The actual full recovery validation command executed successfully was:

```powershell
& .venv-ci/Scripts/python.exe -B scripts/verify_backup_recovery.py --output-dir backups/step5g-proof-07
```

For a repeat, build the local image using `docker build -t
leadforge-backend:5g-verification -f Dockerfile .` and choose a **new** output
directory. The drill itself creates/migrates/seeds its synthetic source, verifies
TCP readiness, backs up, restores twice, compares fingerprints before app writes,
exercises every application/failure assertion and removes its owned containers.

## Corrections made during verification

Early disposable attempts exposed locale lookup incompatibility, equivalent
CHECK deparsing, a registered route slash/status mismatch in the drill, and
localhost trust masking an invalid-password probe. The implementation was
corrected to query pg_database locales, narrowly canonicalize the known role
constraint, use the actual registered API shape and connect clients over private
TCP from a separate network namespace. The final complete drill and regressions
ran after those corrections. A PowerShell quoting error in the frontend image
inspection command was corrected with exact Python subprocess arguments; the
image content check then passed. No failed check was waived or described as a pass.

The restore CLI confirms the load/revision, not business-level recovery by itself.
The recorded drill proves business checks on this synthetic fixture; real incident
operators must complete the runbook validations before declaring recovery.
