# E01 — durable execution requirements and decision matrix

Date checked: **2026-10-12** (Asia/Dhaka). Evaluation is architecture analysis, not an executed benchmark or procurement approval. Account-specific facts remain **UNVERIFIED — REQUIRES HUMAN CONFIRMATION**. [ADR-001](adr/ADR-001-DURABLE-EXECUTION.md) owns the decision; [baseline](E01_EXECUTION_BASELINE.md) owns code evidence.

## Verified source register

Only official sources were used for platform claims. IDs below are reused by this package; recommendations and scores are LeadForge judgments. Public docs do not verify this customer's infrastructure or purchase eligibility.

| ID | Source | Bounded verified fact used |
| --- | --- | --- |
| T1 | [Temporal execution](https://docs.temporal.io/workflow-execution) | History/replay provides durable workflow progress; workflow ID, run ID and namespace are distinct |
| T2 | [Temporal activities](https://docs.temporal.io/activities) | External operations belong in activities and should be idempotent; workflow durability does not make effects exactly once |
| T3 | [Python client](https://docs.temporal.io/develop/python/client/temporal-client) | Python client/worker connects to namespace endpoint; Cloud gRPC endpoint uses port 7233; TLS with API key or mTLS documented |
| T4 | [Cloud connectivity](https://docs.temporal.io/cloud/connectivity) | Public/private connectivity options exist; customer network path must be validated |
| T5 | [Cloud API keys](https://docs.temporal.io/cloud/api-keys) | Service-account API keys can be rotated/revoked; key expiry/revocation affects worker connections |
| T6 | [Worker versioning](https://docs.temporal.io/worker-versioning) and [Python versioning](https://docs.temporal.io/develop/python/workflows/versioning) | Version-aware worker deployment and replay-compatible changes are required; exact selected SDK feature compatibility still needs a spike |
| T7 | [Python testing](https://docs.temporal.io/develop/python/best-practices/testing-suite) | Time-skipping test server and full local-server testing are available; they test different runtime behavior |
| T8 | [Production deployments](https://docs.temporal.io/production-deployment) and [self-hosted guide](https://docs.temporal.io/self-hosted-guide) | CLI dev server exists; self-hosted production service requires separate operational responsibility |
| T9 | [Cloud pricing](https://docs.temporal.io/cloud/pricing) | Actions, active/retained storage and support-plan charges form the invoice; current Developer plan has no base fee and 10% of usage spend; Business greater of USD 500/month or 10%; Actions start at USD 50/million |
| T10 | [Python workflow messages](https://docs.temporal.io/develop/python/workflows/message-passing) | Workflow signals/updates provide message-driven interaction; LeadForge approvals remain domain records |
| T11 | [Temporal namespaces](https://docs.temporal.io/namespaces) | Namespace scopes workflow identifiers/history/configuration; it does not replace LeadForge resource authorization |
| T12 | [Cloud regions](https://docs.temporal.io/evaluate/cloud/regions) | Region choices exist; no LeadForge region/HA/data-residency selection is verified |
| R1 | [Render free limits](https://render.com/docs/free) | Free web services idle after 15 minutes without inbound traffic; filesystem ephemeral; free PostgreSQL expires after 30 days; free web capacity/traffic restrictions apply |
| R2 | [Render workers](https://render.com/docs/background-workers) | Background workers run continuously and poll work without public inbound request handling |
| R3 | [Render compute plans](https://render.com/docs/compute-plans) | Worker/private-service table has paid plans beginning at `0.5c-512mb`, not a `free` worker plan; current plan names differ from older names |
| R4 | [Render deploy lifecycle](https://render.com/docs/deploys) | Deploy/shutdown behavior needs cooperative draining; finite termination grace is not a durable task guarantee |
| R5 | [Render pricing](https://render.com/pricing) | Public pricing entry point; exact chosen worker cost/discount/account quote not confidently extracted: UNVERIFIED |
| P1 | [PostgreSQL 16 SELECT](https://www.postgresql.org/docs/16/sql-select.html) | SKIP LOCKED supports queue-like row consumers but yields an inconsistent view and is not a generic correctness/ordering guarantee |
| C1 | [Celery stable tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html) | Late acknowledgment and worker-loss settings affect redelivery; idempotent tasks are application responsibility |
| C2 | [Celery stable calling](https://docs.celeryq.dev/en/stable/userguide/calling.html) | Distant ETA/countdown tasks can reside in worker memory and Redis visibility timeout can cause redelivery; not the proposed multi-day schedule store |
| Q1 | [RQ scheduling](https://python-rq.org/docs/scheduling/) | Scheduled/repeated jobs require scheduler-enabled workers; job retry/repetition is not an approval/business state machine |
| L1 | [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Checkpointers persist thread state; memory-only checkpoint storage does not survive restart; current LeadForge graph has no checkpointer |

No quoted credentials or credential-bearing connection strings are included. API keys/certificates are credential *types*, not values. Failed documentation URLs were replaced with verified canonical pages; no fact relies on an inaccessible page.

## LeadForge requirements matrix

P0 = required before any autonomous external effect; P1 = required before paying-customer production scale. An engine cannot pass a business gate merely because it supplies a related SDK feature.

| Group / ID | Requirement | Priority | Acceptance evidence required later |
| --- | --- | --- | --- |
| A / D1 | Process/machine crash and redeploy survival | P0 | Kill before/after every durable boundary; run resumes from saved state without guessed success |
| A / D2 | Provider outage recovery | P0 | Bounded retry/circuit break with preserved result, budget and recovery owner |
| A / D3 | Hours/days/weeks of waiting | P0 | Seven-day approval and fourteen-day nurture use persistent wait state, no continuously occupied request/thread |
| B / F1 | Timers and scheduling | P0 | Durable due time, timezone rules, missed-due behavior and bounded lateness measured |
| B / F2 | Retry/backoff/timeouts | P0 | Per-activity deadlines/attempt caps/jitter and permanent-vs-transient classification |
| B / F3 | Cancellation and pause/resume | P0 | Queued work blocked, in-flight effects reconciled; cancellation is not unsending |
| B / F4 | Branch/parallel/child work | P1 | Fan-out/fan-in retains tenant scope, budget and bounded concurrency |
| B / F5 | Workflow/code versioning | P0 | Historic histories replay under intended worker version; incompatible rollout blocked |
| C / H1 | Approval pause, reject, resume | P0 | Approval is persisted independently of worker availability; reject performs no effect |
| C / H2 | Expiry/edit/re-proposal | P0 | Exact payload/version binding; expiry and modified target invalidate old decision |
| C / H3 | Stale approval prevention | P0 | Live grants/context/suppression/cost/policy rechecked at dispatch |
| C / H4 | Organization stop/campaign pause | P0 | Persist stop epoch first; block future claims even if engine unavailable |
| D / X1 | Immutable ActionIntent/effect ledger | P0 | Stable semantic key, fenced attempts and monotonic effect status |
| D / X2 | Provider idempotency and ambiguity | P0 | Timeout-after-accept reconciles; provider without lookup/idempotency requires operator decision |
| D / X3 | Outbox/inbox/replay-safe activities | P0 | Duplicate command/webhook five times causes one logical transition; lost acknowledgment recovers |
| D / X4 | Transaction separation | P0 | Domain+outbox atomic; no DB transaction held across network/approval/timer; no fictitious DB-engine atomic commit |
| E / M1 | Tenant/org/principal identity | P0 | Immutable authenticated tenant context, scoped IDs and revoked grants reject tool effects |
| E / M2 | Worker/tool permissions | P0 | Least-privilege activity services; no agent SQL/raw credentials; missing context fails closed |
| E / M3 | Quotas/fair scaling | P1 | Tenant admission and provider concurrency reservations cannot be bypassed with many workflows |
| F / O1 | History/status/correlation | P0 | Run/action/attempt/provider/outcome linked by IDs; stale UI projection detectable |
| F / O2 | Retry/failure metrics/tracing | P0 | Queue age, deadline misses, approval age, unknown effect and budget liability visible |
| F / O3 | Enterprise audit linkage | P0 | Policy/approval/payload receipts persist in domain audit, independent of engine history retention |
| G / G1 | Local development/CI | P0 | No paid providers; deterministic clocks/time skip plus real-process restart/transport tests |
| G / G2 | Staging/production continuous workers | P0 | Approved host/plan/network/secrets, graceful drain and restart recovery proven |
| G / G3 | Horizontal scale/deployments | P1 | Competing worker tests and replay/canary deployment under active-run load |
| G / G4 | DR/upgrades | P1 | Independently restore DB and engine, reconcile cross-store cut, outbound initially disabled |
| H / K1 | Fixed/usage/operational/engineering cost | P0 | Owner approves measured pilot envelope and worst-case retry/storage/worker budget |
| H / K2 | Early-stage/scale suitability | P1 | No unnecessary cluster; credible migration and event-growth/load/retention limits |

## Five-option capability comparison

**A** Managed Temporal; **B** self-hosted Temporal; **C** bespoke PostgreSQL workflow engine; **D** Celery/RQ-style queue plus required application state; **E** current request-bound LeadForge LangGraph. C/D describe a proposed completed design, not software already present.

| Dimension | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- |
| Crash durability/history | Managed engine history/replay [T1] | Same semantics; operator persistence/availability responsibility [T8] | Run/step/event ledger must be built/tested | Broker/result storage plus app run ledger needed [C1/Q1] | Only committed Lead/analysis survives; graph state lost |
| Timers/long waits | Durable orchestration wait [T1/T10] | Same, if service/storage healthy | Due rows, polling and reschedule logic | DB-backed schedule required for long waits; distant Celery ETA unsafe choice [C2] | No durable timer/approval wait |
| Approval/pause/resume | App approval + durable messages/waits [T10] | Same | App state machine and dispatcher wakeup | App state machine, queue wakeup, scheduler | Not implemented |
| Retries/backoff/timeouts | Engine activity controls; business classification still required [T2] | Same | Lease/deadline/attempt/backoff framework | Task retry controls; broker acknowledgment tuning [C1] | Local bounded AI retries, no backoff |
| Idempotency/effects | LeadForge ledger/provider contract required [T2] | Same | Same + queue/step dedupe implementation | Same + redelivery/ack tests | Narrow CSV/auth/claim guards only |
| Versioning/deployments | Replay-compatible/pinned workers, SDK compatibility gate [T6] | Same plus server upgrade burden | Store definition/interpreter versions; migrate outstanding runs | Version task routing and app orchestration; retain old workers | Interrupted requests; no replay |
| Branch/parallel/children | Workflow primitives [T1] | Same | Need custom transition/fan-in semantics | Canvas/dependencies help jobs; durable governance state remains app work | Fixed sequential graph only |
| Horizontal scale | Multiple polling workers; app tenant/provider quotas required | Worker plus server/persistence scaling | SKIP LOCKED and fences; fairness/vacuum contention must be measured [P1] | Worker/broker scale; app quota/state required | More API processes do not add durability |
| Worker and tenant isolation | Separate workers/credentials; namespace is not row authorization [T3/T11] | Same, plus server auth/ops | Tenant row predicates; scoped leases/grants | Queues are routing, not permission | Active membership at HTTP boundary only |
| Python/FastAPI | Python SDK client from API, workers separate [T3] | Same SDK | Existing SQLAlchemy services; custom driver | Python task functions; DB session lifetime redesign | Existing Python async graph |
| LangGraph | Bounded activity; returned structured result | Same | Bounded job step | Bounded task | Reasoning and request lifetime coupled |
| PostgreSQL | Domain DB separate from managed engine | Domain DB + separate engine persistence/schema ownership | Main persistence; more locks/history/index work | Domain DB remains; broker/result durability separate | Existing domain DB only |
| Render | Dedicated paid worker candidate, verified connectivity needed [R2/R3/T3] | No credible free-stage HA cluster; new paid topology needed | Continuous paid worker/scheduler needed too | Paid worker + durable broker; no free shortcut | Current free web declaration; idle/crash restrictions [R1] |
| Kubernetes | Worker deployments, secrets/egress; no Temporal server cluster | Server cluster, persistence, monitoring/upgrades plus workers | API/worker/scheduler leases/DB ops | Broker/worker/scheduler deployments | Existing local API rehearsal only |
| Local development | CLI dev server plus isolated future worker [T8] | Same local tooling, production not equivalent | Disposable PostgreSQL + test workers | Local broker/worker + app-state tests | Existing mock/SQLite tests |
| CI complexity | SDK tests/time skip/replay + local service integration [T7] | Add server compatibility/migration tests | Extensive property/fault/race tests | Broker faults, acknowledgment/scheduler/state tests | Current tests easy but miss requested semantics |
| Operational burden | Workers, credentials, spend, namespace/latency monitoring | Above plus engine DB/server/HA/DR/on-call | Own scheduler, versioning, histories, recovery semantics | Own broker plus workflow state/scheduler/DR | Low for V1, unacceptable semantics for V2 |
| Fixed/usage cost | Worker/DB compute plus Cloud consumption/support [T9] | Server/persistence/worker compute and operator time | Worker/DB storage/IO and substantial engineering time | Broker/worker/DB plus orchestration engineering | Existing compute; hidden lost-work/provider-repeat cost |
| Lock-in | Temporal workflow semantics/history; adapter cannot make export portable automatically | Same semantic lock-in; infrastructure control | Custom interpreter/schema and maintainer dependence | Broker/task framework + custom orchestration | Current graph/request/API coupling |
| Observability/DR | Engine history + domain audit; two-store recovery contract | Above plus operator engine backups/restore | Entire visibility/archive/restore built internally | Broker/results do not replace domain audit/history | Content-free logs and saved analyses only |
| Likely failure modes | Nondeterministic code, expired key, unavailable worker, unknown effects, DB-engine split | Those plus cluster/persistence outage, unsafe upgrade | Expired lease stale worker, duplicate effects, timer/fan-in race, history bloat | Ack/redelivery mismatch, lost broker, distant ETA, missing business state | Kill after claim, lost graph, client timeout after commit |
| Current-stage judgment | Best target candidate; not yet operationally proven | Too much operations for present team/stage | Possible constrained fallback; not a cheap full Temporal replacement | Good bounded-job option; inadequate alone | Keep V1 only |
| Future-scale judgment | Strong conditional candidate after cost/version/privacy gates | Viable with funded platform/on-call ownership | High build/maintenance risk for full product | Viable component under explicit orchestration design | Reject for multi-day external effects |

Matrix shorthand source IDs refer to the verified register above. Unsupported account/SDK/host guarantees are not inferred from these capabilities.

## Weighted decision matrix

Score 1 = poor fit; 3 = achievable with significant application/operations work; 5 = strong fit after proper implementation. These are transparent engineering judgments, not independent product performance measurements. Effects scores assess how easily the option supports *our* ledger; none grants exactly-once sending.

| Criterion | Weight | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- | --- |
| Durability/long control flow | 20 | 5 | 5 | 3 | 3 | 1 |
| HITL/stop/resume fit | 10 | 5 | 5 | 3 | 2 | 1 |
| Business-effect safety integration | 12 | 4 | 4 | 4 | 3 | 1 |
| Versioning and active-run deployments | 10 | 5 | 5 | 2 | 2 | 1 |
| History/observability/recovery | 8 | 5 | 4 | 2 | 3 | 1 |
| Tenant/security boundary fit | 10 | 4 | 4 | 4 | 3 | 3 |
| Operational burden (higher = simpler) | 12 | 4 | 2 | 2 | 3 | 3 |
| Early-stage total cost (higher = better) | 10 | 3 | 2 | 3 | 4 | 5 |
| Python/LangGraph/DB ecosystem fit | 8 | 5 | 5 | 4 | 4 | 5 |
| **Weighted total / 5** | **100** | **4.46** | **4.04** | **3.00** | **2.98** | **2.16** |

Calculation: sum(weight × score) / 100. Sensitivity: transferring ten weight points from durability to early cost gives A 4.26, B 3.74, C 3.00, D 3.08, E 2.56; A still leads, but cost/operational uncertainty can independently veto acceptance. Changing unproven capability scores must be recorded, not presented as a benchmark result.

Hard gates override rank: continuous worker host; measured TLS connectivity; affordable approved budget; SDK/deployment replay proof; tenant/PII design; provider ambiguity safety. **No option has an executed LeadForge feasibility proof. E fails the required semantics; A remains preferred but acceptance is deferred.**

## Cost and stage strategy

Verified pricing facts are scoped to T9 above; do not assume a universal USD 100 minimum or that Developer is free usage. Published Developer support has zero base fee but charges 10% of usage; Business support has a USD 500 minimum/percentage rule. Current plan/discount/eligibility/tax terms must be reconfirmed before purchase. Exact Render worker monthly quote and account budget are UNVERIFIED; no billing information submitted.

Proposed costing worksheet (not a quote):

```text
Cloud total = billable Actions × applicable Action rate
            + active GB-hours × active rate
            + retained GB-hours × retained rate
            + applicable support-plan charge
LeadForge total = Cloud total + worker compute + domain DB/storage/backup
                + network/provider costs + on-call/engineering time
```

Count activities, retries, messages, heartbeats and schedules according to current billable-action rules rather than equating one workflow or event with one Action. Measure representative history bytes and retention instead of guessing per-run storage. Waiting seven days occupies history/storage but should not occupy a dedicated sleeping worker; platform history and worker memory are different resources [T1/T9]. Worst-case retry/heartbeat/payload growth matters as much as workflow count.

Now: retain current V1 staging, perform only separately authorized disposable local feasibility work, no production dependencies/resources. Later: fund persistent domain DB/backups, continuously running isolated worker(s), credential rotation, replay-safe rollout, monitoring and recovery. Self-hosted Temporal adds server/persistence/on-call cost; C adds long-term orchestration engineering; D adds broker/scheduler and still needs most governance state. None makes a free idle web process a reliable autonomous worker.

## Current Render compatibility finding

Repository `render.yaml` declares free backend/frontend web and free PostgreSQL; `runtime.py` starts one API process. R1/R3 make that **declared topology unsuitable for reliable continuous workflow workers**. A paid Render background worker is a documented candidate, not an existing service. Do not use artificial keep-alive traffic, place a worker in the web process, or mistake Temporal Cloud for worker hosting.

The live Render account plan, service IDs/configuration, database age/backup state, namespace region, latency, outbound HTTP/2/gRPC path, quotas and permitted budget are **UNVERIFIED — REQUIRES HUMAN CONFIRMATION**. Repository configuration does not prove those live facts. No dashboard/API credentials were inspected and no service was mutated.

E01 recommends a paid separate worker with domain-DB access and outbound TLS to the chosen Cloud namespace, or a separately approved continuously running host. Kubernetes is a future worker-host alternative; current local manifests are not an authorized production cluster. Public Render docs also advertise Render Workflows [R2]; that is not evidence of Temporal parity. Evaluate it in a separate scoped comparison only if the owner requests expanding the five-option scope.
