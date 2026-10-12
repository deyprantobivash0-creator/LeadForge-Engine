# E03 acceptance report

Date: 2026-10-12. Approved starting main HEAD `46527419001919aa2f05a1fb3964a5042fe6919c`. Local implementation only, pending code review. [Identity contract and audit](E03_SCOPED_EXECUTION_PRINCIPALS.md).

**STATUS: PASS for local E03 implementation and the supported backend suite.** No deployment approval or live machine-authentication claim.

## Scope

Production files:

- New `backend/schemas/execution_principal.py`: immutable typed value objects, principal factories, tenant/actor/provenance/correlation validation and JSON round trip.
- New `backend/api/dependencies/execution_principal.py`: USER adapter over existing authenticated identity, membership and CSRF; checks context binding and re-resolves live membership.
- New `backend/services/execution_identity.py`: tenant identity consistency check and bounded diagnostic fields; no permission policy.
- `backend/api/routes/lead_routes.py`: create/lifecycle writes use the USER principal dependency and principal service entrypoints; HTTP contracts preserved.
- `backend/services/lead_service.py`: principal-aware create entrypoint joins E02 transaction and delegates existing mutation.
- `backend/services/lead_lifecycle_service.py`: principal-aware lifecycle entrypoint, same transaction and tenant filters.
- `backend/core/logger.py`: adds three safe identity fields to the existing allowlist.

Tests added: `tests/test_execution_principals.py`. Existing test files unchanged. Documents added: this report and `docs/v2/E03_SCOPED_EXECUTION_PRINCIPALS.md`. No frontend, dependency manifest, model, migration, deployment, masterplan or roadmap changes.

## Verification

Commands use the existing `.venv-ci/Scripts/python.exe -B -m pytest -p scripts.ci_pytest -q -p no:cacheprovider` with `LEADFORGE_CI=1`, disposable SQLite and mock AI. Tests never import the application against leadforge.db.

- Initial affected regression suite: 87 passed in 39.05s.
- New principal test first run: 41 passed, one test-helper signature error; corrected the helper call without changing production behavior.
- Final expanded focused suite: **172 passed in 55.60s**; includes all **42 principal tests**, **22 E02 transaction tests**, auth/password change, tenant Leads/attack matrix, imports, processing and observability.
- Full backend: **506 passed, 40 subtests passed in 108.69s**, no failures/skips. Count increased from E02's 464 by the 42 new principal tests. Existing naive-UTC deprecation warnings remain.
- Dependency consistency: pip check passed. Existing pip-audit installed-environment audit passed: no known vulnerabilities found; no dependency changes. An unsupported initial CLI flag combination was corrected to installed-environment mode.
- Existing Gitleaks 8.30.1 with repository configuration and full redaction passed against the ten E03 files. Whitespace checks pass, including separate checks of untracked additions.
- Existing file hashes match outside the four intentionally edited production files; login-script metadata and established database checksum match. HEAD remains the approved starting commit, the index is empty, and the only new paths are the six E03 additions listed above.

Principal tests cover all five valid types, missing actor/organization, strict IDs, wrong machine provenance, unknown types, immutability, stable JSON, forbidden secrets/permission fields, generated/preserved correlation, unsafe correlation rejection, bounded delegation, authenticated HTTP mapping, forged user/context/tenant rejection, membership revocation, raw client principal rejection, machine-header spoofing, tenant mismatch rollback, SYSTEM cross-tenant denial, invalid copied models, worker-style non-HTTP invocation and shared identity in nested service calls/logs.

## Security self-review

No E04 authorization decisions were added. No principal has permissions or an is_privileged flag. SYSTEM is tenant-bound and uses the same repository predicates. Actor and organization selectors from new headers/payloads are not trusted; the existing HTTP membership/CSRF boundary remains the source. Serialized principal validation is not producer authentication and factories are trusted internal construction utilities, not publicly authenticated machine endpoints. No machine actor is represented as a fake User.

The adapter rejects inconsistent user/membership/organization objects and rechecks current membership. Repository SQL tenant predicates are unchanged. Principal services reject explicit tenant mismatch before mutation and still scope resource lookup; nested failure rolls back the outer command. Correlation is bounded, printable, nonsecret and cannot select authority. Delegation is one typed reference, with no recursive metadata graph or implied permission. No ambient actor/tenant state, cookies, session IDs, tokens, secrets, generic execution dictionaries or provider authority were introduced. Logs remain operational diagnostics, not E05 audit evidence.

Auth/login/password/session services remain unchanged. CSV and processing retain existing execution context and service-owned transactions; this deliberately small create/lifecycle slice does not claim backend-wide principal adoption or production-ready machine grants.

Migration required: **NO**. No database persistence is needed for this value object. No E04+, Temporal dependency/resource, staging PostgreSQL access/mutation, Render mutation, commit, push or deployment is authorized or performed. Unrelated work and the temporary login script are preserved.

Established leadforge.db SHA256: `217e5d8a5128936be5fb5fee8fe1f54036f9106e318514da5e6e98d485221a4a`. The operator login script was checked by metadata only, not inspected or executed. Environment-secret contents were not read. No local PostgreSQL or external provider was used.

E03 implementation complete locally. Awaiting code review before commit.
