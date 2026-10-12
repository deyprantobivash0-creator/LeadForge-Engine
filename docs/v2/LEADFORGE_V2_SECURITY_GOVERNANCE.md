# LeadForge V2 security and human governance

Proposed controls, dated 2026-10-12; no policy engine or compliance certification currently exists. Existing authentication, CSRF, tenant scoping, Argon2id/session guards, safe diagnostics and attack tests remain the baseline. Consult [domain ownership](LEADFORGE_V2_DOMAIN_MODEL.md) and [execution architecture](LEADFORGE_V2_ARCHITECTURE.md).

## Authority model

Separate **identity**, **workspace membership**, **resource permission**, **agent/tool capability**, **action policy**, **commercial entitlement**, and **execution state**. Passing one does not satisfy the others. Owner/admin/member are current labels, not an implemented V2 permission model.

Proposed role defaults: owner manages workspace/policy/integrations/billing; admin manages members/campaigns within delegated limits; operator prepares/runs permitted campaigns; reviewer decides eligible approvals; analyst reads scoped metrics/evidence; service principals get explicit machine grants. Keep existing role compatibility initially; new roles/permissions need migration and API review. Platform hard restrictions apply to owners too. Approval requester cannot self-approve actions requiring separation of duties.

Browser mutations retain existing cookie/CSRF architecture. Machine/webhook authentication is a separate transport mechanism feeding the same authorization services, not another password system or blanket CSRF exemption for browser APIs. Service grants bind tenant, tools/actions/resources, expiry, budget, issuer and revocation version. Resource scoping is checked in SQL before aggregation/ranking, checkpoint access, retrieval or export. Defense-in-depth PostgreSQL RLS is a future assessed option, not claimed current protection; connection-pool tenant context and bypass roles must be tested before adoption.

## Policy engine contract

Input is a typed ActionContext: actor/principal and live grants, organization, action type, channel, campaign/version, account/contact/lead, endpoint/recipient, exact payload hash, risk, confidence/evidence freshness, cost/currency upper bound, entitlement, jurisdiction, time/window, consent/lawful-basis evidence, suppression, stop epoch and connection state.

Output is **ALLOW**, **DENY**, or **REQUIRE_APPROVAL**, with deterministic reason codes, matched rule IDs/versions, evidence refs, required constraints/approver quorum, expiry, estimated cost and decision hash. Missing critical data, invalid schemas, unavailable authority checks or contradictory jurisdiction evidence fail closed for external effects. AI may estimate risk or propose rules; it cannot supply the authoritative result or change rules.

Rule precedence: platform hard deny → legal/source/suppression/stop deny → tenant/campaign restrictions → grants/entitlements/budget → approval requirements → allow. Deny wins; multiple approval requirements combine rather than cancel. Campaign rules can tighten workspace policy; exemptions require authorized, expiring, audited configuration and cannot override legal/platform hard denies. Decisions are reproducible from versioned inputs; execution also uses current policy, not only the pinned plan version.

Example policy, illustrative rather than executable configuration:

| Condition | Decision | Reason |
| --- | --- | --- |
| Organization/campaign stopped, revoked grant, suppressed endpoint | DENY | Execution disabled or communication prohibited |
| Missing jurisdiction/required permission evidence for voice | DENY | Eligibility unknown |
| First external touch or approved risk threshold exceeded | REQUIRE_APPROVAL | Human recipient/content review |
| Proposed spend exceeds reservation/goal ceiling | DENY or new budget approval proposal | No unauthorized overspend |
| Low-confidence reply contains contract/pricing commitment | REQUIRE_APPROVAL | Human negotiation authority |
| Permitted reminder, supported claims, eligible contact, valid budget and approval binding | ALLOW | All required controls satisfied |

## Approval object and lifecycle

ApprovalRequest stores request ID/tenant/requester/run, reason, structured evidence, exact proposed action/target/content hash, risk/confidence/cost, policy version, eligible approver role/resource scope, requested_at/expiry, required quorum, decision records (approver, decision, timestamp, rationale), and separate execution status.

```text
pending → approved / denied / expired / invalidated
approved + unchanged payload + live eligibility → authorized action
changed recipient/content/cost/window/policy → invalidated → fresh request
```

Approve/deny endpoints validate current membership, permission, request version and eligibility; decisions are single-use/idempotent and immutable. Approval links reference an object; they contain no reusable execution secret. Chat approvals additionally verify paired external identity, tenant, message callback nonce and request version. High-impact actions require web step-up authentication rather than a generic chat “yes.”

At dispatch, recheck approver eligibility, rule changes, current suppression/consent, budget reservation, connection grants, campaign state and stop epoch. A historical approval does not grandfather revoked permissions. Race tests must cover opt-out or stop between approval and provider acceptance. Protective actions such as pause/opt-out can operate under narrow dedicated capabilities; they cannot increase autonomy.

## Action security and emergency stop

Dispatcher accepts only immutable ActionIntent IDs and constrained parameters; no generated shell/SQL or provider credentials. In a short transaction, reauthorize, reserve cost, claim a fenced execution attempt and record audit. External provider call occurs outside that transaction. Recheck revocation epoch immediately before the effect; disclose the remaining provider-bound race and reconcile as described in architecture.

Organization stop blocks all new external dispatch; campaign pause blocks new touches in that campaign, invalidates queued capabilities and propagates cancellation. It does not discard evidence or reply ingress. Resume requires explicit permission and fresh checks. A sender/call already accepted by the provider may be irreversible. UI must distinguish blocked queued work, acknowledged workers and still-in-flight provider operations.

## Secrets, OAuth and webhook boundaries

