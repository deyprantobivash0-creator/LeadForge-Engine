# Local release candidate boundary

Step 5K-L verifies the current local product release scope through isolated production-built Compose browser journeys, SQL tenant/session/CSRF behavior, fresh PostgreSQL migration, full backend and integration suites, security/dependency scans, container/runtime checks and Docker Desktop Kubernetes regression. See STEP_5K_L_VERIFICATION.md for results. It adds no backend/schema/provider/integration/billing architecture.

A local release candidate is not production-ready. The remote environment has not executed these gates. Mandatory GitHub Actions currently cover backend, PostgreSQL/migrations, frontend, security/dependencies/secrets, containers and their aggregate gate. Browser E2E and performance measurements remain local-first. Uncommitted Step 5K-L work has no exact-SHA remote CI result until publication is separately approved.

AI remains mock. Synthetic stored fixture scores are explicitly test data; mock analyses do not prove intelligence from an external model. Real provider output, latency, failure/cost controls and operations require authorized Step 5I, which remains blocked by remote Step 5H. Docker Desktop Kubernetes uses a local synthetic certificate and retained local PVC; that is not public TLS, managed storage, high availability or remote disaster recovery.

## Remaining production requirements

Select and authorize a remote provider and topology, publish reviewed source normally and require exact-SHA CI, then execute remote Step 5H migrations, health, synthetic browser/security, backup/restore, persistence, rollback and resource validation. Complete authorized real-provider Step 5I afterwards. Establish monitoring/alerts, secrets rotation, backup retention/off-host storage, account/membership operations, resource budgets and support procedures before a production-readiness claim. The current process-local login limiter, synchronous single-worker analysis, offset/substrings and row-wise bounded import remain scaling limitations. Billing, plan enforcement and external integrations are not implemented by this milestone.

## Provider requirements checklist (selection is pending)

Railway or Render are user-proposed candidates, not selected or deployed here. Evaluate a candidate against these architecture requirements; this document makes no current capability or price claims about either provider.

- Run the reviewed non-root Docker backend and production frontend/Nginx images; preserve same-origin /api routing, trusted proxy/HTTPS handling and the existing CSP/cookie policy.
- Provide PostgreSQL compatible with the verified 16.15 baseline, private connectivity, bounded connections and application/migration/backup roles with the existing least-privilege policy.
- Persist PostgreSQL state or use a managed database. The backend/frontend are stateless; CSV preview tokens, sessions and imported rows use the database, and CSV uploads are not a durable filesystem feature.
- Execute a one-shot Alembic upgrade and required-head check before application readiness. Supply a controlled migration identity; never replace migration with create_all.
- Inject secrets through the platform's secret mechanism, separate environments and roles, and rotate credentials without placing them in images/repository/logs. Remote synthetic staging must explicitly retain mock AI.
- Expose reviewed liveness/readiness endpoints, wait for database/schema readiness, configure logs/request-ID collection and define alerting/restart behavior.
- Terminate TLS correctly at the edge; plan an approved domain/public certificate later. Local certificate exceptions are not remote TLS evidence.
- Define off-host encrypted backup storage/retention, scheduling and access, and prove a fresh-target restore and rollback on the selected platform.
- Measure remote CPU/memory, worker and PostgreSQL connection sizing with synthetic traffic. Local samples are starting evidence, not a remote budget or SLA; synchronous analysis and password hashing need headroom.
- Expect a frontend/edge service, a backend service and PostgreSQL, plus migration and backup tasks. A platform edge may replace the local ingress container only after proxy/security behavior is verified.

No accounts/resources have been created, no provider has been chosen, and no remote deployment or Step 5I has been started. Next checkpoint is review of the exact Step 5K-L commit scope, then separately authorized normal publication and exact-SHA CI.
