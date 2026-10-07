# Database and migrations

For the Step 5B local runtime, backend/migration containers connect to
`postgres:5432` on a private Docker network. A separate named volume preserves
runtime data; the 5A host workflow still uses `127.0.0.1:55432` and its original
volume. Application connections use bounded acquisition/connect timeouts and
pre-ping; migrations run as a one-shot startup prerequisite. See
[container runtime](CONTAINERS.md) for commands and safe disposable reset rules.

## CURRENT schema

Development uses SQLite through `backend/database/session.py`; `backend/core/config.py` defaults to `sqlite:///./leadforge.db`. The intended production database is PostgreSQL, but migration and runtime behavior there are **UNVERIFIED**. SQLAlchemy metadata uses a naming convention in `backend/database/base.py`, and `backend/models/__init__.py` registers the seven core models.

| Entity | Current role and ownership |
| --- | --- |
| `Organization` | Workspace identity, slug, plan, monthly lead limit, active flag. |
| `User` | Global account identity with normalized unique email, Argon2id password hash, active flag, and timestamps. No direct organization ID. |
| `OrganizationMembership` | Explicit user-to-organization link with owner/admin/member role, active flag, unique pair, and restrictive foreign keys. |
| `AuthSession` | User-owned revocable session with unique token digest, CSRF digest, expiry, last-seen and revocation timestamps. |
| `Lead` | Organization-owned contact/company record with lifecycle fields, score, priority, and processing status. Unique constraint on `(organization_id, email)` and tenant-oriented indexes. |
| `LeadAnalysis` | Organization-owned analysis snapshot with company/email, priority, score, JSON result, timestamp, and nullable tenant-constrained Lead link for historical backfill. |
| `IngestionJob` | Legacy organization-owned metadata model. Step 4D CSV import does not persist a job or use this model; durable import history remains future work. |

## Mandatory tenant and relationship rules

Every customer-owned entity must have clear organization ownership. Every customer-data query and mutation must receive `organization_id` from an authorized request context: authenticated user -> membership -> organization. Do not accept a caller-provided organization ID as authorization. A get-by-ID, update, delete, aggregate, AI result, import job, and background task all require the same scope. Test with at least two organizations and overlapping identifiers/data.

Step 3C establishes versioned history, a direct tenant-constrained Lead foreign key, and current selection by timestamp then ID. Step 3D implements processing claims and short transactions. Email-change
policy and broader background-job recovery remain open.

## Schema-change policy

SQLAlchemy models represent application schema; Alembic owns schema changes. Add a migration for every schema change. Do not use `Base.metadata.create_all()` as production schema management. Do not casually edit historical migrations once applied; assess forward repair migrations and data conversion explicitly. Validate both a clean database migration and an upgrade from representative existing data. Validate PostgreSQL migrations before production. Review nullability, foreign keys, unique constraints, indexes, and server defaults against ORM defaults.

Current revision chain: `9ed1e76d4c54` -> `e37cdcdf31dd` -> `24b5b28b09b7` -> `c3b2a1d0e9f8`. The new revision adds only identity, membership, and session tables. Disposable clean and populated SQLite upgrades and the new revision's downgrade pass; PostgreSQL remains unverified. The local development database was not migrated.

Identity timestamps follow the existing naïve UTC storage convention. New authentication code derives naïve values from timezone-aware UTC instants at the database boundary. Application defaults and database `CURRENT_TIMESTAMP` defaults cover creation; SQLAlchemy `onupdate` maintains `updated_at` on ORM updates, while direct SQL must set it explicitly. Membership foreign keys restrict deleting users or organizations while memberships exist, protecting organization data from user deletion; session rows cascade only when their user is deleted. The application SQLite engine now enables `PRAGMA foreign_keys=ON` on each connection; PostgreSQL behavior is unaffected. The unique email and token-hash constraints provide lookup indexes. The role and normalized-email checks are enforced in the database. Login and tenant authorization for registered Lead, Dashboard, and Report routes are active; analytics queries use SQL-level organization predicates.

## CURRENT migration risks

- The initial revision creates the entire schema if any one required table is missing, which can collide with a partially initialized database. Its legacy SQLite path rebuilds tables with assumptions about existing columns and data.
- The first revision explicitly rejects an existing non-SQLite database; PostgreSQL upgrades are unverified.
- Migration server defaults and ORM Python defaults are not aligned in all models. Direct SQL writes and schema comparison may diverge.
- A Step 3A read-only comparison found the local SQLite `organizations` table lacks ORM-declared `ix_organizations_id` and `ix_organizations_slug` indexes. The four table/column sets matched; broader constraint/default drift remains unverified.
- Several indexed primary keys and unique/index combinations deserve review for redundant indexes.
- `backend/database/init_db.py` invokes `create_all()` at import time; it must not become a deployment migration path.

No migration should be run against the development database merely to check documentation. Use disposable databases for migration tests and read-only inspection for local state.
# Step 3C analysis history

Revision `d4c3b2a1e0f9` follows auth revision `c3b2a1d0e9f8` and adds a
nullable `lead_analysis.lead_id`. The `(organization_id, lead_id)` foreign key
references a unique `(organization_id, id)` on `leads`, with delete restricted.
It permits many analyses per Lead. A tenant/Lead/date/ID index supports current
and history queries. Backfill joins on exact organization ID and email only
when exactly one Lead matches; missing or ambiguous rows remain unlinked and
are preserved. Unlinked rows never become current intelligence. New writes
require a valid Lead ID. Historical score/priority values are left unchanged;
normalizing those requires a separate audited data policy. Existing naive UTC
timestamps remain; timezone-aware storage requires a later migration.

## Step 3D processing claim

Revision `e5d4c3b2a1f0` follows `d4c3b2a1e0f9` and adds nullable
`leads.processing_started_at` and `leads.processing_attempt_id`. Existing Lead,
analysis, auth, and membership rows are preserved. A conditional tenant-scoped
UPDATE claims a Lead unless an active lease is younger than 15 minutes.
Completion and failure require the matching attempt ID. The previous successful
analysis is never deleted. There is no automatic background sweep; a stalled
attempt becomes claimable on the next process request.

# Step 5A PostgreSQL baseline

`docker-compose.yml` defines a disposable PostgreSQL 16.15 development
database on `127.0.0.1:55432`. The application URL is
`postgresql+psycopg://leadforge_dev:leadforge_dev_only@127.0.0.1:55432/leadforge_dev`.
These credentials are for local development only. SQLite remains supported for
lightweight development and the default isolated suite. PostgreSQL tests live
in `tests_postgres/` and use a separately created, randomly named test database
on that local server. Migration, test, reset, and SQLite return commands are in
[Development](DEVELOPMENT.md).

Current storage uses naive UTC timestamps. The current Lead intelligence query
orders linked analysis rows by `created_at DESC, id DESC`; Dashboard v2 ranks
one current analysis per Lead, while Reports v2 counts historical analysis
events. Both scope organization in SQL. The database enforces unique
`(organization_id, email)` for Leads and a composite tenant/Lead foreign key
for linked analyses. Import confirmation uses savepoints around individual
Lead inserts so PostgreSQL uniqueness resolves concurrent duplicate attempts.

This is a development database baseline, not a production database operating
plan. Pool limits, timeouts, migration coordination, backup/restore procedures,
and report/export capacity need review before production deployment.
