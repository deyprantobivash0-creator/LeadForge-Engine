import { useEffect, useRef, useState } from "react";
import { getOutcomes, recordOutcome } from "../../services/decisionOutcomeService";

/** @param {string} value */
const timestamp = value => new Date(value).toLocaleString("en-GB", { timeZone: "UTC" }) + " UTC";
/** @type {import('../../services/decisionOutcomeService').OutcomeKind[]} */
const kinds = ["Contacted", "Qualified", "Meeting", "Won", "Lost"];

/** @param {{leadId:number|string,decision:import('../../types/revenueDecision').LedgerRecord,disabled:boolean}} props */
export default function DecisionOutcomes({ leadId, decision, disabled }) {
  const [opened, setOpened] = useState(false);
  const [data, setData] = useState(/** @type {import('../../services/decisionOutcomeService').OutcomeHistory|null} */ (null));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [kind, setKind] = useState(/** @type {import('../../services/decisionOutcomeService').OutcomeKind} */ ("Contacted"));
  const [observed, setObserved] = useState("");
  const [note, setNote] = useState("");
  const inFlight = useRef(false);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  /** @param {boolean} [more] */
  async function load(more = false) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError("");
    try {
      const result = await getOutcomes(leadId, decision.id, more ? (data?.items.length || 0) : 0);
      if (mounted.current) {
        setData(previous => ({ ...result, items: more ? [...(previous?.items || []), ...result.items] : result.items }));
        setPending(false);
      }
    } catch { if (mounted.current) setError("Outcome history could not be loaded. Refresh to try again."); }
    finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }

  /** @param {import('react').FormEvent<HTMLFormElement>} event */
  async function submit(event) {
    event.preventDefault();
    if (inFlight.current || pending || disabled) return;
    const date = new Date(observed);
    if (!Number.isFinite(date.getTime()) || date < new Date(decision.recorded_at) || date > new Date() || note.length > 1000 || note.includes("\0")) {
      setError("Choose an observation time after this decision and no later than now, with a note of at most 1,000 characters."); return;
    }
    inFlight.current = true; setBusy(true); setError(""); setMessage(""); setPending(true);
    let confirmed = false;
    try {
      await recordOutcome(leadId, decision.id, { kind, observed_at: date.toISOString(), note: note || null });
      confirmed = true;
      if (mounted.current) { setMessage("Outcome recorded. Refresh history to inspect the saved evidence."); setNote(""); }
    } catch { if (mounted.current) setError("Recording was not confirmed. Refresh history before recording another outcome."); }
    finally { inFlight.current = false; if (mounted.current) setBusy(false); }
    if (mounted.current && confirmed) await load();
  }

  return <details onToggle={event => {
    if (event.currentTarget.open && !opened) { setOpened(true); void load(); }
  }}>
    <summary>Outcome evidence for this decision</summary>
    <section className="decision-outcomes" aria-label="Decision outcome evidence" aria-busy={busy}>
      <p>Later, manually reported observations. These do not change the recorded decision or Lead status.</p>
      <p>Outcome evidence does not establish causation, recommendation accuracy or automatic AI learning.</p>
      <p><strong>{data?.effectiveness || "Outcome not yet loaded"}</strong> · based on the latest observation, not the latest entry time.</p>
      {busy && <p role="status">Loading or recording outcome evidence…</p>}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <button type="button" disabled={busy} onClick={() => void load()}>Refresh outcomes</button>
      {data && data.total === 0 && <p>No outcomes recorded for this decision.</p>}
      {data && data.total > 0 && <p>Newest observations first. Observation and recording times are separate.</p>}
      <ol>{data?.items.map(item => <li key={item.id}>
        <strong>{item.kind}</strong>
        <p>Observed: <time dateTime={item.observed_at}>{timestamp(item.observed_at)}</time></p>
        <p>Recorded: <time dateTime={item.recorded_at}>{timestamp(item.recorded_at)}</time> · User {item.recorded_by_user_id} · Manual report</p>
        {item.note && <p style={{ overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{item.note}</p>}
      </li>)}</ol>
      {data && data.items.length < data.total && <button type="button" disabled={busy} onClick={() => void load(true)}>Load more outcomes</button>}
      <form onSubmit={submit}>
        <label>Observed outcome<select value={kind} onChange={event => {
          const selected = kinds.find(value => value === event.target.value);
          if (selected) setKind(selected);
        }}>{kinds.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Observed at (your local time)<input type="datetime-local" step="1" required value={observed} onChange={event => setObserved(event.target.value)} /></label>
        <label>Outcome evidence note (optional)<textarea maxLength={1000} value={note} onChange={event => setNote(event.target.value)} /></label>
        <p>Entries are permanent and append-only. Check the decision, observation and note before confirming. Report only what you observed.</p>
        <button type="submit" disabled={busy || pending || disabled || !data}>Confirm outcome</button>
      </form>
    </section>
  </details>;
}
