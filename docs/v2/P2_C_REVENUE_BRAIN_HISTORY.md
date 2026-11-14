# Revenue Brain history and change detection v1

The Lead Details drawer contains Revenue Brain current state, latest-change
summary and bounded immutable Decision Ledger history. Current computations
are labeled as unrecorded; only an explicit **Record current decision** click
uses the existing P2-B POST. Opening, refreshing, expanding and paginating are
read-only. No migration, provider call, analytics or autonomous action is added.

## Backend contract

`GET /api/leads/{lead_id}/opportunity-decision/change` uses the existing
authenticated active-membership organization dependency and tenant predicates.
Missing and foreign Leads return the same 404. There are no caller-supplied
historical decision selectors; comparison always uses this Lead's scoped latest
record. Existing P2-B single-record tenant/Lead/UUID protections remain intact.

The typed response contains `current_decision`, `latest_recorded_decision`,
`change`, and `history`. Without history, latest/change are null, the first
history page is empty, and current computation remains available. The first
page is limited to five records; subsequent pages use the existing P2-B history
API. One composed GET needs four scoped SELECTs: current Lead, current analysis,
history count, and first page. No duplicated current-decision HTTP request or
per-record N+1 is needed. The service suppresses autoflush and never settles a
transaction or appends audit/business/ledger state.

`backend/decision/decision_change.py` owns the canonical pure comparison policy;
the comparison service only composes published reads. Version
`decision_change_v1` is derived policy metadata, not persisted schema. Delta is
current minus recorded; confidence subtraction uses decimal representations
without binary subtraction artifacts. Generation/recording times and UUIDs are
references, not semantic-change inputs.

Risk flags, missing signals and reasons use semantic sets, with deterministic
output ordering. Evidence identity uses structured signal, source, safe value
and effect; NFC and whitespace normalization are for comparison only. Distinct
values for the same signal are retained. Evidence source/signal coverage changes
are separately reported as provenance changes. Stored snapshot text is untouched.

## Direction and materiality

Positive dimensions: higher opportunity/fit/readiness/coverage confidence,
removed risks, resolved missing signals, and review no longer required.
Negative dimensions are their inverse. Both positive and negative changes mean
`MIXED`; only positive means `IMPROVED`; only negative means `DECLINED`.
No semantic changes means `UNCHANGED`. A recommendation-only, reason-only or
evidence-text-only change is `MIXED`, with no invented recommendation ranking.
Different policy versions or evidence-source contexts always mean `MIXED`;
score increases alone cannot establish improvement across those contexts.
This is a comparison classification, not verified buyer behavior or an outcome.

Material factors are centralized: absolute opportunity delta at least 5 points;
fit/readiness at least 10 points; coverage-confidence delta at least 0.05;
any recommendation, review, risk, missing-signal, policy-version or evidence
provenance change. Safe value/effect or reason differences are still shown but
are not independently material without one of these factors. Direction and
materiality are distinct: small improvements can be below material thresholds.

Structured output includes previous/current recommendation and review flags,
added/removed risks, newly missing/resolved signals, added/removed evidence and
reasons, material factors, and bounded deterministic explanations. Explanations
describe changes without asserting causal attribution or action execution.
Frontend code formats this result; it does not recompute business differences.

## Experience and limits

The existing JavaScript app uses JSDoc transport interfaces and a static
declaration for the existing parsed-JSON API client. No second UI framework,
TypeScript runtime migration or production dependency change is introduced.
The panel reuses workspace colors/buttons and the existing dialog focus trap;
native details/summary elements work by keyboard and are included in the trap.
Direction uses text and a glyph as well as color. Long evidence/reasons wrap.

Stored estimates remain labeled estimates, with a separate plain-language note
explaining neutral defaults. Coverage confidence is explicitly not a probability
of sale. Generated and recorded UTC timestamps are labeled separately; policy
versions are accessible on current and historical records. History respects
server order, uses five-record pages, and expands loaded data without requests.
Offset pagination retains P2-B semantics; refresh resets the first page after
an explicit recording or source edit.

An in-flight guard prevents rapid duplicate clicks; backend score deduplication
is unchanged. A confirmed POST triggers a read refresh, without optimistic fake
history. An uncertain POST result requires a read refresh before another record
attempt. Confirmed-write/failed-refresh guidance distinguishes these outcomes.
Two deliberate later recordings remain valid. Async response guards prevent
old Lead/workspace reads from replacing active state; development StrictMode
reuses the same component's in-flight initial read without a cross-tenant cache.
