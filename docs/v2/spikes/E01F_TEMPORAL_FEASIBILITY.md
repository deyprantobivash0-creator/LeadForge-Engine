# E01-F Temporal feasibility

Date: 2026-10-12. Baseline: `17ca6d1dbc8fe84f16612e2e8b3e5e4b677913d6`, branch `main`.

Recommendation: **KEEP_DEFERRED**. The local Python execution model passes the experiments; Cloud acceptance still needs customer-specific operational evidence. This report supplements ADR-001 without changing its status or authorizing E02/product implementation.

## Environment and isolation

Windows; Python 3.12.14; Temporal Python SDK 1.34.0; pytest 9.1.1; pytest-asyncio 1.4.0. Official Temporal CLI 1.9.1 reports Server 1.32.0 and UI 2.54.1. No Docker or installed CLI was found. The Windows amd64 release archive was downloaded from the official temporalio/cli GitHub release; SHA256 matched `babb65844835045c91fb98930fe10b81de28db80c8c609180473d2c0b18c7589`.

All executables, isolated dependencies, synthetic provider SQLite databases and local engine persistence lived in newly created disposable OS-temp/Git-ignored `.ci-tools` children. None became application source. The server listened only on 127.0.0.1:17233, with HTTP 17234 and metrics 17235; headless, scratch SQLite persistence. No staging database, production module, real email provider or Cloud account was used.

High-level reproduction recipe (fresh disposable environment):

1. Create a Python 3.12 virtual environment; install pinned `temporalio==1.34.0`, `pytest==9.1.1`, `pytest-asyncio==1.4.0` from PyPI.
2. Download/check the official CLI release checksum and extract only into scratch.
3. Run `temporal server start-dev --ip 127.0.0.1 --port 17233 --http-port 17234 --metrics-port 17235 --headless --db-filename <scratch>/temporal.sqlite --log-level error`.
4. Register the synthetic workflow and Activities on a unique task queue; start workers as subprocesses with separate logs. Use SDK Client, Worker, Replayer and WorkflowEnvironment facilities.
5. Run `python -B -m pytest -q -p no:cacheprovider test_spike.py --tb=short`. Create the time-skipping executable download directory before calling `WorkflowEnvironment.start_time_skipping`.
6. Capture results; kill only experiment workers, stop server, remove exact fresh scratch directories.

