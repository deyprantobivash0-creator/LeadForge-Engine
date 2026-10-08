# Product and release hardening (Step 5K-L)

The current product journey is sign in -> select an authorized workspace -> Dashboard -> add a Lead or preview/confirm CSV -> Leads and lifecycle -> Lead Intelligence -> historical UTC Reports -> read-only Settings. This milestone keeps the existing visual language and registered API contracts.

## Recovery and feedback

The root React error boundary contains unexpected render failures, shows a reload action and an opaque support reference, and emits an allowlisted structured browser diagnostic. It deliberately excludes raw exception messages, stacks, component props and customer data. API failures still use page-specific retry states. A failed HTTP response is not a render failure.

Requests have a 90-second bound covering headers and body consumption. A timed-out mutation can still have completed on the server: the message instructs users to refresh/check its result before retrying. No automatic mutation retries are added. Network errors, unavailable records, validation and rate limits have understandable defaults; specific safe domain errors such as CSV errors remain intact. ApiError retains validation details and the response request ID. A late forbidden response from an old workspace cannot refresh the new workspace selection.

Session rejection removes the protected shell and explains that sign-in is required again. Explicit sign-out does not show an expiry warning. No-workspace users are told to ask their administrator for membership, can check access again and can sign out. There is no fake workspace-creation flow; bootstrap/membership administration is currently external to the product UI. Existing single/multiple workspace selection remains explicit, and invalid saved preferences are cleared.

## Forms and customer workflows

Lead creation rejects trimmed blank company/source values, provides associated field messages, focuses the invalid control and maps server validation without exposing submitted values or internal validator text. Native email/required/length checks and backend validation remain authoritative. Duplicate creation keeps its useful workspace-specific 409 explanation. Login, lead creation, detail save and analysis use synchronous in-flight guards; controls restore after failure. Detail mutation errors are alerts rather than success announcements.

CSV upload explains empty/wrong-extension/oversized files while the backend validates actual bytes, encoding, required headers and rows. File replacement is blocked during a pending request. Preview remains non-mutating; explicit confirmation returns actual imported/duplicate/invalid counts. Refresh preview requests a new real token for the same file after an expiry or rejection; choose another file resets the flow. Import history is not supported and is not fabricated.

Reports remain historical analysis events within a UTC period, with an inclusive custom end date and a maximum supported window. The client rejects impossible, reversed and oversized date ranges. Clicking the active preset triggers a real reload instead of a permanent loading state. Empty reports explain how to create analysis activity; export preserves selected-period semantics.

Intelligence identifies the selected Lead, links back to the directory, validates route IDs before requesting data, and distinguishes a persisted failed latest attempt from previous successful intelligence even after reload. Current scores/priorities remain server-derived. Processing has an explicit refresh-status action; no polling loop or client-side scoring is introduced. History keeps server pagination and merges repeated IDs safely.

Lead directory refresh failures retain the last snapshot only for the exact same query and workspace-mounted component. Search/filter changes do not reuse another query's data. Search lengths match backend bounds. Pagination is server-side: 20 visible rows, bounded API page sizes up to 100, deterministic newest-first ordering and tenant-filtered totals. There is no new sorting contract or unbounded client-side paging. The Intelligence landing page intentionally shows six recent Leads and offers Browse all leads.

Dashboard remains a current Lead snapshot with one count per Lead and deterministic latest-successful analysis. Reports count historical events; they are not interchangeable. Settings remains read-only and explicitly labels unimplemented integrations as planned. Provider configuration does not claim connectivity.

## Accessibility and responsive behavior

The document identifies LeadForge; route navigation updates its title and focuses the main landmark without scrolling. A keyboard-visible skip link, visible control focus, existing modal focus containment/Escape/return, labels, invalid-field associations and live status/error announcements support the main flows. Existing mobile Lead cards preserve critical lifecycle, score, priority and actions. Long text wraps in the shell and product panels. Desktop 1440, tablet 768 and mobile 390 widths are checked for page overflow across all six product surfaces; harmless script-like text stays literal React text.

Automated checks are practical behavioral assertions and label/landmark/overflow checks, not an axe audit or WCAG certification. A local mobile screenshot is inspected separately. Chromium is the current browser target; assistive-technology/device matrices and exhaustive contrast certification remain future validation.

## Cleanup and limitations

Static import/reference tracing proves the old AIIntelligence page and its six components in components/ai are unreachable from the application entry point. They are removed because they contain obsolete demo metrics/provider claims and unused imports. Shared reusable components and quarantined backend architectures are retained. No TODO/FIXME/HACK/XXX, console.log, debugger or no-op href="#" controls were found in the scanned current frontend/backend JS/JSX/Python source; legitimate input placeholders and mock test/provider code are retained.

Two existing AuthContext lint warnings remain: the context exports useAuth alongside its provider, and session restoration changes state from an effect. They are functional existing patterns; no dependency or broad auth refactor is introduced to suppress warnings.

Deferred capabilities include UI account/workspace administration, durable import history, distributed login limiting, background analysis workers, enterprise search/cursor pagination, integration connections and billing. Remote infrastructure/provider validation is separately deferred. The commercial packaging is unchanged. No runtime or development dependencies are added, and no backend/schema/migration behavior changes.

## Reproduction

Run the existing full backend/PostgreSQL/frontend/security/container gates with scripts/ci.py, actionlint and Gitleaks. Run two isolated product rehearsals:

```powershell
python scripts/verify_e2e_local.py --product-hardening --evidence .staging-artifacts/5k-l/complete-1
python scripts/verify_e2e_local.py --product-hardening --evidence .staging-artifacts/5k-l/complete-2
```

The optional runner mode uses the existing fresh production-built Nginx/FastAPI/PostgreSQL runtime, synthetic fixtures and real CSRF/session/tenant checks. Browser-only negative cases intercept transport responses locally; there is no production fault endpoint. It performs 30 reads per established endpoint, restart recovery and retained-failure browser checks rather than repeating the full concurrency campaign. Each project removes only its own containers/networks/disposable volume. Generated reports, images and archives remain ignored. See STEP_5K_L_VERIFICATION.md for exact final evidence.
