import { useEffect, useRef, useState } from "react";
import { getDecisionChange, getDecisionHistory, recordCurrentDecision } from "../../services/revenueDecisionService";
import "../../styles/revenue-decision.css";

const actions = { RESEARCH_MORE: "Research more", HUMAN_REVIEW: "Human review", QUALIFY: "Qualify", PREPARE_OUTREACH: "Prepare outreach", NURTURE: "Nurture", DEPRIORITIZE: "Deprioritize" };
/** @type {Record<import('../../types/revenueDecision').ChangeDirection, [string,string]>} */
const directions = { IMPROVED: ["↗", "Improved"], DECLINED: ["↘", "Declined"], MIXED: ["↔", "Mixed changes"], UNCHANGED: ["=", "Unchanged"] };
/** @type {Record<string,string>} */
const labels = { INSUFFICIENT_DATA: "Insufficient data", LOW_CONFIDENCE: "Low coverage confidence", CONFLICTING_SIGNALS: "Conflicting signals", INVALID_ANALYSIS: "Invalid analysis", STALE_ANALYSIS: "Stale analysis", UNKNOWN_LIFECYCLE: "Unknown lifecycle", LOW_ASSESSED_FIT: "Low stored fit estimate", ANALYSIS_IN_PROGRESS: "Analysis in progress", company_profile: "Company profile", contact_details: "Contact details", company_assessment: "Stored company estimate", contact_assessment: "Stored contact estimate", intent_assessment: "Stored intent estimate", lifecycle_state: "Lifecycle state" };
const sources = { lead_record: "Lead record", stored_assessment: "Stored estimate · not externally verified", policy: "Neutral default · not an observed signal" };
/** @param {number} value */
const percent = (value) => `${new Intl.NumberFormat("en", { maximumFractionDigits: 4 }).format(value * 100)}%`;
/** @param {number} value */
const signed = (value) => `${value > 0 ? "+" : ""}${value}`;
/** @param {string} value */
const timestamp = (value) => new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "medium", timeZone: "UTC" }) + " UTC";
/** @param {boolean} value */
const review = (value) => value ? "Human review required" : "No human review required";

/** @param {{items:import('../../types/revenueDecision').DecisionEvidence[]}} props */
function Evidence({ items }) {
  return items.length ? <ul className="decision-evidence">{items.map((item, index) => <li key={`${item.signal}-${index}`}>
    <strong>{labels[item.signal] || item.signal.replaceAll("_", " ")}: {item.observed_value}</strong>
    <span>{sources[item.source]}</span><p>{item.effect}</p>
  </li>)}</ul> : <p>No supporting evidence entries.</p>;
}

