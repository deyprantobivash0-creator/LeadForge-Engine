# E03 scoped execution principals

Date: 2026-10-12. Baseline main `46527419001919aa2f05a1fb3964a5042fe6919c`. Local implementation, pending review. No migration or E04 permission implementation.

## Existing identity and tenant flow

AuthSession is an authenticated, expiring/revocable global User identity. Cookie/token validation and active-user checks live in AuthenticationService and auth dependencies. A browser's X-Organization-ID selects a workspace; it is not authority. OrganizationAuthorizationService resolves active membership joined to an active organization. CSRF is separately checked for writes. AuthorizedOrganizationContext carries ORM User, Membership and Organization for request handling; services/repositories generally receive integer organization IDs, without execution provenance.

| Command | Before / retained boundary | E03 integration |
|---|---|---|
| Lead create | Route validates LeadCreate and membership/CSRF, passes authorized organization ID; service owns transaction | USER principal adapter -> create_lead_for_principal -> existing service/repository |
| Lifecycle change | Same auth/tenant/CSRF boundary; repository scopes Lead ID and organization | USER principal adapter -> update_lifecycle_for_principal -> existing service/repository |
| CSV preview/confirm | Explicit organization/user IDs and session-bound preview signature; service-owned batch transaction | Retained; no principal threading in this epic |
| Lead processing | Explicit organization/Lead IDs; fenced claim and snapshot, provider outside transaction, atomic completion/history | Retained standalone phased operation; not migrated to a worker |
| Password change | Account-only validated AuthSession; guarded password update + other-session revocation | Retained; tenant principal is inappropriate for a global account command |
| Login/session issuance/logout | Credential authentication precedes workspace selection; guarded issuance and service transaction | Retained; no artificial tenant or machine User |

Query/read paths retain their existing context. Existing tests construct disposable organizations/users/sessions and invoke integer-scoped services; those lower-level calls remain supported. No live default tenant is introduced. The unused development default-organization helper remains quarantined. RequestIDMiddleware maintains a request-ID ContextVar for logging; it is correlation only. There is no ambient actor/tenant state used by the new command services.

## Value object and validation

`backend/schemas/execution_principal.py` defines frozen Pydantic ExecutionPrincipal and ActorReference models with forbidden extra fields and instance revalidation. They are application values, not ORM entities. No Session, cookie, token, credential, permission result or model prompt is included.

| Field | Contract |
|---|---|
| principal_type | Exactly USER, SYSTEM, AGENT, WORKFLOW or INTEGRATION |
| actor_id | USER: strict positive signed-64-bit integer User ID; machines: bounded stable ASCII string, never a fake integer User ID |
| organization_id | Required strict positive signed-64-bit integer for every tenant principal; bool/string coercion rejected |
| correlation_id | Required nonempty safe ASCII identifier, max 64; generated UUID4 hex if omitted |
| delegated_by | Optional single immutable ActorReference (type + actor ID); no recursive chain |
| workflow_run_id / integration_id / agent_id | Optional bounded stable provenance identifiers; matching field required and equal to actor_id for that principal type |

Direct USER principals cannot claim machine/delegated provenance. AGENT can also carry its workflow/integration provenance. SYSTEM requires an explicit named actor and organization; there is no global SYSTEM constructor or authorization bypass. A platform-global operation would require a separately designed context and authorization boundary.

Factories `for_user`, `for_system`, `for_workflow`, `for_agent` and `for_integration` have typed parameters and invoke normal model validation. They validate shape, not membership, machine registration or grants. Ordinary internal code can build a principal, so object construction alone is never an authentication proof.

## Trusted construction boundaries

For the two migrated HTTP writes:

```text
validated browser session / active User
  -> existing organization selector + active membership + CSRF
  -> require_user_principal
  -> bound USER principal with validated request correlation
  -> service-owned command scope
  -> identity/organization match check
  -> existing tenant-scoped repository
```

The adapter accepts existing validated context and separately authenticated User, checks context/user/membership/organization bindings and active flags, then re-resolves live membership through the existing authorization service. A manually assembled dataclass is not treated as an authorization stamp. The adapter does not accept raw actor/type selectors. Existing LeadCreate/lifecycle payloads still reject extra fields; no public principal-deserialization endpoint exists. Authentication, CSRF, response schemas and membership rules remain authoritative and unchanged.

