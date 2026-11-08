# Revenue Brain opportunity decisions v1

`GET /api/leads/{lead_id}/opportunity-decision` requires the existing authenticated
session and active membership selected by `X-Organization-ID`. Missing and foreign
leads return the same 404. The typed response is `OpportunityDecision`; all customer
responses retain `Cache-Control: no-store`. No CSRF token is required for this GET.
The shared path contract accepts positive signed int64 IDs. PostgreSQL currently
stores int4 IDs: values above its physical maximum return the same missing-lead
404 without an overflowing Integer bind. SQLite retains its int64 lookup range.

The read service reuses `LeadRepository.get_lead_by_id` and
`LeadAnalysisRepository.get_current_for_lead`: at most two tenant-scoped reads,
latest linked analysis ordered by `created_at DESC, id DESC`. It suppresses
autoflush, does not settle the caller's transaction, and writes no business,
audit, authentication, session, or decision-history state. No migration is needed.

## Available evidence and limits

The model has company, email, source, optional industry, lifecycle, processing
state, and linked company/contact/intent assessments. There is no configured
target ICP, role, size, business-need field, or observed engagement/intent feed.
Company-fit means the **stored company assessment**, not verified ICP alignment.
Intent means a **stored estimate**, not an observed buying event. Presence of a
company or email contributes only to signal coverage; neither proves fit,
deliverability, decision-maker status, or purchase readiness.

The latest result must validate as the existing `LeadBrainResult`. Its final
score/priority must agree with both persisted analysis columns and the existing
`LeadScorer` (40/25/35, half-up rounding, 80/60 Hot/Warm thresholds). The analysis
must belong to the same tenant/lead and match its company/email snapshot. A
component needs nonempty evidence referencing present current Lead fields;
`lead_data` values must match exactly. Derived evidence is explicitly weaker.
An unsupported component is unknown, even when its stored score is zero. Legacy
JSON, inconsistent scores, or changed evidence never become invented facts.
Unsupported components also disqualify the combined qualification factor.

No raw company, email, notes, arbitrary summaries, provider reasoning, or auth
values are returned in decision evidence. Entries use allowlisted safe signal
summaries and scores. Existing lead/analysis scores and lifecycle remain intact.

## Versioned deterministic policy

The canonical policy is `revenue_brain_v1` in
`backend/decision/opportunity_policy.py`. All scores use integer half-up rounding.

| Factor | Definition |
| --- | --- |
| Fit | Supported stored company assessment; unknown uses a neutral 40 prior. |
| Readiness | 70% supported stored intent assessment + 30% lifecycle proxy. |
| Lifecycle proxy | New 0; Qualified 40; Contacted 60; Meeting 90; Won/Lost 0; unknown 40. |
| Qualification | Validated existing combined qualification; unknown uses 40. |
| Coverage | Available critical signals weighted as below, independent of score size. |
| Opportunity | 35% fit + 35% readiness + 20% qualification + 10% coverage. Closed Won/Lost overrides to 0. |

Unknown priors preserve uncertainty rather than equating absent evidence with
negative evidence. Missing signals are explicit and prevent preparation advice.
No elapsed-time decay, randomness, external provider, network, or LLM is used.
Only `generated_at` varies between identical stored-state decisions.

Confidence weights: company presence .15, contact presence .15, each supported
company/contact/intent assessment .20, known lifecycle .10. Assessment provenance
quality is .8 when it includes directly matching Lead evidence and .4 when all
support is derived. This is evidence completeness/provenance confidence, not a
calibrated probability of sale. Fully covered directly backed estimates give
.88 confidence; complete derived estimates give .64. Advanced lifecycle
(Qualified/Contacted/Meeting) with intent below 30 flags conflict and subtracts
.25. Invalid/stale/unknown lifecycle/in-progress context subtracts .15 once.
The result is clamped to [0,1] and rounded to two decimals.

## Recommendations and review

Recommendations never execute actions. Apply these rules in order:

1. Won/Lost: `DEPRIORITIZE` (not an active opportunity).
2. Conflicting, invalid, stale, unknown-lifecycle, or in-progress context: `HUMAN_REVIEW`.
3. Missing critical signals: `RESEARCH_MORE`.
4. Confidence below .65: `HUMAN_REVIEW`.
5. Supported fit below 30 or opportunity below 35: `DEPRIORITIZE`.
6. Opportunity at least 70 and readiness at least 65: `PREPARE_OUTREACH`.
7. Readiness below 65: `QUALIFY`.
8. Otherwise: `NURTURE`.

Review is required for missing, conflicting, uncertain, or low-confidence context;
it is not required merely because an opportunity is strong or weak. A closed
lead may still need data review while its recommendation stays deprioritized.
Risk and missing-signal enums distinguish unsupported estimates, stale/invalid
analysis, low assessed fit, unknown lifecycle, and incomplete coverage.

Scores are 0–100, confidence 0–1 (finite); reasons ≤12 ×240 characters, evidence
≤12 with bounded signal/value/effect text, risks ≤8, missing signals ≤6. The
schema forbids extra fields and exposes the policy version and aware UTC time.

P2-A adds no frontend, autonomous loop, outreach, lifecycle transition, external
action, or decision ledger. Persistence/history belongs to a separate P2-B design.
