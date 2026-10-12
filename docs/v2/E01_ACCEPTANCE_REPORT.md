# E01 — analysis acceptance report

**Date:** 2026-10-12 (Asia/Dhaka).
**Task result:** PASS — documentation/feasibility analysis delivered.
**Architecture outcome:** **DEFER_DECISION_PENDING_FEASIBILITY_SPIKE**.
**Runtime acceptance:** NOT GRANTED. **E08 engine adoption:** blocked pending F01–F08 and architecture review.
**Baseline:** `d5ca7be212e324c68ea00dc648f54a4d3ca0a1b4`, `main`; no commit/push in this task.

## Deliverables and acceptance coverage

| Requirement | Evidence / disposition |
| --- | --- |
| Read eight committed V2 documents, extract E01 assumptions | [Execution baseline](E01_EXECUTION_BASELINE.md); working copies read and compared with committed contents; no baseline document changed |
| Audit actual execution/transactions/runtime | Source/line evidence, classification and current sequence diagram in baseline; sync DB + async request-bound reasoning distinguished |
| Requirements A–H | [Decision matrix](E01_EXECUTION_DECISION_MATRIX.md): durability, flow, HITL, effects, tenant, observability, operations and cost gates |
| Compare five options with explicit weights | Matrix scores A 4.46, B 4.04, C 3.00, D 2.98, E 2.16; weight total 100, sensitivity and hard feasibility gates |
| Verify changing external claims | Dated official Temporal/Render/PostgreSQL/Celery/RQ/LangGraph source register; inaccessible URLs not used; account-specific facts marked UNVERIFIED |
| Temporal feasibility seventeen answers | [ADR](adr/ADR-001-DURABLE-EXECUTION.md), including worker location/TLS/auth, restart/deploy/waits, versioning, tenant/PII, local/CI and operations |
| PostgreSQL fallback / queue alternative | [Failure model](E01_FAILURE_MODEL.md): claims/fences/heartbeats/scheduler/history/version state, danger of rebuilding an orchestrator; job queue vs durable workflow explicit |
| Exact layer ownership/contracts | ADR contract table and LangGraph/orchestrator/domain/policy/dispatcher responsibility table |
| Twelve failure scenarios | Failure model includes proposed behavior and deterministic test evidence required for every requested scenario |
| Decision rule | Exactly one outcome: deferred, not automatic Temporal adoption; A remains preferred candidate |
| Cost/stage strategy | Public pricing model verified; no invented chosen-host invoice; now retain V1, later fund/rehearse continuous worker topology |
| Dependency review | E02–E15 order preserved; engine-independent E02–E07 need separate approval, E08 additionally requires feasibility decision; no silent roadmap rewrite |
| No implementation/resources | No experiment, SDK install, worker, namespace, Redis, paid account, migration, DB/Render mutation, manifest/runtime edit or E02 work |

## Main findings

Current Lead Brain commits claims/results, but cannot resume in-memory reasoning after a crash or wait on multi-day approval/timers. A saved lease is not a durable scheduler; another request can reclaim it after expiry. No worker, event inbox/outbox or business-effect ledger is registered. Existing service-owned transactions and attempt fences are reusable, while some Lead repository commits need E02 ownership work.

Managed Temporal is a credible target candidate, not accepted infrastructure. Source-declared Render topology is two free web services and free PostgreSQL with one API worker, not a continuous workflow worker. Verified worker-plan/idle restrictions make that declared layout unsuitable for the requested execution. Live account topology, network/auth, namespace region, host budget and SDK version/deployment behavior remain **UNVERIFIED — REQUIRES HUMAN CONFIRMATION**. A local test cannot establish those facts.

Proposed transition is API/domain PostgreSQL/outbox → engine client → Temporal Cloud, with separately hosted continuously polling workers invoking bounded LangGraph and scoped services. PostgreSQL policy/approval/stop/budget/action records remain business authority. Provider ambiguity requires reconciliation regardless of engine. Self-hosted and PostgreSQL/queue fallback options need explicit cost/operations scope rather than becoming unplanned substitutions.

## Feasibility evidence not performed

F01 host/live topology and budget; F02 namespace/region/privacy/auth; F03 sustained TLS/gRPC and rotation from selected host; F04 pinned SDK restart/approval/time/version tests; F05 mock effect/stop/tenant safety; F06 active-run replay/load/drain; F07 measured invoice envelope; F08 independent-store restore reconciliation. Full specifications and pass criteria are in ADR.

No executable V1 contract fixtures or throwaway prototype were created because this task explicitly prefers zero source changes. Current source/test inventory and future fixture specifications were documented instead. Existing test presence does not prove the future engine's recovery properties. Application tests, GitHub CI, live service checks and provider/network experiments were not executed or modified here.

E01 is complete as a defensible analysis with deferred outcome; the original production-engine go/no-go gate remains open. Request architecture review before authorizing a narrowly scoped feasibility spike or any implementation. Do not begin E02 merely because this report says analysis PASS.

## Validation and preservation

- Only the five requested E01 Markdown documents created: this report, execution baseline, decision matrix, failure model and ADR.
- Relative document links/fences/whitespace and weighted-score arithmetic checked. Source register provides references for platform claims; customer-specific uncertainties and unperformed proofs explicitly labeled.
- `git diff --check` passed; existing CRLF warning for `docs/RENDER_STAGING.md` is unrelated. New untracked files also receive direct text checks because Git diff alone omits them.
- Existing Gitleaks scanner receives only the concatenated five E01 documents through stdin with full redaction; no original V2 document, operator script or secret file is scanned/printed.
- Preservation checksums compare all 451 pre-existing tracked/untracked files, including all eight committed V2 docs/manifests, plus a separate `leadforge.db` checksum. No old file changed or disappeared; local HEAD and index remain unchanged.
- `_temporary_staging_login.py` remains untracked and untouched; contents not inspected/printed or executed. It is only checksummed for preservation.
- No application source, manifest, Docker/runtime config, migration or staging/production data changed. No dependency installation, resource purchase, Temporal namespace, Redis, worker, PostgreSQL/Render operation, commit, push or deployment occurred.

## Follow-up authorization boundary

Review ADR and approve/reject the deferred recommendation. If accepted for investigation, authorize a separate disposable local spike with explicit directory, dependencies, network and compute limits. Cloud/Render accounts, credentials, worker resources and budget require their own explicit scope. No paid resource is necessary to finish this E01 analysis, and none was created.

**E01 analysis complete. Awaiting architecture review before implementation.**
