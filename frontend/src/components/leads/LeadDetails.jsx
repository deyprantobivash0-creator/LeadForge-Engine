import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getLead, processLead, updateLeadLifecycle } from "../../services/leadService";

const statuses = ["New", "Qualified", "Contacted", "Meeting", "Won", "Lost"];
const dateInput = (value) => value ? value.slice(0, 10) : "";
const dateValue = (value) => value ? `${value}T00:00:00` : null;

export default function LeadDetails({ leadId, onClose, onSaved }) {
  const panelRef = useRef(null);
  const closeRef = useRef(null);
  const mutationRef = useRef(false);
  const [lead, setLead] = useState(null);
  const [intelligence, setIntelligence] = useState(null);
  const [status, setStatus] = useState("New");
  const [notes, setNotes] = useState("");
  const [lastContacted, setLastContacted] = useState("");
  const [nextFollowUp, setNextFollowUp] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [mutationError, setMutationError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const previousFocus = document.activeElement;
    closeRef.current?.focus();
    function handleKey(event) {
      if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
      if (event.key !== "Tab") return;
      const controls = [...panelRef.current.querySelectorAll("a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)")];
      if (!controls.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", handleKey);
    return () => { document.removeEventListener("keydown", handleKey); previousFocus?.focus?.(); };
  }, [onClose]);

  useEffect(() => {
    let active = true;
    getLead(leadId).then((detail) => {
      if (!active) return;
      setLead(detail);
      setIntelligence(detail.current_analysis);
      setStatus(detail.status);
      setNotes(detail.notes || "");
      setLastContacted(dateInput(detail.last_contacted));
      setNextFollowUp(dateInput(detail.next_follow_up));
      setError("");
    }).catch((failure) => { if (active) setError(failure.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [leadId, revision]);

  async function save(event) {
    event.preventDefault();
    if (mutationRef.current) return;
    mutationRef.current = true; setMutationError("");
    setSaving(true);
    setMessage("");
    try {
      await updateLeadLifecycle(leadId, {
        status, notes, last_contacted: dateValue(lastContacted), next_follow_up: dateValue(nextFollowUp),
      });
      setMessage("Lead lifecycle updated.");
      setRevision((value) => value + 1);
      onSaved?.();
    } catch (failure) {
      setMutationError(failure.message);
    } finally {
      mutationRef.current = false;
      setSaving(false);
    }
  }

  async function runProcessing() {
    if (mutationRef.current) return;
    mutationRef.current = true; setMutationError("");
    setProcessing(true);
    setMessage("");
    try {
      await processLead(leadId);
      setMessage("Lead intelligence updated.");
      setRevision((value) => value + 1);
      onSaved?.();
    } catch (failure) {
      setMutationError(failure.message);
    } finally {
      mutationRef.current = false;
      setProcessing(false);
    }
  }

  return <div className="lead-details-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="lead-details-panel" role="dialog" aria-modal="true" aria-labelledby="lead-details-title" ref={panelRef} onMouseDown={(event) => event.stopPropagation()}>
      <div className="details-header"><div><span className="section-kicker">LEAD DETAILS</span><h2 id="lead-details-title">{lead?.company || "Lead details"}</h2></div><button ref={closeRef} type="button" onClick={onClose} aria-label="Close lead details">×</button></div>
      {loading && <p role="status">Loading lead...</p>}
      {!loading && error && <div role="alert"><p>{error}</p><button onClick={() => { setLoading(true); setRevision((value) => value + 1); }}>Retry</button></div>}
      {!loading && !error && lead && <div className="details-content">
        <p>{lead.email} · {lead.source}</p>
        <p>Lifecycle: {lead.status} · Processing: {lead.processing_status}</p>
        <div className="intelligence-box"><h3>Lead intelligence</h3>
          {intelligence ? <><p>Priority: {intelligence.priority} · AI Score: {intelligence.lead_score}/100</p>{intelligence.result?.company?.summary && <p>{intelligence.result.company.summary}</p>}</> : <p>Not analyzed yet.</p>}
          <button type="button" onClick={runProcessing} disabled={saving || processing || lead.processing_status === "processing"}>
            {processing ? "Processing..." : intelligence ? "Re-analyze Lead" : "Process Lead"}
          </button>
          {lead.processing_status === "processing" && !processing && <p>Processing is in progress. <button type="button" onClick={() => setRevision((value) => value + 1)}>Refresh status</button></p>}
          <Link className="lead-intelligence-link" to={`/ai/${leadId}`}>View full intelligence →</Link>
        </div>
        <form className="lifecycle-editor" onSubmit={save}>
          <h3>Lifecycle</h3>
          <label htmlFor="lead-status">Status</label>
          <select id="lead-status" value={status} onChange={(event) => setStatus(event.target.value)}>{statuses.map((item) => <option key={item}>{item}</option>)}</select>
          <label htmlFor="lead-notes">Notes</label>
          <textarea id="lead-notes" maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} />
          <label htmlFor="last-contacted">Last contacted</label>
          <input id="last-contacted" type="date" value={lastContacted} onChange={(event) => setLastContacted(event.target.value)} />
          <label htmlFor="next-follow-up">Next follow-up</label>
          <input id="next-follow-up" type="date" value={nextFollowUp} onChange={(event) => setNextFollowUp(event.target.value)} />
          <button className="save-lifecycle-button" type="submit" disabled={saving || processing}>{saving ? "Saving..." : "Save changes"}</button>
          {mutationError && <p role="alert">{mutationError}</p>}
          {message && <p role="status">{message}</p>}
        </form>
      </div>}
    </aside>
  </div>;
}
