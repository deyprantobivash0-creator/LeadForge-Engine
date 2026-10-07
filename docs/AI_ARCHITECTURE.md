# AI architecture

Step 4F exposes only a safe local readiness summary through Settings. It does
not report provider connectivity. Mock works in development/test and explicitly
opted-in synthetic staging under strict production configuration; Gemini
and Ollama can be configuration-ready while external service or local model
availability remains unverified. DeepSeek remains unavailable. Models, keys,
hosts, and raw environment values are not returned. Provider selection remains
server configuration, not a browser setting.

## Canonical processing path

```text
Tenant-owned Lead -> LeadProcessingService -> injected Provider Factory/Router
                  -> async LangGraph Lead Brain
                  -> Company Agent -> Contact Agent -> Intent Agent
                  -> validated structured results -> deterministic scoring
                  -> next-action recommendation -> atomic persistence
                  -> tenant-scoped intelligence API
```

This is now the registered synchronous route. The service verifies tenant ownership through an atomic claim before provider work. Current analysis/history selection is defined in Step 3C.

## Processing states and invariants

| State | Meaning |
| --- | --- |
| `pending` | Lead has not started an analysis attempt. |
| `processing` | One accepted attempt is in progress; duplicate requests have defined idempotent behavior. |
| `completed` | Validated result and deterministic score were persisted consistently. |
| `failed` | Attempt failed with a safe, inspectable error record and retry policy. |

The route permits pending/completed/failed to processing; an active processing attempt conflicts. A processing lease older than 15 minutes can be atomically reclaimed; attempt IDs prevent the old worker from completing or failing the replacement attempt. Completion and failure clear lease fields.

## Provider and result requirements

- Inject a provider selected by one factory/router. The mock path must support ordinary tests without network calls or paid providers.
- Keep workflow and agent calls async from endpoint/service through provider, or explicitly isolate synchronous work. Do not pass coroutines into scoring.
- Set bounded timeouts, retry only appropriate transient failures, classify provider errors, and define fallback policy. Record provider/model, attempt, latency, and safe failure metadata without logging prompts or secrets indiscriminately.
- Validate structured outputs against versioned schemas before scoring or persistence. Reject malformed JSON, missing required facts, invalid confidence ranges, and impossible score inputs. Evidence must identify support for claims; confidence is not evidence by itself.
- Score deterministically from validated inputs where product rules define the score. Record scoring version and reasoning inputs so results can be explained or recomputed. A recommendation must refer to validated evidence and have a clear provenance.
- Persist result, score, recommendation, status, and error metadata consistently, with tenant ownership and a defined Lead-to-analysis link. Prevent duplicate current analyses from racing.

## CURRENT implementation and debt

`backend/ai/providers/base.py` declares async text and structured generation. `router.py` selects Mock, Gemini, Ollama, or DeepSeek. Mock is local; DeepSeek raises `NotImplementedError`. Gemini uses synchronous SDK generation inside an async method; Ollama does not check HTTP status before reading JSON. Both structured paths assume valid raw JSON. Common retry, fallback, metadata, and cost rules are absent.

`backend/agents/` has async Company, Contact, and Intent agents. `AIOrchestrator` requires a `provider` constructor argument, while these agents instantiate it without one. `backend/graph/nodes.py` constructs agents at import time and invokes their async methods synchronously. `backend/workflows/lead_workflow.py` is another synchronous workflow. `backend/ai/workflow/lead_brain_workflow.py` currently defines only state, not an executable graph. These generations must be consolidated; do not decide which to delete before establishing tests and the canonical behavior.

The older `backend/graph`, `backend/agents`, and `backend/workflows` paths are unregistered and remain quarantined. The canonical `LeadBrainWorkflow` uses the single provider interface and performs meaningful company, contact, intent, and qualification stages. The legacy unregistered ingestion caller still needs tenant and Lead IDs before it can use `AnalysisService`.
# Step 3C persistence boundary

The registered route uses the selected provider. New analysis persistence validates a
structured `final_decision` with a 0–100 integer score and canonical priority,
then requires a tenant-owned Lead. Existing deterministic scoring in
`backend/decision/lead_scorer.py` owns the 80/60 Hot/Warm/Cold thresholds and
the 40/25/35 component weights.
Do not infer new fields from absent `result` keys.

Processing uses three short transactions: atomically mark `processing` and commit;
run the provider outside a transaction; validate/persist analysis and mark
`completed` together. On failure, mark `failed` in a separate transaction.
The previous successful analysis remains current. The graph validates bounded
component assessments and exact `lead_data` evidence; `derived` evidence is
explicitly labeled. It does no web enrichment. The application computes final
score as 40% company fit + 25% contact quality + 35% buying intent, rounded
half up; >=80 is Hot, >=60 Warm, otherwise Cold. Only transient provider
availability/timeouts receive at most one retry by default, with no delay;
malformed output is not retried. Each call has a configurable finite timeout.
`MockProvider` returns only an insufficient-evidence assessment and is blocked
outside development/test unless `LEADFORGE_STAGING=true` explicitly opts strict
production configuration into synthetic mock staging. Gemini uses the Google Gen AI SDK asynchronously;
Ollama uses a finite-timeout local HTTP call. Both require a manual smoke test.
DeepSeek is explicitly unsupported. Background jobs, cost controls, and human
review of model-derived evidence remain future work.
