# E01-F executable results

Date: 2026-10-12. **STATUS: PASS for the feasibility spike. Recommendation: KEEP_DEFERRED for Temporal Cloud acceptance.** Operational acceptance is incomplete; see the [18-gate matrix](E01F_TEMPORAL_FEASIBILITY.md#acceptance-gate-matrix).

Environment: Windows, Python 3.12.14, Temporal SDK 1.34.0, CLI 1.9.1 (Server 1.32.0, UI 2.54.1), pytest 9.1.1, pytest-asyncio 1.4.0. Baseline main HEAD: `17ca6d1dbc8fe84f16612e2e8b3e5e4b677913d6`.

## Final test run

Command: isolated venv `python -B -m pytest -q -p no:cacheprovider test_spike.py --tb=short`.

```text
...................                                                      [100%]
19 passed in 69.48s (0:01:09)
```

The 19 tests include one evidence-export assertion; 18 are behavioral tests. All data and provider receipts were synthetic. Most integration tests used a separate real worker subprocess against the official local dev server; the patched-new-execution and time-skipping tests used in-process SDK workers.

| Test | Assertion / measured result |
|---|---|
| basic_reasoning | COMPLETED; organization 101; validated score 0, empty evidence; one research call |
| worker_kill_restart_waiting_timer | Worker PID 21680 killed during five-second durable timer; replacement PID 4836; COMPLETED; research calls remained 1; history 18 events |
| approval_online | Exact proposal/organization approval while waiting leads to APPROVED completion |
| offline_approval | Kill while WAITING_FOR_APPROVAL; signal accepted with no worker; one WorkflowExecutionSignaled event before restart; restart completes APPROVED; research remains 1 |
| reject | REJECTED logical outcome; no provider effects |
| native_cancel | Cancellation while approval wait raises WorkflowFailureError with CancelledError cause; engine status CANCELED |
| organization_stop | Matching organization stop during wait returns logical CANCELLED; no effects |
| pause_resume | Approval while paused reaches PAUSED; resume completes |
| send_retry | Provider accepts then Activity raises; attempts [1,2], same key, one accepted logical effect, CONFIRMED receipt |
| hard_worker_crash_after_accept | Provider commits acceptance; entire worker exits 23; effects already 1; restart and timeout-triggered retry produce attempts [1,2], same key, effects still 1 |
| unknown_reconciliation | UNKNOWN after acceptance; one send, one same-key/tenant lookup, one accepted effect, CONFIRMED |
| unkeyed_negative_control | Attempt-dependent identity produces two accepted effects, demonstrating retries alone do not deduplicate |
| missing_tenant | Missing organization causes workflow failure before any research/provider record; zero calls/effects |
| explicit_two_tenants | Organizations 101 and 202 carried explicitly; results and recorded calls retain their respective organization |
| wrong_approval_binding | Organization 202 approval cannot release organization 101 wait; matching approval completes |
| replay | Captured history: 16 events; unchanged replay passes; deliberately incompatible timer insertion raises NondeterminismError; guarded patch replays old history |
| patched_new_execution | Patched workflow executes successfully on new history |
| time_skipping | SDK WorkflowEnvironment advances 14 virtual days; workflow completes in 0.032 wall seconds |
| write_evidence | Nonempty synthetic evidence exported successfully |

Replay fixture SHA256 before deletion: `e95abbbb146d832117b3e89cba3ed547a5c47823bb84b4df1b593bb84e7bc88b`. A digest identifies the tested fixture; it does not replace the fixture or permit replay after cleanup.

## Failures encountered and resolved

The initial restricted process could not download dependencies because host networking was blocked (WinError 10013). A host-enabled process could not reliably execute/write a virtual environment created by the restricted identity. Fresh host-created Git-ignored scratch resolved the permissions boundary; installs stayed isolated. No system-wide configuration or application dependency changed.

The first complete test run reported `18 passed, 1 skipped in 69.84s`. Time-skipping server startup failed with an executable-download path error. Creating its disposable download destination fixed it: focused verification passed two selected tests in 2.23s; the final full run passed all 19. This was a local setup issue, not an unresolved SDK limitation.

The incompatible replay and two-effect negative control are intentional successful tests of failure detection. The provider crash is also intentional. No unexpected test failure remains.

## Interpretation and limits

Normal execution, worker restart, offline approval, rejection, native cancellation, domain stop, pause, Activity retry, UNKNOWN reconciliation, explicit tenant context, bounded reasoning and replay-safe patching are locally feasible. No real LangGraph invocation was tested; the authorized representative bounded function demonstrates its Activity boundary. No customer data, real email, PostgreSQL concurrency, live principal checks, Cloud connectivity, worker deployment routing, scaling, actual CI runner or engine disaster recovery was tested.

Current free Render topology is unsuitable for a continuous poller: [worker plans have no free tier](https://render.com/docs/compute-plans), and [free web services idle](https://render.com/docs/free). A funded continuous worker, authenticated Cloud connection, approved region/privacy controls, operating budget, alert/runbook validation and recovery expectations remain unresolved. Public documentation is evidence of available mechanisms, not of LeadForge account configuration.

## Cleanup and repository boundary

Temporary worker processes and the local dev server were stopped; the three newly created disposable scratch directories, including all executable fixtures, virtual environments, SQLite simulator/engine data and downloaded binaries, were removed after capture. No unrelated directory was removed. Only the two E01-F documents were added to the repository.

Existing tracked/untracked file content was checked against the pre-spike SHA256 inventory; the excluded temporary login script was checked by metadata only and never inspected/executed. `.env` contents were not read. `leadforge.db` checksum remains `217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a`. Existing HEAD and index remain unchanged. Exact final status is reported in the delivery message; `git diff --check` passes.

No application source, manifest, deployment configuration or migration was changed. No staging database access, Render mutation, cloud/paid resource creation, purchase, commit or push occurred. Unrelated work remains preserved. No product code was implemented.

E01-F feasibility spike complete. Awaiting architecture decision.
