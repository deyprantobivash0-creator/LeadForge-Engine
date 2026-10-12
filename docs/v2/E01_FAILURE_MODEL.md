# E01 — failure, effect-safety and fallback model

Date: 2026-10-12. This is a proposed LeadForge protocol and future test specification, not executed fault evidence. [ADR](adr/ADR-001-DURABLE-EXECUTION.md) defers engine acceptance. Platform features are sourced in the [decision matrix](E01_EXECUTION_DECISION_MATRIX.md); all ledger/authorization behavior below must be built and tested in later authorized epics.

## Durable business-effect protocol

1. Freeze ActionIntent recipient/channel/content/connection/version/cost ceiling; compute stable opaque semantic key. Keep a separate ID for each execution attempt. Same key must never refer to changed content.
2. In one domain transaction verify actor/tenant/resource, live grants, approval binding/expiry, suppression/stop, connection eligibility and atomic budget reservation. Claim effect record with version/fencing token; append audit/outbox. Do not hold the transaction during provider calls.
3. Dispatch through the authorized adapter. Provider idempotency key is stable across retries if the provider promises the required semantics; validate retention window and request binding rather than assuming all providers support it.
4. Persist provider acceptance ID and evidence. Acknowledgment to the engine is separate. Activity retry reads saved result, not a new send command.
5. If provider acceptance is ambiguous, mark unknown and retain estimated liability. Query/reconcile by provider operation/key where supported. If no safe lookup exists, require human investigation; prefer uncertain delivery over a blind duplicate. Never generate a fresh key just to bypass a timeout.
6. Verified inbox events monotonically advance effect/conversation state and publish domain outbox events. Duplicate/out-of-order callbacks cannot decrement a confirmed result or create another action.

