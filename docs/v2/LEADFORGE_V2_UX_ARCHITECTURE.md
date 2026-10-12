# LeadForge V2 frontend information architecture

Proposed UX, not implemented navigation. Audit baseline 2026-10-12: active React views are Dashboard, Leads, Import, Intelligence, Reports and Settings, with explicit workspace selection. Existing AuthContext/API client, scoped reads, credentials/CSRF and dark workspace styles remain reusable.

## Navigation and ownership

| Destination | User purpose / primary objects | Progressive-release rule |
| --- | --- | --- |
| Mission Control | Goal progress, spend/reservations, operational health, approvals and agent activity | Start as truthful current snapshot; no invented pipeline/meetings |
| Leads | Candidates, qualification, evidence, lifecycle, source and import | Preserve current directory/detail and CSV entry |
| Accounts | Company identity, contacts/buying committee and relationship context | Enable after Account/Contact migration |
| Opportunities | Evidence-backed revenue hypotheses, stage/amount, participants and next actions | Display hypotheses distinctly from confirmed opportunities |
| Discovery | Source eligibility, runs, candidate review, dedupe and monitoring | No search button without provider/license readiness |
| Campaigns | Segments, versions, sequences, draft/approved touches and stop controls | Keep draft/shadow mode until dispatch gates pass |
| Conversations | Unified email/message/call/note/meeting timeline and obligations | Channel status visible; no separate hidden channel memory |
| Agents | Scoped definitions, runs, tool activity, failure and cost | Permission-aware diagnostics, no raw secret/model internals |
| Approvals | Exact action preview, reason/evidence/risk/cost/expiry and decisions | Available before enabling external effects |
| Signals | Observations, sources, freshness, subscriptions and relevance | Inference and external observation clearly labeled |
| Reports | Analysis activity plus future outcomes/cost/attribution | Preserve current report semantics; version new metrics |
| Integrations | Connected accounts, granted scopes, health, revocation and sync | Readiness is not connectivity; disabled states explain prerequisites |
| Revenue Brain | Business facts, ICP/personas/offers, source evidence and versions | Confirmed, observed, inferred and external facts differentiated |
| Settings | Account/security, workspace/members, roles, policy, billing and retention | Existing password/sign-out flow retained; permission-specific sections |

Avoid mounting fourteen empty pages on day one. Group work areas (Operate, Intelligence, Govern, Workspace), expose implemented destinations progressively, and retain explicit capability status rather than fake active controls. Mission Control summarizes with deep links; it does not duplicate every domain editor.

## Interaction model

Every view shows active workspace and meaningful data freshness. Resource URLs are resolved through authenticated tenant APIs; IDs or client preferences are never authorization. Switching workspace aborts in-flight reads, clears caches/run subscriptions, remounts scoped state and prevents late results overwriting the new workspace. Keep `api.js` parsed-JSON behavior and CSRF cookie/header handling; V2 services normalize typed responses without introducing `response.data` assumptions.

Add typed server-state query keys containing organization and resource/filter/version. Use optimistic UI only for reversible local preferences or edits with version conflict recovery; never optimistically show a message as sent, approval as executed or booking as confirmed. New asynchronous mutations return a run reference; durable progress comes from status APIs and scoped SSE/event streams. Reconnect uses last event ID then snapshot reconciliation; streaming tokens are ephemeral preview, validated persisted result is authoritative. Proposed SSE uses existing same-origin cookie authorization; do not place bearer secrets in stream URLs.

## Approval and action surfaces

Approval detail displays recipient/channel, exact message/script or diff, provenance, financial ceiling/currency, evidence age, risk/rules, approver eligibility, expiry and expected side effects. Distinguish approve, deny, request revision and stop. Editing executable content creates a new version/approval; UI cannot reuse an approved badge on changed content. A final server check handles permission loss, expiry or stop between viewing and clicking.

Approval queue supports urgency, cost/risk/channel and campaign filters, keyboard decisions and clear pending/approved/expired/invalidated/executed states. Bulk approval is unavailable until its permission, review semantics and bound payload set are explicitly designed. Confirm high-impact or irreversible actions with a concrete preview, not generic “Are you sure?” prompts. Stop controls remain prominent even when a provider or workflow is degraded; show propagation and irreversible in-flight actions honestly.

## Runs, errors and evidence

Timeline/campaign/run views show queued, running, waiting for approval/event/timer, retrying, completed, failed, cancelled and reconciliation-required states. Show last update, next permitted execution window, budget and blocker. A spinner cannot represent a multi-day approval wait. Failed provider acceptance has an unknown-delivery state and reconciliation action; UI must not encourage another send.

Errors use safe messages and request/run IDs; never expose raw provider errors, stack traces or tokens. Distinguish transport error from an operation failure because a timed-out mutation may have committed. Retry is available only where idempotency/recovery semantics are known. Empty states explain no data versus filtered results versus access/provider configuration failures and offer a permitted next step.

Each “Explain This” link uses a persisted decision ID. Evidence cards show category, source locator, observed/freshness timestamps, confidence/verification, contradiction and allowed drill-down. Counts and progress name their denominator: analyzed Leads, accepted messages, confirmed deliveries, qualified meetings and attributed outcomes are different metrics.

## Accessibility, mobile and animation

Use semantic headings/forms, associated labels, keyboard-visible focus, focus restoration after dialogs, escape behavior, accessible tabs/tables and status announcements. Dense approvals/timelines need reading order and text alternatives; badges must not rely on color. Proposed release gate is WCAG 2.2 AA assessment with keyboard/screen-reader testing, not a current compliance claim.

Mobile prioritizes Mission Control, approvals, alerts, conversation review and emergency stop; keep complex policy/campaign editing usable through progressive disclosure rather than compressed desktop tables. Test at 390, 768, 1024 and 1440 CSS pixels, large text/zoom, long translated content and network loss. Chat owner commands link to web for high-impact review.

Use animation to connect state changes (queued → dispatched, new evidence, approval invalidation) and preserve spatial context. Avoid decorative motion hiding uncertainty or fake progress. Respect prefers-reduced-motion, avoid flashing, avoid focus movement on streaming updates, and never continuously animate waiting/failed states.

## Frontend acceptance gates

Extend existing Playwright tests with mocked/fixture-backed async APIs and real isolated backend flows: workspace switching while requests stream, approval expiry/permissions/version conflicts, no duplicate send UI, timeout reconciliation, stop/resume, empty/error/access states, keyboard/mobile behavior, privacy and deletion. Lint and case-sensitive production build remain required. Channel traces/screenshots must redact message/PII/token content or be disabled where redaction cannot be assured. No new frontend framework is justified merely by the V2 navigation plan.
