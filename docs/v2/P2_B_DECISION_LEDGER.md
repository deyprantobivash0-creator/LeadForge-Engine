# Decision Ledger v1

The ledger records explicit Revenue Brain decisions as immutable tenant/lead
history. It stores the exact canonical P2-A decision, including its policy
version, three scores, confidence, recommendation, review flag, reasons,
evidence, risk flags, missing signals, and decision generation time. Recording
adds a UUID4 identity and a separate aware UTC recording time. Historical reads
use stored content; they do not recompute against current lead data or policy.

## API

All routes use the existing authenticated session and active organization
membership selected by `X-Organization-ID`. Customer responses retain the
existing `Cache-Control: no-store` policy.

| Method and path | Behavior |
| --- | --- |
| `GET /api/leads/{lead_id}/opportunity-decision` | Existing read-only P2-A computation; creates no history. |
| `POST /api/leads/{lead_id}/opportunity-decisions` | Compute once, persist that snapshot, return typed record with status 201. |
| `GET /api/leads/{lead_id}/opportunity-decisions` | Stored history, newest first, `recorded_at DESC, id DESC`. |
| `GET /api/leads/{lead_id}/opportunity-decisions/{decision_id}` | One stored record scoped to both organization and lead. |

POST requires the existing browser CSRF protection and a human execution
principal. It accepts no body or an empty JSON object; extra fields are rejected.
Clients cannot submit scores, tenant identifiers, policy versions, or arbitrary
snapshot metadata. History uses `limit` (default 50, range 1–100) and `offset`
(default 0, range 0–100000000), returning `items`, `total`, `limit`, and `offset`.
Missing and foreign leads return the same 404. Missing, foreign, or wrong-lead
record IDs return the same 404. UUID identity alone never grants access.

Repeated explicit POSTs append separate events, even for identical decisions.
There is no established generic POST idempotency framework to reuse. A client
retry can therefore create another record; there is no score-based deduplication.
There are no edit/delete endpoints, automatic recordings, or synthetic backfill.

## Boundaries and storage

`DecisionLedgerService` owns one published E02 transaction. It validates the
typed human principal and fresh active membership, acquires the tenant-scoped
lead through the published governed lock, calls `OpportunityDecisionService`
once, constructs an explicit bounded snapshot, and asks the ledger repository
to insert and flush. E02 settles the operation. The standalone return DTO is
built before settlement, with no post-commit scoring or ORM refresh.

The repository contains scoped insert/history/single-record SQL, with no scoring
or independent settlement. Snapshot mapping explicitly allowlists fields. It
copies typed JSON values and revalidates primitive nested data before insertion.
It excludes raw lead/contact fields, requests, provider payloads, sessions,
credentials, and arbitrary ORM serialization. P2-A's distinction between stored
estimates and missing/default policy priors survives unchanged.

One `decision_ledger` table stores bounded scalar fields and JSON collections.
Application validation bounds list lengths, text, enums, finite confidence and
integer scores; database constraints also enforce required fields, ranges,
domains and serialized JSON size limits. The query index is
`(organization_id, lead_id, recorded_at, id)`. A composite foreign key references
`leads(organization_id, id)`, preventing cross-tenant lead association. Both
organization and lead deletion use `RESTRICT`, consistent with retained linked
analysis history. No destructive cascade is introduced.

ORM update/delete guards and migration-installed SQLite/PostgreSQL triggers
reject mutation of persisted rows. This protects ordinary application writes,
including SQL UPDATE/DELETE that bypass ORM events. A privileged database owner
can still change schema, disable guards, truncate, or drop tables; this is not a
cryptographic or privileged-operator tamper-proof archive.

Migration `31e5e19bd71f` follows `5d59e6268f43`; published migrations are unchanged.
It adds only this empty table, constraints, index, and immutability guards.
Downgrade explicitly removes the ledger and destroys its history; it is tested
only on owned disposable databases. Production rollout needs its own review.

## P1 interaction and scope

The published P1 success/denial audit catalog is closed to lead creation,
lifecycle changes, and imports. Recording a decision has no existing applicable
action identifier or audit event. This increment leaves that catalog and P1-G
recorders unchanged instead of mislabeling a ledger event as an existing action.
The record command uses typed human identity, fresh membership and request CSRF.
An expanded permission/audit taxonomy needs a separately reviewed policy change.

Recording uses deterministic local P2-A scoring. It invokes no provider/LLM,
outreach, webhook, CRM change, qualification update, or lifecycle transition.
Frontend history views, analytics and autonomous actions are outside P2-B.