Engine retries are at-least-once opportunities to run an activity [Temporal activities](https://docs.temporal.io/activities); delivery safety comes from this protocol and provider capabilities, not a “completed” engine flag. At-most-one semantic dispatch with uncertainty is feasible for unsupported providers; guaranteed exactly-one delivered email is not established by LeadForge infrastructure alone.

## Twelve required scenarios

| Scenario | Proposed behavior and recovery | Required deterministic test / observable evidence |
| --- | --- | --- |
| 1. Worker crashes researching | Read-only activity restarts or resumes a separately designed checkpoint; inputs/source grants remain scoped; completed evidence artifact result reused | Kill before/after artifact commit; no cross-tenant result, one logical completion, repeated billable computation visible |
| 2. Crash after email accepted before local success | Effect was already dispatching; retry reconciles same semantic key/provider receipt; unknown if no lookup; no new send key | Mock provider accepts then drops connection/process; one provider acceptance, unknown/reconciled ledger and retained budget |
| 3. Approval while worker offline | Approval+outbox commit independently; relay retries durable message; compatible worker processes it later and revalidates authority | Stop worker, approve, restart; one recorded decision/resume and no expiry bypass |
| 4. Campaign paused while waiting | DB pause/epoch blocks new claims immediately; workflow message updates wait projection; timer due does not grant send | Pause before timer due, advance clock, resume under fresh checks; no send during pause |
| 5. Organization emergency stop | Commit organization stop first; invalidate queued capabilities and signal runs; dispatcher gates deny even with engine outage | Engine offline, stop, reconnect worker; queued effects blocked; already in-flight provider requests reported honestly |
| 6. Provider rate-limits | Shared provider/tenant admission budget; bounded backoff/jitter/Retry-After; permanent/eligibility errors do not retry; no fresh reservation per attempt | Inject 429 then recovery; attempt count/deadline/reservation bounded; other tenants not starved |
| 7. Timeout may hide acceptance | Distinguish research computation retry from sending uncertainty; send goes unknown and reconciliation, not failed→new touch | Simulate timeout-before-accept and timeout-after-accept separately; receipt/unknown state preserved |
| 8. Deploy with 10,000 active workflows | Compatible version-pinned worker fleets/drain, staged rollout and historic replay; no mass kill/migration of business intents; watch history/queue capacity | Synthetic active/waiting workload under approved host budget, old/new replay fixtures, canary/drain/reconnect metrics; not performed here |
| 9. Fourteen-day nurture across deployments | Durable timers/messages and pinned sequence/Brain versions; historical worker compatibility retained; live policy still rechecked at each effect | Time-skip fourteen days through two releases, reply/opt-out midway; no stale-context follow-up |
| 10. Same webhook five times | Signature/authenticity + connection/tenant mapping before inbox; unique event key; one transaction/projection and one logical signal | Five identical callbacks and an out-of-order variant produce one transition; different tenant mappings cannot collide |
| 11. Approval after Lead/context changed | Compare approval's action hash/input version and validity requirements; invalidate/re-propose if material context changed; current rule/suppression recheck | Edit recipient/content/offer, revoke role or opt out before approval/dispatch; no old approval executes new payload |
| 12. Missing/wrong tenant inside worker | Reject before retrieving artifacts, invoking model/provider, consuming reservation or mutating any row; quarantine with safe reason | Inject missing tenant, mismatched resource, altered grant; zero provider/tool calls and no other-tenant data |

Temporal history/messages can support the restart/wait aspects [execution](https://docs.temporal.io/workflow-execution), [Python messages](https://docs.temporal.io/develop/python/workflows/message-passing). These scenarios describe LeadForge design requirements, not assertions that those features already exist or that all tests have passed.

## Stop, lease and network boundary

Stop linearizes at committed organization/campaign epoch. No new dispatch claim may be authorized after it. Already claimed/dispatching actions are in flight, even if the provider call has not returned. A live pre-send check narrows the race but cannot atomically couple a database stop to remote provider acceptance. Keep in-flight actions visible, use provider cancellation where supported and reconcile. Do not promise instantaneous revocation of an email/call already authorized/accepted externally.

Fencing tokens prevent stale workers updating database result state. They cannot by themselves fence a remote provider that does not inspect the token/idempotency key. Therefore lease expiry never authorizes blind re-dispatch of an uncertain effect. Heartbeat/liveness is not proof a send did not happen.

## Minimum credible PostgreSQL alternative (Option C)

This is a design sketch, not a migration or executed SQL. Scope it to explicit bounded versioned state machines, not arbitrary replay of generated Python. Required conceptual records:

| Record | Minimum responsibility |
| --- | --- |
| workflow_runs | Tenant/principal, immutable definition/input versions, current state/version, deadline, stop epoch, terminal result |
| workflow_steps | Stable semantic step, dependency/join state, input/output artifact refs, version, next eligible time, retry policy |
| scheduled_jobs | Unique ready operation, due_at UTC, attempt/deadline/status, queue class and priority; durable long timers |
| job_claims | Job/tenant, monotonically increasing fence, owner, lease_until, heartbeat_at, attempt state |
| workflow_events | Append transition/version/reason, correlation/causation and history cursor; audit link |
| outbox / inbox | Domain-event relay and deduplicated provider/approval/command consumption |
| effects / approvals / reservations | Same immutable effect protocol, governance and cost safety as any engine |

Claim algorithm: transaction selects a bounded set of due runnable rows with `FOR UPDATE SKIP LOCKED`, locks parent state/version where needed, verifies authority/admission limits, increments fence/attempt and sets lease, then commits. Worker executes without that lock. Completion transaction requires tenant+job+fence+expected parent version, writes result/event/outbox and schedules successors atomically. PostgreSQL explicitly describes SKIP LOCKED as queue-like consumption with an inconsistent view, not general ordering correctness. [PostgreSQL 16 SELECT](https://www.postgresql.org/docs/16/sql-select.html).

Database clock controls due/lease/expiry; workers heartbeat using current fence, so stale heartbeat/completion cannot extend a stolen claim. Reaper expires leases in small transactions, requeues only safely retryable work and flags unknown effects for reconciliation. Competing schedulers are safe only with uniqueness/claim constraints. Optional notifications wake pollers; periodic scans remain necessary because notifications are not the durable queue. Indexes by status/queue/due plus tenant admission enforce bounded work selection; fairness prevents one customer's huge backlog dominating others.

Approval waits are durable run states with no claimed worker; decision+outbox atomically enqueues one successor. Expiry schedules a separate deduplicated transition. Pause/stop changes run gates before pending jobs can claim. Cancellation does not delete history or unknown effects. Branch/fan-in uses persisted dependency counters/versions/unique edges; a duplicate child completion cannot release the parent twice.

Versioned definitions and interpreters must be retained while old runs exist; worker deployment can't reinterpret a waiting step with new semantics. Migrate active runs only via explicit audited compatible transition. Replay should rebuild read projections from events, not replay external sends. Keep snapshots/checkpoints and history compaction with audit retention, restore cursors and deletion/PII handling. Monitor ready age, overdue timers, leases, stolen jobs, attempts, transition conflicts, DLQ and engine-table vacuum/index pressure.

This becomes “build your own Temporal” at general replay semantics, arbitrary child/fan-in ordering, reliable multi-day timers under failover, cancellation propagation, deployment version routing, workflow history/recovery tooling and cross-store/provider ambiguity. All require property/concurrency/fault tests and sustained ownership. Existing Lead claim/attempt logic is a useful precedent but lacks scheduler, heartbeat, general event history and resume semantics. Do not extrapolate it into a complete engine.

Conditional fallback acceptance: narrowly define supported transitions/workloads, fund an owner, prove all applicable P0 matrix/failure gates on disposable PostgreSQL and measure contention/history growth. If those costs exceed Cloud plus worker hosting, C is not the cheap option. No fallback implementation occurs while ADR is deferred.

## Celery/RQ-style alternative (Option D)

Useful for bounded Python jobs, queue admission and retryable computation. Celery acknowledgment/redelivery settings and idempotent-task design must be deliberately tested; late acknowledgments alone are not universal crash redelivery. [Celery tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html). RQ exposes scheduling/repeat/retry mechanisms, but those do not define business approval/action authority. [RQ scheduling](https://python-rq.org/docs/scheduling/).

For LeadForge, still build workflow_runs/steps/events, DB long schedule, approval expiry/resume, stop, deployment/task versions, durable audit and effect ledger. Do not encode a fourteen-day wait as one distant Celery ETA/countdown: documented worker-memory/redelivery limitations matter. [Celery scheduling caveats](https://docs.celeryq.dev/en/stable/userguide/calling.html). Broker persistence/backup/failover and result retention require an approved configuration; no Redis durability assumption is made here.

Queue-only is not accepted for full V2. A limited hybrid could be evaluated as C's transport after explicit scope/ownership review; it cannot remove C's orchestration responsibilities.

## Recovery and disaster recovery

API crash: replay outbox start/command with stable ID. Engine unavailable: accept only safely persisted intents/decisions, expose backlog, deny effects lacking live authority. Worker offline: no work progresses, but durable waits/accepted messages remain stored. Domain DB unavailable: halt effects instead of treating engine history as authority. Provider outage: circuit break and preserve unknown liabilities. Credential revoke: reconnect requires approved rotation, not an unchecked fallback.

DB and engine backups have different recovery cuts. Restore with dispatch disabled; reconcile action/provider IDs, replay unapplied outbox/inbox records, restore run projections, reapply stop/suppression/deletion, verify old definition/worker artifacts, then permit bounded resume. No engine history retention is a substitute for domain audit retention. Dead letters preserve safe reason/refs and retry policy; re-drive is permissioned, idempotent and reauthorized.

Local time-skipping tests can prove logical waits without sleeping days; real transport/restart and PostgreSQL races are separate gates. [Python testing](https://docs.temporal.io/develop/python/best-practices/testing-suite). E01 executed neither those tests nor any broker/engine/database operation.
