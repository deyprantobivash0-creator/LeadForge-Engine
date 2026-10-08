# Local performance and resilience methodology

Run `python -B scripts/verify_e2e_local.py` from the repository root with Docker
on PATH. See [E2E testing](E2E_TESTING.md) for setup and isolated synthetic data.
The full runner calls `scripts/local_performance.py` inside a separate read-only
load container restricted to two CPUs and 256 MiB. That container reaches
production Nginx on private Docker networking with the canonical loopback Host
and Origin. Real session cookies, Argon2id login, membership authorization and
CSRF remain enabled. The application uses one Uvicorn process and PostgreSQL
16.15; there are no paid load tools or external provider calls.

## Sampling and correctness

Warm each read endpoint once, then time 30 sequential requests with
`time.perf_counter`. Report linearly interpolated p50/p95/p99, maximum, request
count and failures. These are HTTP round-trip measurements including Nginx,
application authorization, queries and response transfer, not isolated SQL
execution times. Small samples make p99 exploratory, not a reliable tail SLA.
Baseline endpoints are liveness, readiness, Lead list/detail, Dashboard v2,
Reports v2 Today, current intelligence and session validation.

Use concurrency 1, 5, 10, 25 and 50 for authenticated Lead list, Dashboard and
Reports: 50 requests per endpoint/level except 100 at concurrency 50. Each worker
has its own opener and a snapshot of one authorized synthetic session's cookies;
this is request concurrency, not 50 independently logged-in users. HTTPS trust
configuration is reused rather than rebuilding an unused certificate store per
HTTP request. Tenant sentinel exclusion and deterministic pipeline/report
summaries are asserted, as well as zero unexpected status failures. Pause between
levels; requests have timeouts and a 10-second safety bound, which is a local
test abort criterion, not a product SLA.

Authentic login has five samples, logout four; session validation has 30. The
runner waits for the existing 10-attempt/minute shared proxy login budget rather
than bypassing it. It deliberately verifies 429 and Retry-After separately.
The limiter is process-local and shares the proxy peer; it is not distributed
production abuse protection.

Mock analysis measures the synchronous request including commit, then reads the
persisted analysis and compares IDs. Separate database commit duration is not
instrumented; do not call the full request duration a commit-only measurement.
This is **MOCK PROVIDER ONLY**, not real LLM latency or cost evidence.

CSV tiers are 10/100/500/1000 rows. Assert preview changes no Lead count, confirm
imports the exact count, and repeat preview classifies all rows as duplicates.
The current active import enforces 1 MiB and 1000 rows. Test empty, NUL-containing,
malformed, oversized and 1001-row inputs; browser tests cover partial valid/invalid
and duplicate rows. Rejected previews cannot write Leads. Existing PostgreSQL
integration also verifies savepoint race handling and full rollback of unrelated
constraint failures. No huge datasets or invented plan-limit behavior are used.
Measure list/Dashboard/Reports again with the resulting 1613 Alpha Leads.

## Resources, queries and faults

Sample only the disposable services and labeled load driver with Docker stats.
Retain CPU, memory and I/O samples locally. Stop the disposable backend if their
combined memory exceeds 50% of Docker allocation, or CPU exceeds eight cores in
two successive samples. These resource safeguards protect this desktop, not
deployment capacity promises. Driver resource limits keep generator work separate
from application utilization. A stopped run is failure, never accepted evidence.

Read `pg_stat_activity` before/after load, require no persistent idle transaction,
and check recovery after a database outage. SQLAlchemy uses pre-ping, a five-second
pool timeout and five-second connection timeout. SQL review records query counts
and individual durations for 20/100-row Lead pages, Dashboard and Reports on the
synthetic dataset. Compare page query counts for N+1; inspect tenant/date
predicates, current-analysis ranking and existing indexes before considering a
change. Do not infer a missing-index fix from a small local dataset alone.

Under light authenticated traffic, stop only this project's PostgreSQL and verify
readiness 503, liveness 200, generic private customer errors and recovery. Restart
backend and frontend while a bounded probe runs through Nginx; allow temporary
unavailability from this single-instance topology, then require readiness and
browser recovery. Expire synthetic sessions in this disposable database and
require subsequent validation 401. Inject a provider failure through the existing
service seam; verify the latest successful analysis survives both in PostgreSQL
and in the browser. Check browser/performance request IDs in redacted logs, which
must exclude the generated database password, fixture login password and payload.

## Interpretation

Results are specific to an AMD Ryzen 7 5700X desktop (16 logical CPUs, about
16 GiB host RAM; Docker about 7.72 GiB), existing local services and this small
synthetic history. They are not cloud production SLAs or proof of capacity.
Use GREEN for responsive successful local reads with low bounded-load tails,
ACCEPTABLE for deliberate password work/bounded batch work or visible queuing,
and NEEDS OPTIMIZATION for reproducible correctness failures or material sustained
delays. Classification follows the measured evidence in
[Step 5J-L verification](STEP_5J_L_VERIFICATION.md), not fabricated commercial SLAs.

Known future scaling risks include offset pagination at large offsets, substring
searches without specialized indexes, repeated current-analysis ranking across
aggregate queries, row/savepoint work during 1000-row imports, and full-period
historical CSV export. The current UI offers newest-first ordering and filters;
there is no arbitrary user-selected sort. None of these observations alone
justifies changing schema or rewriting queries in this milestone.
