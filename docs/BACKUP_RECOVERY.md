# Backup and recovery

Step 5G provides one PostgreSQL-native backup/inspection/restore CLI and a real
synthetic recovery drill. It does not deploy, schedule production jobs, upload
backups, replace production credentials or make LeadForge production-ready.
See [verification evidence](STEP_5G_VERIFICATION.md) and [database policy](DATABASE.md).

## Scope and format

The whole application PostgreSQL database is backed up: organizations, users,
memberships, server-side auth sessions, Leads, LeadAnalysis history, the existing
IngestionJob table, sequences, indexes, constraints and `alembic_version`.
The current registered CSV preview/confirm flow parses bytes in memory and stores
Leads in PostgreSQL; it does not retain uploaded files or a separate file store.
Settings exposes derived configuration, not a persisted configuration store.
IngestionJob is a legacy schema capability rather than registered import history;
its existing records are nevertheless included. No registered customer data
directory or required PostgreSQL extension was found; the drill verifies only
the default `plpgsql` extension. Reassess scope if file storage/extensions arrive.

Images, source, frontend assets, host virtual environments, node_modules, temporary
files, caches and logs are reproducible or outside database recovery scope. Git
source/configuration procedures and secret provisioning must be recovered
separately. Existing historical SQLite snapshots and `leadforge.db` are not used
or modified by these tools. This is not a filesystem/volume snapshot or a cluster
backup: PostgreSQL roles, tablespaces, postgresql.conf, pg_hba.conf and encryption
keys require separate protected infrastructure records.

