# Decision evaluation: observed association

P2-E reads durable Decision Ledger and P2-D outcome rows. It never evaluates
unsaved computations, Lead lifecycle status, provider guesses or external data.
It changes no scores, recommendations, prompts or outcomes. No migration or new
dependency is needed; migration 72b6a8d9e014 remains unapplied to the working DB.

## Policy latest_observation_v1

Each tenant-owned recorded decision is eligible and counts once. Its outcome is
the latest by observed_at DESC, recorded_at DESC, UUID DESC, exactly as in P2-D.
Older conflicting observations remain in history; there is no correction or
retraction support. A later-entered older observation does not supersede a newer
observation. This policy is a summary of a timeline, not a claim that prior
evidence disappeared or that the latest report is verified truth.

Qualified, Meeting and Won contribute positive evidence; Lost contributes
negative evidence; Contacted is inconclusive. There is no separate neutral kind
in P2-D and none is invented here. No outcome means pending, never negative.
Evaluated + pending = eligible. Positive + negative + inconclusive = evaluated.
Category totals use the stored recommendation enum and reconcile with totals.
Policy versions are not ranked or declared comparable in accuracy: these are
observed category counts across the stored all-time sample only.

Coverage is evaluated / eligible. With zero evaluated decisions the API returns
null coverage and the UI shows counts and an honest no-evidence message, not a
failure percentage. Counts always expose denominators. Every nonzero sample is
labelled Limited evidence: this first slice makes no statistical-strength claim
or arbitrary significance threshold. No category is ranked as objectively better.

## Read-only API and performance

GET /api/dashboard/decision-evaluation returns totals, coverage, evidence context,
policy version, all-time window and the six canonical recommendation categories.
It rejects query filters. GET /api/dashboard/decision-evaluation/evidence accepts
only limit (1–100, default20) and offset (0–100000000, default0), returning a
bounded page of decision/outcome IDs, Lead ID, recommendation and separate
decision-recorded, observed and outcome-recorded timestamps. has_more uses one
extra row. There is no unbounded record payload or outcome-note export.

Both routes use authenticated active membership and organization predicates on
both sides of the join, including organization/Lead/decision matching. No caller
organization selector is trusted. The repository ranks outcomes in SQL and each
response executes one SQL statement; no N+1 and no persisted aggregates. Summary
and detail are separate live reads and may differ under concurrent recording.
The UI discloses that limit and offers refresh. No cross-request snapshot promise
is made. Offset paging shares the existing product's concurrent-insert limits.

## Experience and scope

Intelligence includes a collapsed evaluation section, loaded on explicit opening.
It presents counts, category denominators and limitations without decorative
charts or percentages. A bounded evidence page exposes provenance IDs and opens
the existing Lead Details view to inspect decisions and outcomes. Loading,
empty, partial evidence, errors and retry are explicit; no placeholder metrics
are fabricated. Existing workspace remounting isolates tenant state.

This is deterministic evaluation for human interpretation. It does not establish
causation, recommendation correctness, accuracy, conversion probability or model
learning. It introduces no write API, migration, analytics warehouse, autonomous
action, integration, correction or retraction.
