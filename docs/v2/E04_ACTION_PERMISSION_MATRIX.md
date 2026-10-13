# E04 action permission matrix

Date: 2026-10-12. Baseline main `9927177bb11403a0af54d4bd175eb0b6b2c3dbd4`. Local implementation pending review. Structural authorization only; no schema migration or E05/E10/E11 implementation.

## Existing authorization audit

| Path / check | Classification | Existing behavior / E04 scope |
|---|---|---|
| AuthSession token, expiry/revocation, active User | AUTHENTICATION | Existing auth dependencies/services remain authoritative |
| X-Organization-ID parsing | TENANT MEMBERSHIP input selection | A selector alone grants no authority |
| Active membership joined to active Organization | TENANT MEMBERSHIP | Required before all customer routes; retained |
| Membership role owner/admin/member | ROLE AUTHORIZATION metadata, previously not action-enforced | DB check constrains names; no registered command-specific role comparisons found |
| Lead create | TENANT MEMBERSHIP + BUSINESS INVARIANT | E03 principal adapter, tenant/email uniqueness; now lead.create at principal service boundary |
| Lifecycle mutation | TENANT MEMBERSHIP + BUSINESS INVARIANT | Allowed lifecycle vocabulary and tenant resource lookup; now lead.lifecycle.change |
| Lead processing | TENANT MEMBERSHIP + BUSINESS INVARIANT | Fenced claim/completion, provider limits/configuration; existing phases retained, permission taxonomy defined but processing enforcement not migrated |
| CSV preview | TENANT MEMBERSHIP + BUSINESS INVARIANT | CSRF, bounded parse, signed digest/user/session preview; retained |
| CSV confirmation | TENANT MEMBERSHIP + BUSINESS INVARIANT | Now USER principal, lead.import and lead.create before batch mutation; closes alternate registered Lead-creation path |
| Reports / intelligence / Lead reads | TENANT MEMBERSHIP | SQL organization predicates, no differentiated role restrictions; retained read enforcement |
| Settings / workspace list | TENANT MEMBERSHIP | Read-only; role displayed, not a client grant; no management command exists |
| Password change / session commands | AUTHENTICATION + BUSINESS INVARIANT | Account-only guarded credential/session semantics, CSRF; excluded from organization permission checks |
| Mock/provider environment constraints | POLICY-LIKE CHECK / configuration safety | Not a structural action role decision; unchanged |
| Development/bootstrap/provisioning | Operator/development safety boundaries | Outside customer authorization; not executed or changed |

No implemented role-based distinction among owner/admin/member was found for these current workspace actions. Their equal mapping preserves behavior; it does not infer new management capabilities. Future member/workspace management needs its own reviewed action mapping. No unknown/ambiguous role receives permission.

## Typed taxonomy and human matrix

ActionPermission is a StrEnum with stable serialized values. No wildcard, admin/write/execute-everything primitive exists. Raw strings are not trusted permissions in the evaluator/capability constructor.

| Action | owner | admin | member | Enforcement in this epic |
|---|---|---|---|---|
| lead.read | Permit | Permit | Permit | Taxonomy; existing read membership/filter rules retained |
| lead.create | Permit | Permit | Permit | Principal create service + CSV confirm |
| lead.lifecycle.change | Permit | Permit | Permit | Principal lifecycle service |
| lead.process | Permit | Permit | Permit | Taxonomy; existing process path retained |
| lead.import | Permit | Permit | Permit | Principal CSV confirm service |
| analysis.read | Permit | Permit | Permit | Taxonomy; existing read rules retained |
| report.read | Permit | Permit | Permit | Taxonomy; existing read rules retained |
| workspace.read | Permit | Permit | Permit | Taxonomy; existing workspace/Settings rules retained |

ROLE_PERMISSIONS is immutable and explicitly enumerates the current action set; extending the enum does not automatically grant a new action. Unknown roles/actions deny. All known roles currently receive the implemented action set, so there is no invented restricted human role or arbitrary removal of an existing feature. A trusted narrowed human snapshot can only intersect this role set, demonstrated in evaluator/delegation tests; it cannot expand a role.

Campaign/outreach/approval/voice/integration-management categories are future documentation concepts only. No runtime permission for nonexistent operations was added. Self-security is excluded because account authentication is not an organization grant.

## Identity and authority separation

ExecutionPrincipal remains unchanged: who/type/tenant/provenance/correlation, no permissions. Frozen HumanAuthorizationContext and MachineAuthorizationContext bind a principal to a frozenset of actual ActionPermission enum members. Mutable sets, arbitrary strings and wildcard capabilities are rejected. The action enum makes capability count finite and bounded.