Executable fixtures and captured raw history were deliberately removed after evidence capture as requested. The companion results document records test names, assertions and measurements; it is not a retained runnable test suite. Reproduction requires rebuilding the described synthetic fixtures. Official [CLI](https://docs.temporal.io/cli) and [Python testing facilities](https://docs.temporal.io/develop/python/best-practices/testing-suite) describe the supported tools.

## Experiment design

RevenueWorkflow accepts explicit organization_id, actor_id, execution_principal and correlation_id. It calls a bounded research Activity, saves its validated structured result in workflow state/history, waits on engine timers or approval signals, and completes. Activity retry policy: initial interval 100ms, maximum 1s, maximum three attempts, start-to-close timeout 10s. Research's representative reasoning call has a one-second bound. Synthetic results contain score zero and empty evidence, never customer-like invented intelligence.

Approval carries organization, proposal identity and APPROVED/REJECTED decision. Wrong organization/proposal is ignored; only WAITING_FOR_APPROVAL accepts it. The wait has a seven-day deadline. Signals implement pause/resume and an organization-matching stop. Native engine cancellation is tested separately. A logical CANCELLED result is a completed workflow with a domain outcome; it is distinct from engine CANCELED status. These signals prove a representation, not production authorization, campaign fan-out, immediate interruption of an in-flight provider call, or policy enforcement. Expiry itself was not separately tested.

The fake provider stores accepted keys in its own SQLite table with a primary-key constraint, committing before reporting a receipt. The stable key is workflow identity plus a fixed semantic touch identifier; the record includes organization. One test raises after acceptance; another terminates the entire worker with exit code 23 after acceptance. Retry uses the same key and returns the original synthetic operation receipt. A negative control deliberately uses an attempt-dependent key and produces two accepted effects. UNKNOWN acceptance is represented as data, then reconciled by lookup under the same tenant/key; it never blindly sends a new identity.

This demonstrates **provider idempotency/reconciliation**, not Temporal exactly-once delivery. Production needs an immutable EffectRecord with organization, approved action/version/hash, stable semantic key, provider operation reference, attempt/fencing ownership and auditable transitions such as PREPARED, DISPATCHING, UNKNOWN, CONFIRMED and terminal failure. UNKNOWN must block automatic new-identity dispatch until reconciliation or explicit governed resolution. Live permissions, budget, suppression and stop checks belong at dispatch. Atomic domain intent/outbox and provider-ledger race recovery remain future work; the simulator is not a PostgreSQL concurrency proof.

For E03, execution context must originate from authenticated membership and a registered scoped principal, then be resolved/revalidated by tenant-scoped services. The spike rejects absent organization before recording any Activity/provider IO and separates two explicit tenants. It does not validate real membership, grant revocation, principal expiry or adversarial authorization. No implicit current-tenant global exists.

The LangGraph boundary uses the explicitly permitted representative bounded reasoning function, without importing or installing LeadForge's graph. Workflow owns durable ordering/timers/approval/history; Activity owns bounded reasoning and structured validation; domain policy/dispatcher would own effect authority. This proves boundary compatibility, not actual LangGraph integration or model latency/cost.

Captured history replays unchanged. A deliberate timer-before-research change fails with NondeterminismError. A `workflow.patched('e01f-new-path')` guard preserves old-history replay and permits new execution. Current [Worker Versioning guidance](https://docs.temporal.io/worker-versioning) uses deployment name/build ID and pinned or auto-upgrade behavior; auto-upgrade still needs replay-safe changes. Future deployment must retain compatible worker builds, replay historical fixtures and prove routing/draining/rollback. Actual deployment version routing was not exercised.

## Operations and remaining acceptance work

Local development needs only CLI server plus separate Python workers. A sleeping workflow does not require a sleeping HTTP request. Offline workers delay runnable work; the engine keeps accepted history/signals. This experiment kills workers, not the engine or its persistence, and proves neither engine HA nor disaster recovery.

The existing E01 baseline describes free Render staging without a dedicated worker. Public [compute plans](https://render.com/docs/compute-plans) list no free background-worker plan. Free web services [spin down after inactivity](https://render.com/docs/free); that topology is unsuitable for an always-on poller. This is a documented topology assessment; the live account was not inspected. Render [background workers](https://render.com/docs/background-workers) or another approved continuous host require separate funding and authorization.

Future workers need independent deploy/restart control, graceful shutdown, resource limits and bounded Activity concurrency. Multiple workers can poll task queues; sizing must follow measured queue latency, provider limits, memory and model workload. Long-lived runs require build retention and controlled deployment version changes. No scaling benchmark was performed.

The [Python Cloud client](https://docs.temporal.io/develop/python/client/temporal-client) documents TLS with API-key authentication or mTLS. Future configuration needs namespace/endpoint, scoped engine credential (or certificate/private key), rotation ownership, outbound gRPC connectivity to the selected endpoint (normally port 7233), approved DB/provider connectivity and possibly a payload-codec key. Cloud hosts the engine; LeadForge hosts its workers. Actual credentials, TLS handshake, namespace permissions and egress were not tested.

Privacy review must approve service region, residency, history retention, payload minimization/encryption, key custody and deletion obligations. Avoid putting secrets or unnecessary customer content in histories, search attributes or logs. Region choice remains unverified.

Budget approval needs workload estimates for Cloud actions/history storage/support plus continuous worker, database, egress, model and monitoring costs. [Current pricing](https://docs.temporal.io/cloud/pricing) supplies inputs, not an approved LeadForge budget. No purchase or resource creation occurred.

Monitoring should cover worker availability, queue age/schedule-to-start latency, workflow-task failures/nondeterminism, Activity retries/timeouts, approval age, UNKNOWN effects and reconciliation backlog. Assign alerts/runbooks/owners; test them. Recovery planning needs agreed RPO/RTO, domain DB/outbox backups, compatible build recovery, provider reconciliation and Cloud failure expectations. Engine history alone cannot recover missing business authority or prove external acceptance.

CI viability requires a separately authorized CI job with pinned/checksummed dependencies, cached test-server binary, isolated ports/temp persistence and cleanup. The local SDK testing facilities succeeded, but no actual CI runner/job was tested or modified. Local success is not a CI PASS.

## Acceptance gate matrix

PASS means the stated local feasibility scope passed; it does not approve production behavior.

| # | Gate | Status | Evidence / boundary |
|---|---|---|---|
| 1 | Python SDK suitability | PASS | Registered workflow, Activities, Client, Worker, Replayer |
| 2 | Worker crash recovery | PASS | Hard kill/restart; research called once; post-accept crash retry |
| 3 | Long durable wait model | PASS | Durable timer restart; 14-day virtual timer; not 14 real days |
| 4 | Approval signal model | PASS | Online/offline approval and rejected wrong tenant |
| 5 | Retry semantics | PASS | Attempts 1 and 2, bounded policy |
| 6 | Cancellation/stop model | PASS | Native cancellation, organization stop, pause/resume |
| 7 | Explicit tenant context | PASS | Missing organization fails before IO; two tenants separated |
| 8 | External-effect safety compatibility | PASS | Same-key retry/reconciliation; negative control duplicates |
| 9 | Testability | PASS | Real server integration, replay and SDK time skipping |
| 10 | Workflow evolution/versioning | PASS | Replay failure detected; patch old/new paths pass; routing untested |
| 11 | Local developer experience | PASS | Isolated official Windows CLI/SDK setup and cleanup |
| 12 | CI viability | UNVERIFIED | Local facilities pass; actual runner not exercised |
| 13 | Cloud TLS/auth model | UNVERIFIED | Official model reviewed; no authenticated connection |
| 14 | Worker hosting | UNVERIFIED | Free topology unsuitable; continuous host not selected/validated |
| 15 | Regional/privacy fit | UNVERIFIED | Requires approved region/data handling |
| 16 | Production operating budget | UNVERIFIED | No funded workload estimate |
| 17 | Operational monitoring | UNVERIFIED | Proposed signals; no alert/runbook drill |
| 18 | Disaster/recovery expectations | UNVERIFIED | No engine/DB/Cloud recovery drill or RPO/RTO agreement |

The local results do not justify REJECT_TEMPORAL_CLOUD. The seven unverified operational gates prevent ACCEPT_TEMPORAL_CLOUD. Resolve those gates and obtain an architecture decision before adoption. No product implementation was performed.
