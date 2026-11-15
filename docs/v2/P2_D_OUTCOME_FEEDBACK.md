# Decision outcome feedback

P2-D adds later, manually reported evidence to a specific immutable Decision
Ledger UUID, scoped to its original organization and Lead. It does not mutate
Lead status, scores, recommendations, decision-time evidence or audit taxonomy.
No provider, learning pipeline, integration or autonomous action is involved.

## Contract and interpretation

GET/POST `/api/leads/{lead_id}/opportunity-decisions/{decision_id}/outcomes`
reuse active-membership authorization and the existing user/CSRF write boundary.
POST accepts only `kind`, aware `observed_at`, and optional nullable `note`.
Kinds reuse lifecycle vocabulary: Contacted, Qualified, Meeting, Won, Lost.
New is not an observed post-decision result. Notes permit at most 1,000
characters and reject NUL. Observation must be at or after decision recording
and no later than server recording time. Missing, mismatched and foreign
decision/Lead combinations return the same 404; invalid payload/time is 422.

POST returns 201 with the outcome UUID, organization/Lead/decision identifiers,
authenticated recorder user ID, observation time, server recording time and
`manual_user_report` source. User-supplied actor/tenant/source fields are rejected.
All valid active human membership roles may report, matching explicit decision
recording; machine principals cannot report. Tenant checks remain SQL predicates.

GET returns `items`, `total`, `limit`, `offset`, and `effectiveness`. Pagination
defaults to 20, permits 1–100 rows and offset 0–100000000. Order is observation
time descending, then recording time and UUID descending. The interpretation
uses the latest observation across all pages, not the requested page alone:

- No observations: Outcome pending.
- Contacted: Inconclusive (activity does not demonstrate usefulness).
- Qualified, Meeting, Won: Positive outcome.
- Lost: Negative outcome.

These labels summarize manually reported business results, not whether a prior
recommendation was correct or caused the result. Conflicting or evolving reports
remain visible. An older observation entered later does not override a newer
observation. No numeric effectiveness score or automatic model learning is claimed.

## Persistence and tradeoffs

The closed security audit model cannot safely hold this business vocabulary.
`decision_outcomes` is an append-only child of the existing Decision Ledger,
not another decision-history model. A composite FK enforces organization, Lead
and decision ownership together; the referenced ledger gets an additive unique
index. Recorder IDs reference Users. Service-owned transactions settle each write.
ORM and SQLite/PostgreSQL triggers reject outcome UPDATE/DELETE. Existing decision
immutability triggers remain intact. No decision rows or existing user data are
backfilled or rewritten.

This first slice has no edit/delete or correction/retraction endpoint. Mistaken
entries remain permanent; later observations append rather than silently replace
them. A formal supersession/retraction policy needs separate future design before
introducing corrections. The UI warns users to check evidence before confirming.

Revision `72b6a8d9e014` follows `31e5e19bd71f`. Upgrade adds only the new table,
indexes and triggers. Downgrade destroys outcome evidence, removes those objects,
and retains existing decision rows. Migration verification uses disposable DBs.
The working application database is not migrated in this local implementation;
deployment/migration execution remains separately gated.

## Lead Details

Each expanded recorded decision contains an initially closed Outcome evidence
section. Opening it loads that decision's scoped outcomes, without changing
P2-C's current/comparison/history requests. Users choose a kind, enter a local
observation timestamp, optionally add a note, and explicitly confirm. UTC display
separates observation from recording. Notes render as text. Loading, empty,
failure/retry and bounded Load more states are provided. A synchronous in-flight
guard blocks duplicate submits; unconfirmed writes require explicit read refresh
before another attempt. No optimistic outcome history is fabricated.
