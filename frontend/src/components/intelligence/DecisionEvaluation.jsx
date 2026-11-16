import { useEffect, useRef, useState } from "react";
import { getEvaluation, getEvaluationEvidence } from "../../services/decisionEvaluationService";
import LeadDetails from "../leads/LeadDetails";

export default function DecisionEvaluation() {
  const [data, setData] = useState(/** @type {import('../../services/decisionEvaluationService').Evaluation|null} */ (null));
  const [page, setPage] = useState(/** @type {import('../../services/decisionEvaluationService').EvidencePage|null} */ (null));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lead, setLead] = useState(/** @type {number|null} */ (null));
  const active = useRef(false);
  const inFlight = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  /** @param {'summary'|'evidence'} target @param {number} [offset] */
  async function load(target, offset = 0) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError("");
    try {
      if (target === "summary") {
        const result = await getEvaluation();
        if (active.current) { setData(result); setPage(null); }
      } else {
        const result = await getEvaluationEvidence(offset);
        if (active.current) setPage(result);
      }
    } catch { if (active.current) setError("Decision evaluation could not be loaded. Try again."); }
    finally { inFlight.current = false; if (active.current) setBusy(false); }
  }
  return <section className="intelligence-card" aria-label="Decision evaluation">
    <details onToggle={event => { if (event.currentTarget.open && !data) void load("summary"); }}>
      <summary>Inspect decision evaluation</summary>
      <h2>Decision outcome evidence</h2>
      <p>All-time recorded decisions in this workspace. Observed association is not causation or recommendation accuracy. No automatic learning occurs.</p>
      <p>Each decision counts once using its latest observed outcome, then recording time and UUID to break ties. Older conflicting reports remain in outcome history; corrections and retractions are not available.</p>
      {busy && <p role="status">Loading decision evaluation…</p>}
      {error && <p role="alert">{error}</p>}
      {data && (busy || error) && <p role="status">Showing the last loaded evaluation until refresh succeeds.</p>}
      <button type="button" disabled={busy} onClick={() => void load("summary")}>Refresh evaluation</button>
      {data && <>
        <p><strong>{data.evidence_context}</strong>. Counts describe this stored sample, not statistical significance.</p>
        {data.evaluated === 0 && <p>No outcome evidence has been recorded yet. Pending decisions are not failures.</p>}
        <p>Outcome evidence available for <strong>{data.evaluated} of {data.eligible}</strong> recorded decisions.</p>
        <p>Outcome pending: {data.pending}. Positive evidence: {data.positive}. Negative evidence: {data.negative}. Inconclusive: {data.inconclusive}.</p>
        <div style={{ overflowX: "auto" }}><table>
          <caption>Evidence by recorded recommendation; no category ranking</caption>
          <thead><tr><th>Recommendation</th><th>Evaluated / eligible</th><th>Pending</th><th>Positive</th><th>Negative</th><th>Inconclusive</th></tr></thead>
          <tbody>{data.categories.map(row => <tr key={row.recommendation}><th scope="row">{row.recommendation.replaceAll("_", " ")}</th><td>{row.evaluated} / {row.eligible}</td><td>{row.pending}</td><td>{row.positive}</td><td>{row.negative}</td><td>{row.inconclusive}</td></tr>)}</tbody>
        </table></div>
        <button type="button" disabled={busy} onClick={() => void load("evidence")}>Inspect underlying evidence</button>
      </>}
      {page && <div>
        <p>Underlying records are a separate live read; concurrent observations may change the summary. Refresh evaluation to recompute.</p>
        <ol>{page.items.map(row => <li key={row.decision_id}>
          <p>Decision {row.decision_id} · {row.recommendation.replaceAll("_", " ")} · recorded {row.decision_recorded_at}</p>
          <p>{row.outcome_id ? `Outcome ${row.outcome_id}: ${row.kind}; observed ${row.observed_at}; recorded ${row.outcome_recorded_at}` : "Outcome pending"}</p>
          <button type="button" onClick={() => setLead(row.lead_id)}>Inspect lead {row.lead_id} decisions and outcomes</button>
        </li>)}</ol>
        {page.items.length === 0 && <p>No underlying decisions on this page.</p>}
        {page.offset > 0 && <button type="button" disabled={busy} onClick={() => void load("evidence", Math.max(0, page.offset - page.limit))}>Previous evidence page</button>}
        {page.has_more && <button type="button" disabled={busy} onClick={() => void load("evidence", page.offset + page.limit)}>Next evidence page</button>}
      </div>}
    </details>
    {lead !== null && <LeadDetails leadId={lead} onClose={() => setLead(null)} />}
  </section>;
}