/** @param {{value:import('../../types/revenueDecision').DecisionContent}} props */
function DecisionDetails({ value }) {
  return <div className="decision-detail">
    <p className="decision-context">Stored estimates are not verified buying signals. Neutral defaults fill gaps when supported estimates are missing.</p>
    <h5>Reasons</h5><ul>{value.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
    <h5>Evidence and source</h5><Evidence items={value.evidence} />
    <h5>Risk flags</h5><p>{value.risk_flags.map(flag => labels[flag]).join(" · ") || "No risk flags in this decision."}</p>
    <h5>Missing signals</h5><p>{value.missing_signals.map(signal => labels[signal]).join(" · ") || "No missing signals in this decision."}</p>
  </div>;
}

/** @param {{value:import('../../types/revenueDecision').DecisionContent}} props */
function Metrics({ value }) {
  return <dl className="decision-metrics">
    <div><dt>Opportunity</dt><dd>{value.opportunity_score}<small>/100</small></dd></div>
    <div><dt>Fit</dt><dd>{value.fit_score}<small>/100</small></dd></div>
    <div><dt>Readiness</dt><dd>{value.readiness_score}<small>/100</small></dd></div>
    <div><dt>Coverage confidence</dt><dd>{percent(value.confidence)}</dd></div>
  </dl>;
}

/** @param {{change:import('../../types/revenueDecision').DecisionChange}} props */
function LatestChange({ change }) {
  const [symbol, label] = directions[change.overall_direction];
  /** @type {[string,string[]][]} */
  const collections = [["New risks", change.added_risk_flags], ["Removed risks", change.removed_risk_flags], ["Newly missing", change.added_missing_signals], ["Resolved missing", change.resolved_missing_signals]];
  return <section className="decision-card" aria-label="Changes since latest recording">
    <h4>Changes since latest recording</h4>
    <p className={`decision-direction direction-${change.overall_direction.toLowerCase()}`}><span aria-hidden="true">{symbol}</span> {label} <small>· {change.material_change ? "Material change" : "Below material thresholds"}</small></p>
    <dl className="decision-deltas">
      <div><dt>Opportunity change</dt><dd>{signed(change.opportunity_score_delta)} points</dd></div>
      <div><dt>Fit change</dt><dd>{signed(change.fit_score_delta)} points</dd></div>
      <div><dt>Readiness change</dt><dd>{signed(change.readiness_score_delta)} points</dd></div>
      <div><dt>Confidence change</dt><dd>{signed(Number((change.confidence_delta * 100).toFixed(4)))} percentage points</dd></div>
    </dl>
    {change.recommendation_changed && <p><strong>Recommendation:</strong> {actions[change.previous_recommendation]} → {actions[change.current_recommendation]}. This does not mean an action occurred.</p>}
    {change.human_review_changed && <p><strong>Review status:</strong> {review(change.previous_human_review_required)} → {review(change.current_human_review_required)}</p>}
    {collections.map(([title, values]) => values.length > 0 && <p key={title}><strong>{title}:</strong> {values.map(value => labels[value]).join(" · ")}</p>)}
    <ul>{change.explanations.map((text, index) => <li key={index}>{text}</li>)}</ul>
    {change.evidence_changed && <details><summary>Inspect evidence changes</summary><h5>Added evidence</h5><Evidence items={change.added_evidence} /><h5>Removed evidence</h5><Evidence items={change.removed_evidence} /></details>}
    {change.reasons_changed && <details><summary>Inspect explanation changes</summary><h5>Added reasons</h5><ul>{change.added_reasons.map(text => <li key={text}>{text}</li>)}</ul><h5>Removed reasons</h5><ul>{change.removed_reasons.map(text => <li key={text}>{text}</li>)}</ul></details>}
  </section>;
}

/** @param {{leadId:number|string,sourceRevision?:number,disabled?:boolean}} props */
export default function RevenueDecisionHistory({ leadId, sourceRevision = 0, disabled = false }) {
  const [data, setData] = useState(/** @type {import('../../types/revenueDecision').DecisionChangeResponse|null} */ (null));
  const [history, setHistory] = useState(/** @type {import('../../types/revenueDecision').HistoryPage|null} */ (null));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  const [recording, setRecording] = useState(false);
  const [message, setMessage] = useState("");
  const [recordError, setRecordError] = useState("");
  const [confirmationPending, setConfirmationPending] = useState(false);
  const [writeConfirmed, setWriteConfirmed] = useState(false);
  const [moreLoading, setMoreLoading] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const scope = useRef(0);
  const mounted = useRef(false);
  const recordInFlight = useRef(false);
  const pageInFlight = useRef(0);
  const nextOffset = useRef(0);
  const pendingRead = useRef(/** @type {{key:string,promise:Promise<import('../../types/revenueDecision').DecisionChangeResponse>}|null} */ (null));

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  useEffect(() => {
    const token = ++scope.current;
    let active = true;
    queueMicrotask(() => {
      if (active) { setLoading(true); setError(false); setMoreError(false); setMoreLoading(false); }
    });
    // Reuse the same in-flight read during development StrictMode replay.
    // Workspace and Lead changes remount this component; no cross-tenant cache.
    const key = `${leadId}:${sourceRevision}:${reload}`;
    if (pendingRead.current?.key !== key) pendingRead.current = { key, promise: getDecisionChange(leadId) };
    pendingRead.current.promise.then(result => {
      if (!active || scope.current !== token) return;
      setData(result); setHistory(result.history); nextOffset.current = result.history.items.length;
      setConfirmationPending(false); setRecordError(""); setWriteConfirmed(false);
    }).catch(() => { if (active && scope.current === token) setError(true); })
      .finally(() => { if (active && scope.current === token) setLoading(false); });
    return () => { active = false; };
  }, [leadId, sourceRevision, reload]);

  async function record() {
    if (recordInFlight.current || loading || moreLoading || disabled || error || confirmationPending) return;
    recordInFlight.current = true;
    setWriteConfirmed(false);
    setRecording(true); setRecordError(""); setMessage("");
    try {
      await recordCurrentDecision(leadId);
      if (!mounted.current) return;
      setWriteConfirmed(true); setMessage("Decision recorded.");
      setConfirmationPending(true); setLoading(true); setReload(value => value + 1);
    } catch {
      if (mounted.current) {
        setConfirmationPending(true);
        setRecordError("Recording was not confirmed. Refresh history to check the result before recording again.");
      }
    } finally {
      recordInFlight.current = false;
      if (mounted.current) setRecording(false);
    }
  }

  async function loadMore() {
    if (pageInFlight.current === scope.current || !history || loading || recording) return;
    const token = scope.current;
    pageInFlight.current = token;
    setMoreLoading(true); setMoreError(false);
    try {
      const page = await getDecisionHistory(leadId, { limit: history.limit, offset: nextOffset.current });
      if (!mounted.current || scope.current !== token) return;
      nextOffset.current = page.offset + page.items.length;
      setHistory(previous => ({ ...page, items: [...new Map([...(previous?.items || []), ...page.items].map(item => [item.id, item])).values()] }));
    } catch {
      if (mounted.current && scope.current === token) setMoreError(true);
    } finally {
      if (pageInFlight.current === token) pageInFlight.current = 0;
      if (mounted.current && scope.current === token) setMoreLoading(false);
    }
  }

  return <section className="revenue-brain" aria-label="Revenue Brain decision history" aria-busy={loading}>
    <header><span className="section-kicker">DECISION MEMORY</span><h3>Revenue Brain</h3><p>Current computation and immutable recorded history. No action runs from these recommendations.</p></header>
    <div className="decision-actions">
      <button type="button" className="lf-button lf-button-primary" disabled={recording || loading || !data || disabled || error || confirmationPending || moreLoading} onClick={record}>{recording ? "Recording decision…" : "Record current decision"}</button>
      <button type="button" className="lf-button lf-button-secondary" disabled={loading || recording || moreLoading} onClick={() => { setLoading(true); setReload(value => value + 1); }}>Refresh Revenue Brain</button>
    </div>
    <p className="decision-context">Opening or refreshing this panel never records a decision.</p>
    {message && <p role="status">{message}</p>}
    {recordError && <p role="alert">{recordError}</p>}
    {loading && <div className="decision-loading" role="status">{data ? "Refreshing Revenue Brain…" : "Loading Revenue Brain…"}</div>}
    {data && (loading || error) && <p role="status">Showing the last loaded computation and history. Refresh must complete before recording.</p>}
    {error && <div role="alert"><p>{writeConfirmed ? "The decision was recorded, but history could not refresh. Refresh to check the saved record." : "Revenue Brain could not be loaded. Try again."}</p><button type="button" className="lf-button lf-button-secondary" onClick={() => { setLoading(true); setReload(value => value + 1); }}>Retry Revenue Brain</button></div>}
    {data && <>
      <section className="decision-card" aria-label="Current computed decision">
        <h4>Current computed decision</h4><p className="decision-marker">Current · not a recorded snapshot</p>
        <Metrics value={data.current_decision} />
        <p><strong>Recommendation:</strong> {actions[data.current_decision.recommended_action]}</p>
        <p><strong>{review(data.current_decision.human_review_required)}</strong></p>
        <p className="decision-context">Confidence describes evidence coverage, not the chance of a sale.</p>
        <p>Decision generated: <time dateTime={data.current_decision.generated_at}>{timestamp(data.current_decision.generated_at)}</time></p>
        <p className="decision-context">Policy: {data.current_decision.decision_version}</p>
        <details><summary>Inspect current reasons and evidence</summary><DecisionDetails value={data.current_decision} /></details>
      </section>
      {data.change && <LatestChange change={data.change} />}
      <section className="decision-card" aria-label="Recorded decision history">
        <h4>Decision history</h4>
        {history?.items.length === 0 && <div className="decision-empty"><strong>No recorded decisions yet</strong><p>Your current Revenue Brain decision is available above. History begins when you explicitly choose Record current decision.</p></div>}
        <ol className="decision-records">{history?.items.map(item => <li key={item.id}>
          <h5>{item.id === data.latest_recorded_decision?.id ? "Latest recorded decision" : "Earlier recorded decision"}</h5>
          <p>Recorded: <time dateTime={item.recorded_at}>{timestamp(item.recorded_at)}</time></p>
          <p><strong>Opportunity {item.opportunity_score}/100</strong> · {actions[item.recommended_action]}</p>
          <p>Coverage confidence {percent(item.confidence)} · {review(item.human_review_required)}</p>
          <p className="decision-context">Policy: {item.decision_version}</p>
          <details><summary>Inspect recorded decision</summary><Metrics value={item} /><p>Decision generated: <time dateTime={item.decision_generated_at}>{timestamp(item.decision_generated_at)}</time></p><p>Decision recorded: <time dateTime={item.recorded_at}>{timestamp(item.recorded_at)}</time></p><DecisionDetails value={item} /></details>
        </li>)}</ol>
        {history && <p className="decision-context">Showing {history.items.length} of {history.total} recorded decisions.</p>}
        {moreError && <p role="alert">More history could not be loaded. Try Load more again.</p>}
        {history && (history.items.length < history.total || moreError) && <button type="button" className="lf-button lf-button-secondary" disabled={loading || recording || moreLoading} onClick={loadMore}>{moreLoading ? "Loading more decisions…" : "Load more decisions"}</button>}
      </section>
    </>}
  </section>;
}