HumanAuthorizationContext is a trusted current-membership snapshot, not an accepted client role. ActionPermissionService never accepts a supplied human snapshot as service authority. For USER it selects the scalar membership role through PermissionRepository, joining active User, Membership and Organization with explicit tenant/user predicates. Scalar reads bypass stale ORM identity-map role/active fields. No long-lived role/permission cache is introduced. Missing/inactive membership/user/organization produces no authority. A supplied machine/human context cannot replace USER's live database authority.

MachineAuthorizationContext is an explicit trusted internal assignment to the full immutable principal, including tenant, actor, run/provenance and correlation. SYSTEM, AGENT, WORKFLOW and INTEGRATION all need granted capabilities; no type shortcut exists. Missing context or missing requested capability denies. A context for another actor, run/correlation or organization denies.

There is no persistent machine grant table, machine HTTP ingress, transport token or grant deserializer. Trusted code may construct a root context from an approved capability set; future ingress must authenticate the producer and bind approved tenant/actor authority before constructing it. Machine context to_dict returns sorted permission strings and ordinary principal primitives for future envelopes, but that shape is not an authenticated grant. A raw dictionary is rejected by the evaluator. E08 must not blindly trust capability lists from workflow inputs or external JSON.

## Pure evaluator and decisions

evaluate_permission performs deterministic checks only, without database/network/LLM calls. Its frozen PermissionDecision includes result (PERMIT/DENY), typed permission (null for unknown input), principal type and stable reason code. to_dict emits ordinary deterministic primitives suitable for future audit/intent references.

Checks: typed known action -> valid identity/context -> matching target/principal/context tenant -> full principal binding -> matching human/machine context kind -> mapped human role or machine capability -> membership in the effective set. Human effective permissions are role permissions intersected with the context's narrowing set. Machine effective permissions are only the explicitly assigned set.

Reasons: PERMITTED_BY_ROLE, PERMITTED_BY_CAPABILITY, DENIED_PERMISSION_NOT_GRANTED, DENIED_INVALID_CONTEXT, DENIED_TENANT_MISMATCH, DENIED_PRINCIPAL_MISMATCH, DENIED_UNKNOWN_ROLE, DENIED_UNKNOWN_PERMISSION. No input role/capability/unknown string becomes a grant just because it parses or looks safe. The service uses a generic safe 403 ACTION_PERMISSION_DENIED response; operational logs record enum action/result/reason and safe principal IDs, never credentials or capability payloads.

Existing E03 explicit organization mismatches still fail with its safe tenant mismatch error before mutation. Permission context mismatches deny in the evaluator. Valid authority remains subordinate to repository tenant filters; a foreign resource retains not-found behavior. Authorization is not a replacement for resource ownership or business validation.

## Service enforcement and E02 atomicity

The initial implementation failed the final E04 security gate: protected wrappers called older public integer-only mutation methods. HTTP protection was insufficient because supported direct service callers could skip the wrappers. E04-R consolidates each operation into one authorized public command; the failed gate remains architecture history.

| Canonical command | Mandatory authority / permission | Internal mutation detail |
|---|---|---|
| LeadService.create_lead | ExecutionPrincipal; live human membership or explicit machine context; lead.create | _create_lead_internal |
| LeadLifecycleService.update_lifecycle | ExecutionPrincipal; live human membership or explicit machine context; lead.lifecycle.change | _apply_lifecycle_change |
| LeadImportService.confirm | ExecutionPrincipal USER matching session-bound user; live membership; lead.import AND lead.create | _confirm |

The public commands own the E02 scope. Identity, tenant and permission checks occur within that scope before mutation, allowing fresh membership reads and rollback of any earlier outer-command writes on denial. Missing principal fails at argument binding; explicit invalid identity fails closed; a machine with no context/capability is denied. No authority default permits execution. Creation preserves exact uniqueness classification on flush or owning-scope commit failure. Lifecycle retains status validation and tenant-filtered lookup. Confirmation retains signed preview verification, bounded parsing, SQLite outer BEGIN and per-row savepoints. Preview stays nonmutating; no AI processing is started.

create_lead_for_principal, update_lifecycle_for_principal and confirm_for_principal are removed. The service update_status alias had no production callers and duplicated the status subset of update_lifecycle; it is removed, with tests migrated to the canonical lifecycle command. Repository update_status remains a low-level flush-only API, not an application command.