Future non-HTTP construction is possible without Request or browser Session data:

```python
principal = ExecutionPrincipal.for_workflow(
    "run-1", organization_id,
    delegated_by=ActorReference(principal_type=PrincipalType.USER, actor_id=user_id),
    correlation_id="command-chain-1",
)
LeadService(db).create_lead_for_principal(
    principal, organization_id=organization_id,
    company="Synthetic", email="synthetic@example.com", source="test",
)
```

This example represents trusted application execution after a future ingress authenticates the machine/delegating authority. It is not permission to run a machine command from a caller-supplied JSON envelope. No worker, machine credential, registration, expiry/revocation store or grants are implemented. E04 must supply live action/resource authorization; later transport adapters must verify producer/provenance before trusting deserialized values.

## Service and transaction trust rules

The new explicit principal entrypoints are create_lead_for_principal and update_lifecycle_for_principal. The bounded create/lifecycle slice proves HTTP-to-service and worker-style execution without churning imports, processing, queries or auth. Legacy integer-scoped methods remain trusted internal mutation steps used by those entrypoints and E02 tests. They are not new external identity ingress and must not be called by future unverified machine transports to bypass principal construction.

Both principal entrypoints use E02 service_transaction. They require an actual validated ExecutionPrincipal, revalidate even an invalid internal model_copy/model_construct, reject a mismatched explicit organization before repository access, and pass the organization to the unchanged tenant predicates. Missing/invalid context raises safe 400 identity errors; explicit tenant mismatch raises 403 EXECUTION_TENANT_MISMATCH. A valid tenant principal targeting another organization's Lead returns the existing not-found result/HTTP 404; SYSTEM receives the same behavior.

Nested command scopes join the same outer transaction. The caller passes the same immutable principal explicitly, preserving correlation and provenance; failure rolls back the whole logical command under E02. No Session.info/ContextVar/global actor or tenant is inferred. Repositories still scope by organization; the principal does not replace defense in depth.

## Correlation, delegation and serialization

HTTP uses the existing RequestIDMiddleware value in request.state. That middleware accepts one bounded safe X-Request-ID or generates UUID4 hex for missing/invalid/duplicate input. Accepted caller correlation is nonsecret diagnostic data, never authentication or authorization. Standalone principals generate UUID4 hex or validate an explicitly preserved ID. A child preserves correlation intentionally; a newly generated correlation starts a different diagnostic chain. No distributed tracing infrastructure was introduced.

Delegated_by identifies the immediate upstream actor. For User -> Workflow -> Agent, the Workflow refers to User, the Agent refers to Workflow, and workflow_run_id/correlation connect records. Earlier hops must live in future trusted execution/audit records; the value object does not recursively embed history or prove that delegation was allowed. Tenant/grant/version/expiry validation of that chain remains E04/later work. Provenance cannot broaden authority.

`to_json` uses stable declared field order and JSON primitives including explicit null optional fields. `from_json` validates the same field/type rules and rejects unknown principal types/extra fields; a round trip preserves all identity fields. This initial application schema is not bound to Temporal types. Deserialization validates shape only. Untrusted external JSON must never automatically become trusted execution identity, and logs should not render validation inputs.

## Logging, handoff and remaining debt

The existing safe logger allowlist now includes principal_type, actor_id and correlation_id. The two command entrypoints emit bounded execution.lead.create/lifecycle diagnostics with those fields plus organization_id, without Lead payload, delegation blob or transport credentials. The events occur before outer commit and are not durable audit records; E05 remains unimplemented.

E04 receives explicit type-aware actor, organization, immediate authority provenance and correlation. It must define authenticated machine bindings, action/resource permissions, live membership/grant revocation/expiry and delegation limits without granting SYSTEM special privilege. No role, policy decision, capability matrix, approval logic, audit/run/agent/integration table or new transport authentication is added here.

The old roadmap's possible E03 migration referred to persistent principals/grants; this authorized slice deliberately uses a value object. No architecture correction or masterplan/roadmap edit is necessary. Broader principal threading, trusted machine ingress, durable provenance chains and schema evolution are explicit remaining work. Actual PostgreSQL testing is not claimed by this local epic. See [acceptance report](E03_ACCEPTANCE_REPORT.md).