Keep raw secrets in an encrypted vault/credential store with envelope keys and credential references in PostgreSQL. Rotation/revocation and tenant ownership are explicit. Never send secrets to models, return them in schemas, place them in URL query strings, persist them in browser storage, or log payloads. OAuth scopes are minimum per capability; use state/nonce/PKCE where supported, pinned redirect URIs, single-use callback state and a refresh-token concurrency guard. Refresh/reconnect is not an opportunity to broaden scopes silently.

Webhook endpoints bind to a connection before resolving tenant, verify provider authenticity over required raw bytes/URL/parameters, enforce size/rate/replay controls and store inbox dedupe IDs. Do not copy a universal HMAC scheme across providers. Twilio request validation depends on the provider's canonical request inputs and SDK validator; reverse-proxy URL handling must be tested. [Twilio webhook security](https://www.twilio.com/docs/usage/webhooks/webhooks-security).

Untrusted webhook bodies, source pages, chat text and transcripts are data. Egress controls deny internal/metadata hosts, private ranges and redirect bypass; source adapters allow permitted domains and content types. No agent remote plugin/skill installation or arbitrary browser automation as a discovery shortcut.

## PII, provenance and retention

Classify credentials, identifiers, contact endpoints, message bodies, recordings/transcripts, commercial facts and aggregate analytics separately. Encrypt transport/storage, restrict artifact access by tenant and role, and expose short-lived downloads through authorization. Keep operational logs content-free. Audit records retain IDs/hashes and decision metadata; full content is separately governed.

Proposed retention policy must be workspace/jurisdiction/contract specific. Define artifact expiry, audit retention, provider data-deletion capability, deletion SLA, backup expiry and legal holds before enabling collection. No universal retention duration is asserted here. Deletion service enumerates facts, artifacts, projections, embeddings, checkpoints, conversations and provider copies; tombstones prevent re-import. Backups may not support individual erasure; expiry and restore-time deletion replay must be documented. Preserve minimal suppression tokens only with an approved purpose/retention basis; avoid recontact after “delete.”

Export is tenant-scoped, permissioned, audited, asynchronous and minimized; use CSV formula neutralization and expiring downloads. Support verified data-subject requests with contact matching rather than treating workspace ownership as proof of data-subject identity. Restore starts with dispatch disabled and deletion/suppression reconciliation.

## Communication and jurisdiction governance

ContactEndpoint has permission evidence, channel/purpose, jurisdiction/recipient type, collection source, verification state and opt-out history. A discoverable or verified address is not automatic authorization to contact it. Unknown eligibility denies autonomous sending until reviewed. Suppression includes organization/contact/channel/purpose scope, reason, source event and effective time; campaign overrides cannot clear global channel prohibitions.

Unsubscribe and stop expressions are processed deterministically before AI classification, with minimal public single-purpose unsubscribe endpoints rather than authenticated browser-CSRF requirements. Replays are idempotent; eligibility checks occur for every queued touch. Hard bounce invalidates endpoint; complaints/opt-out stop relevant enrollments; soft bounce/temporary failures follow a bounded approved policy. No opt-out notification includes unnecessary contact details.

A legal review must produce a versioned jurisdiction matrix for recipient class, channel, purpose, sender location, recording, synthetic voice and retention before launch. Email and messaging rules vary; UK corporate/individual distinctions and personal-data processing are separate considerations. [ICO electronic mail guidance](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/electronic-and-telephone-marketing/electronic-mail-marketing/). US commercial-email controls should be reviewed against the [FTC CAN-SPAM guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business). These references motivate separate controls, not a claim of worldwide compliance.

Synthetic voice must have a separately approved legal/channel profile, AI disclosure script, consent evidence where required, recording policy, do-not-call screening, caller identity, approved time window, duration/spend limits and usable human transfer. US FCC guidance treats AI-generated voice under artificial/prerecorded voice rules; counsel must check current applicable requirements/exceptions before implementation. [FCC declaratory ruling](https://docs.fcc.gov/public/attachments/FCC-24-17A1.pdf). A disclosure alone is not consent, and human approval cannot legalize an otherwise prohibited call. The UAE goal example remains blocked for external actions until its jurisdiction profile is approved.

## Audit, explainability and abuse controls

AuditEvent stores actor and delegated principal, tenant/resource, command/action/run, state transition, policy/approval versions, input/output evidence hashes, provider receipt reference, cost and timestamps/correlation. Append through a restricted writer, export integrity batches to protected immutable storage, audit privileged access and key rotation. Hash chains are tamper-evidence only when anchors and write permissions are protected; JSON diagnostic logs are not the enterprise audit ledger.

“Explain This” resolves a decision ID into authorized source evidence, score/rule versions, constraints, approving actors, executed payload/receipt and outcome uncertainty. It must say when evidence expired, was inferred or was contradicted. Do not produce post-hoc invented justification or expose hidden chain-of-thought, other tenants, secrets or unrestricted transcripts.

Distributed rate/abuse budgets cover authentication, API, webhook ingress, discovery, model/tool calls, dispatch and channel sender reputation. The current process-local limiter remains until intentionally replaced; multi-worker budgets require atomic shared counters/reservations. Billing entitlements never bypass safety budgets. Suspicious mass export, failed command auth, prompt-injection attempts, spend spikes and send anomalies generate auditable alerts and protective pauses.

Release gates include tenant attack matrices across queues/checkpoints/vector retrieval, permission revocation mid-run, separation of duties, approval TOCTOU, signed webhook negative tests, concurrent reservations, duplicate/unknown delivery, stop propagation, PII redaction, deletion/export/restore and legal-profile fixture tests. No autonomous channel is enabled without an owner, runbook, kill switch and measured incident recovery.