Private helpers neither authorize nor open a service transaction nor commit. They assume an already-authorized command context and participate in the caller's E02 transaction. Leading underscores express the supported API contract, not a Python security sandbox: arbitrary code executing inside the trusted backend with a Session can access helpers/repositories and is outside this structural authorization threat boundary. No route calls a private helper.

### Call-site inventory and migration

Search covered backend/, tests/, tests_postgres/ and scripts/ for definitions, direct calls and method references.

| Classification | Sites / disposition |
|---|---|
| REGISTERED_HTTP_COMMAND | backend/api/routes/lead_routes.py: create route -> create_lead; lifecycle route -> update_lifecycle. backend/api/routes/import_routes.py: confirm -> confirm. Existing authentication/membership/CSRF dependencies remain. |
| INTERNAL_SERVICE_CALL | Old wrappers' calls to unchecked public methods removed. Canonical commands call only their named private helpers; helpers call tenant-scoped repositories. |
| TEST | tests/test_action_permissions.py: all principal commands renamed, foreign fixture uses narrowly authorized create helper, denial sentinel targets _confirm. tests/test_execution_principals.py: commands and route capture renamed, foreign fixture uses create helper. |
| TEST | tests/test_service_transactions.py: create helper grants only lead.create; lifecycle helper grants only lead.lifecycle.change; import fixture creates an active member and supplies a USER principal. Repository-layer calls stay direct. |
| TEST | tests/test_lead_create_conflicts.py: direct integrity-error test uses the fixture's real human principal. tests_postgres/test_postgres_baseline.py: both direct creation calls and both confirmation calls use real fixture USER principals. PostgreSQL tests are migrated but not executed locally. |
| DEVELOPMENT/OPERATOR | No callers of these protected service mutations found in the searched backend/scripts paths. scripts/e2e_fixture.py and scripts/verify_backup_recovery.py construct synthetic ORM Leads as disposable operator fixtures; they are not application command entrypoints and were not changed or executed. Operator login script was excluded from content inspection and execution. |
| DEAD/UNUSED | Public service update_status had only E02 test callers, now migrated. Obsolete wrapper names and raw signatures remain only in intentional rejection regressions. Empty legacy test stubs are not application entrypoints. |

Direct-call regressions cover missing/None/unscoped identity, old positional signatures, unavailable aliases, zero mutation on denial, both import permission halves independently denied, both permitted, private-helper transaction participation, authorized human/machine calls, current membership revocation and repository tenant filtering. Protected operations have no alternate supported unchecked public command.

Processing and read paths remain explicit migration debt: permission defined != permission enforced. Their existing membership/tenant protections are unchanged. E04-R does not extend processing phases or general reads.

## Delegation and non-escalation

delegate_capabilities accepts trusted parent authority, a typed child machine principal and a typed immutable subset. It validates same organization and correlation plus immediate delegated_by matching the parent actor/type. The requested child set must be a subset of the parent's effective permissions. Human -> Workflow -> Agent narrowing is tested; requests for additional capabilities fail rather than silently expand. An empty scope grants nothing. E03 delegation provenance alone still grants no authority.

Root assignment/delegation is not a persistent credential, full trust-chain policy, or proof of identity. Human parent snapshots should be resolved live before delegation. Machine contexts are operation-scoped trusted inputs; no long-lived cache, revocation store, expiry or cross-process authenticating signature is claimed. Persisted/replayed grants require separately reviewed future ingress/lifecycle work.

## Boundaries, handoff and remaining debt

E05 can later append principal/action/result/authority references in the same service transaction; current permission.evaluated events are diagnostics before commit, not an audit ledger. E09 can refer to stable action identifiers. E10 contextual confidence, cost, suppression, jurisdiction and approval rules are not evaluated here. E11 approval is absent. No model/network/prompt authorization exists.

Read routes, import preview and processing retain existing membership/tenant invariants, with taxonomy and explicit migration debt. Account login/password/session operations retain their security boundary and concurrency guards. Concurrent revocation after a permission read remains a transaction/dispatch timing concern; this implementation claims fresh reads for later requests/commands, not instantaneous global revocation. Actual PostgreSQL lock/concurrency testing was not performed locally.

No database/schema/role migration, new dependency, infrastructure, Temporal or future-epic table was needed. The masterplan/roadmap's anticipated persistent grants remain future work; this bounded authorized slice needs no architecture rewrite. See [acceptance report](E04_ACCEPTANCE_REPORT.md) for executed results.