Use PostgreSQL custom-format (`pg_dump --format=custom`), which is compressed,
inspectable using pg_restore and portable across architectures. PostgreSQL
documents [pg_dump consistency and archive formats](https://www.postgresql.org/docs/16/app-pgdump.html)
and [pg_restore transaction behavior](https://www.postgresql.org/docs/16/app-pgrestore.html).
A dump uses a consistent database snapshot while normal reads/writes continue;
manual table copying is not the backup mechanism. Coordinate migrations/DDL
during backup. Safe metadata is queried separately from the dump snapshot;
it describes source configuration, not a transactionally coupled row-count
promise. The drill quiesces its synthetic source and proves it did not change
between fingerprint and backup. Table count/digest manifests are verification
artifacts, not a substitute database export.

## Execution and safety model

`scripts/postgres_backup.py` needs Python 3.12 and Docker, not host PostgreSQL
clients or additional Python libraries. `pg_dump`, `pg_restore` and psql run
from the established digest-pinned `postgres:16.15` image. Connected clients
join the explicitly selected PostgreSQL container's single Docker IPv4 network
and connect to its inspected private IPv4 address on port 5432, with five-second connection timeout, bounded statement/lock
timeouts and no password prompts. Do not use an arbitrary older host client.
The client uses a separate network namespace rather than the server's loopback
listener, so the official image's local trust rule cannot bypass password checks.
Source/server/client version 16.15 is checked; future version support needs a
reviewed tool/image update and a new drill.

Backup requires explicit container, database, user, environment and output
directory. The password comes solely from `LEADFORGE_BACKUP_PASSWORD`, passed to
the client container through the variable name `PGPASSWORD`, never in shell
argv, filenames, manifests or logs. No private .env is loaded. Docker
administrators can inspect environment values and are a trusted boundary.
Never dump/render the environment or enable shell tracing around credentials.

Output uses an exclusive UTC timestamp + random-suffix bundle directory with a
`.dump`, `.dump.sha256` and `.dump.json`. No previous file is overwritten. The
archive is written in binary directly by Python subprocess I/O, avoiding
PowerShell text redirection/BOM conversion. An in-progress `.partial` is never
presented as a completed dump. Tools fsync output, inspect the table of contents,
validate SHA-256/metadata, then emit completion. Failure removes only files
allocated inside that new bundle; a nonzero exit is mandatory. An empty parent
directory may remain. A crash can leave partial files; treat them as failed,
never rename them into a success. Restore-test proof remains necessary even
when checksum and table of contents pass.

The manifest contains UTC creation time, PostgreSQL version, format, source
container/database, selected environment, encoding/locale, stored Alembic
revision, extension names, size, SHA-256 and inspected object names/count.
It contains no DSN, password, API key, bearer value or hash of an individual
credential. SHA-256 detects accidental corruption, not authenticity if an
attacker can replace both archive and manifest; protect the storage and trust
only known-source dumps. Restore executes archive-defined SQL, so do not accept
untrusted dumps merely because their checksum matches.

Restore expects a database that **already exists and is empty**, preferably
created from `template0` with UTF8 and the recorded collation/ctype. It never
drops, resets or cleans a database. It requires exact confirmation of
`container/database`, rejects the source database name and obvious normal/default
targets (`leadforge_dev`, `leadforge`, `postgres`, `template0`, `template1`),
validates the checksum/header/manifest and required schema/data entries, and
checks for existing user relations, functions, schemas or extensions. Explicit
confirmation does not bypass those refusals. A different alias is not permission
to use a live target; fence it from applications and concurrent operators.

`pg_restore --single-transaction --exit-on-error --no-owner --no-privileges`
provides atomic restore and avoids source-cluster ownership/ACL dependencies.
No `--create`, `--clean` or trigger-disabling shortcuts are used. Source ACLs are
omitted by pg_dump; restored objects belong to the restore identity. Provision
and verify the intended target role grants separately. A failed data restore
rolls back to the empty database; failure remains explicit. After a successful
archive load, stored Alembic revision must match the backup metadata. If a
post-load validation fails, quarantine that target; do not declare recovery.

## Storage, credentials and retention

Use an explicit external directory for production backup artifacts. Inside this
repository the CLI permits output only under ignored `backups/`, rejects
symbolic-link traversal, and will not write into source/public directories.
Local `backups/` is reserved for disposable synthetic verification. Dump,
metadata/checksum, backup and directory patterns are excluded by Git and Docker;
application Dockerfiles copy fixed code/asset paths. Nginx serves only its static
asset root; no backup directory or archive is served. Backup tools are operator
utilities, never HTTP endpoints or application startup tasks.

Full backups contain password hashes, leads, analysis and session digests and
must be treated as highly sensitive. Restrict operators/OS ACLs and storage
access, audit reads/deletes and separate normal runtime access from backups.
The local synthetic artifacts are unencrypted. Custom-format compression is
**not encryption**. Production requires encryption at rest (protected storage
or reviewed artifact encryption), separately managed/rotatable encryption keys
and a tested key-recovery procedure. No encryption keys are created here.
Production offsite transfer must use authenticated encrypted transport and
independent restricted storage, ideally immutable/versioned against accidental
deletion/ransomware. No S3/Drive/FTP/cloud connection or upload is configured.

Provisional engineering targets, not SLAs: RPO <=24 hours with daily consistent
logical backups; RTO <=2 hours after a recovery decision for the current single
database architecture. These are planning targets requiring realistic-volume
deployment drills; local synthetic timings do not establish production capacity.
If a 24-hour loss window is unacceptable, increase backup frequency and assess
WAL archiving/PITR in a separately authorized infrastructure phase.

Commercial product intent includes 30-day backups. Recommend a minimum rolling
30-day daily-success retention with verified restoration and offsite protection;
optional weekly/monthly retention can extend this, never silently shorten it.
Retain the previous valid backup until the replacement is verified and retention
is met. Legal/customer deletion rules and contract definitions still need review.
No tier/billing or local automatic deletion lifecycle is implemented. The drill
creates only synthetic artifacts; delete only its explicitly recorded directory
after recording safe evidence. Do not use git clean, global volume prune, or
wildcard cleanup over unknown backups.

The local superuser-style database role remains a limitation. Future deployment
must separate application DML role, migration/schema-owner role, backup read
role and restore/provisioning administrator. A dedicated backup identity needs
CONNECT and appropriate schema/table/sequence read privileges (and future
default grants), not general application DDL. Restore needs deliberate CREATE
permissions in the fresh target; reconcile target runtime grants afterward.
Do not give the application backup-storage or cluster-admin credentials.

## Session recovery policy

Sessions are included to prove full database recovery; the CLI preserves them
and does not silently change product semantics. An old backup can revive an
otherwise unexpired session revoked after the snapshot. The drill deliberately
demonstrates this, then verifies recovery-session invalidation. Recommended
disaster recovery policy: revoke **all** restored sessions while the database
is fenced, before users or old session cookies can reach the recovered app.
Authorized administrator SQL in the verified restore target:

```sql
UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE revoked_at IS NULL;
```

Require fresh login and verify the old cookie returns 401. This does not alter
password hashes or membership relationships. The backup itself remains intact.

## Operator recovery sequence

1. Declare the incident and fence writes/access. Identify source and target
   containers/DBs explicitly; preserve the damaged source for diagnosis.
2. Select a trusted completed backup within the loss window. Verify manifest,
   SHA-256 and pg_restore listing. Do not print row data, SQL payloads or secrets.
3. Provision a **new** UTF8 empty target with recorded locale and required
   extensions using a separate administrator. Verify identity/emptiness/grants.
4. Restore the archive into the explicitly confirmed fresh target. Prove the
   backed-up schema/revision/data before running any migrations.
5. Compare table counts, tenant relationships, constraints, IDs, historical/
   current analyses, Unicode and timestamps against expected evidence. Verify
   sequence-backed writes. Do not accept merely nonzero row counts.
6. Inspect `SELECT version_num FROM alembic_version;`. For the tested current
   backup this is e5d4c3b2a1f0 and no pre-restore upgrade is needed. If an older
   compatible archive is restored, first recover its stored schema, then apply
   reviewed forward Alembic migrations with the migration identity. Never edit
   archive content or historical migrations to upgrade it. No indefinite old
   backup/backward application compatibility promise is made.
7. Revoke restored sessions while fenced; verify fresh synthetic/operator login
   and old-cookie denial. Start an isolated backend against the restored DB with
   mock AI for testing; verify readiness, workspaces, Dashboard, Leads,
   Intelligence/history, Reports/CSV, tenant denials and logout. Reconcile target
   permissions before any separately authorized deployment/cutover.
8. Record recovery time, backup identity and safe verification results. A checksum
   or restore exit alone is not a declaration of recovery. Stop here in 5G:
   production scheduling, deployment, DNS/TLS/cutover belong to later steps.

## Exact PowerShell commands

Replace angle-bracket values with explicit existing source/fresh target names.
Use a real operator-provisioned empty restore DB, not the source/runtime DB.
The password is prompted, never included in the command argument:

```powershell
$pythonRecovery = (Resolve-Path .venv-ci/Scripts/python.exe).Path
$sourceContainer = '<source-container>'
$sourceDatabase = '<source-database>'
$backupRole = '<backup-role>'
$backupDirectory = '<external-backup-directory>'
$passwordInput = Read-Host 'Backup DB password' -AsSecureString
$env:LEADFORGE_BACKUP_PASSWORD = [Net.NetworkCredential]::new('', $passwordInput).Password
try {
    & $pythonRecovery scripts/postgres_backup.py backup --container $sourceContainer --database $sourceDatabase --user $backupRole --environment production --output-dir $backupDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed' }
} finally {
    Remove-Item Env:LEADFORGE_BACKUP_PASSWORD -ErrorAction SilentlyContinue
}
```

Inspection is offline and requires no DB password or running source container:

```powershell
$artifact = '<completed-backup.dump-path>'
$manifest = Get-Content -LiteralPath ($artifact + '.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLower() -ne $manifest.sha256) { throw 'Checksum mismatch' }
& $pythonRecovery scripts/postgres_backup.py inspect --artifact $artifact
if ($LASTEXITCODE -ne 0) { throw 'Backup inspection failed' }
```

The restore identity/password can differ from the source. Provision the empty
target first; the tool deliberately has no destructive reset option:

```powershell
$restoreContainer = '<target-container>'
$restoreDatabase = '<fresh-recovery-database>'
$restoreRole = '<restore-role>'
$passwordInput = Read-Host 'Restore DB password' -AsSecureString
$env:LEADFORGE_BACKUP_PASSWORD = [Net.NetworkCredential]::new('', $passwordInput).Password
try {
    & $pythonRecovery scripts/postgres_backup.py restore --container $restoreContainer --database $restoreDatabase --user $restoreRole --environment production --artifact $artifact --confirm-target "$restoreContainer/$restoreDatabase"
    if ($LASTEXITCODE -ne 0) { throw 'Restore failed; recovery not verified' }
} finally {
    Remove-Item Env:LEADFORGE_BACKUP_PASSWORD -ErrorAction SilentlyContinue
}
```

## Exact Linux/container commands

Use an externally injected password (no private dotenv, command tracing or URL):

```sh
# LEADFORGE_BACKUP_PASSWORD is supplied externally by the operator.
python3 scripts/postgres_backup.py backup --container '<source-container>' --database '<source-database>' --user '<backup-role>' --environment production --output-dir '<external-directory>'
python3 scripts/postgres_backup.py inspect --artifact '<completed-backup.dump-path>'
python3 scripts/postgres_backup.py restore --container '<target-container>' --database '<fresh-recovery-database>' --user '<restore-role>' --environment production --artifact '<completed-backup.dump-path>' --confirm-target '<target-container>/<fresh-recovery-database>'
unset LEADFORGE_BACKUP_PASSWORD
```

These invoke the matching client container automatically. For standalone checksum
verification, enter the trusted bundle directory and run `sha256sum -c
<artifact-name>.dump.sha256`. The portable inspect command checks checksum,
manifest and native TOC together. Docker/path/quoting support is shared across
Windows and Linux; no duplicate shell implementation.

## Repeatable synthetic drill and CI relationship

Requires Docker, installed canonical backend/test requirements and matching app
image; it never uses existing volumes. Run from repository root:

```powershell
docker build -t leadforge-backend:5g-verification -f Dockerfile .
if ($LASTEXITCODE -ne 0) { throw 'Recovery backend build failed' }
& $pythonRecovery -B scripts/verify_backup_recovery.py --output-dir backups/step5g-new-drill
if ($LASTEXITCODE -ne 0) { throw 'Recovery drill failed' }
```

Linux: `python3 -B scripts/verify_backup_recovery.py --output-dir
backups/step5g-new-drill`. Output must be a new directory. The drill provisions
only its own --rm PostgreSQL container, creates synthetic source and independent
empty targets, migrates only the source, seeds two tenants, backs up, restores
twice, compares manifests, starts a hardened disposable backend per target and
exercises real HTTP behavior. It tests credential/service/output/corruption/
target/partial-restore failures with privacy assertions. It proves revocation
after backup can be lost, and that invalidating restored sessions works.
Its defaults briefly bind only loopback 55433 (synthetic PostgreSQL) and 58400
(synthetic backend); occupied ports cause failure, never stopping another app.
Each app is removed and the verified drill-owned PostgreSQL container/anonymous
volume is removed on exit. The normal :8080 runtime remains separate.

Fingerprint comparison preserves row values, IDs, timestamps and constraint
definitions. PostgreSQL can deparse the restored membership-role CHECK with
equivalent explicit text casts; only the two known equivalent expressions for
that specific constraint are normalized. A test rejects a changed allowed role.
Credential hashes are deliberately excluded from printable row digests; real
login/session checks verify their recovery without exposing them.

Client subprocesses have a 300-second default deadline. This is suitable for
the verified synthetic database, not a large production-capacity claim. Review
timeouts, disk capacity and restore duration before adopting this tool at scale.

Run the existing [CI reproduction commands](CI.md) for final SQLite/PostgreSQL,
configuration/privacy/security, frontend and container regressions. Focused
helper tests are included automatically by tests/; real recovery is not mocked
away. Recommend this real drill as a manual/pre-release check and a future
scheduled synthetic restore test after hosting is authorized. No production
backup test is added to each PR, no 5F restart or workflow deployment change.
Remote CI remains pending.

## Failure troubleshooting

| Failure | Safe response |
| --- | --- |
| Invalid credentials/privileges | Nonzero exit; externally supply correct backup/restore identity, verify CONNECT/reads/CREATE grants. No password/driver stderr is printed. |
| Unavailable PostgreSQL/container | Check explicit identity, running engine and authenticated TCP readiness; initialization's temporary Unix socket is not final readiness. |
| Output invalid/unwritable | Use explicit private directory/ACL, free space and a new bundle; no completed-looking dump survives normal failure. |
| Missing/mismatched sidecars/header | Stop before connecting to target; choose a trusted complete backup, never waive checksum or re-sign a real corrupt artifact. |
| TOC missing schema/data | Reject incomplete/selective/wrong-app archive. A readable list alone is not enough: test actual data restore. |
| Wrong/nonempty target | Provision a different verified fresh DB; exact confirmation never overrides source/default/nonempty refusal. |
| pg_restore data error | Atomic rollback is expected; verify target emptiness and nonzero exit. Quarantine anything with post-load validation failures. |
| Alembic mismatch | Inspect backed-up revision first; use a compatible application and reviewed forward migrations after restore, never historical rewrites. |
| App not ready/401/403 | Check target DSN privately, schema/head, expected fresh login/memberships/session revocation and explicit workspace selection; preserve tenant/CSRF controls. |
| Logs/privacy | Only allowlisted event fields, sizes, durations, names and SHA-256 are printed. SQLSTATE/query IDs identify psql failures without SQL/row values. Never upload dumps/raw logs in support requests. |

Known image advisories, shared login budget, local superuser role, manual deep
image scans and lack of production readiness remain unchanged. Production
scheduler/offsite storage/encryption/monitoring/IAM/capacity/cutover are deferred.
Stop after Step 5G; no Step 5H deployment or external upload.
