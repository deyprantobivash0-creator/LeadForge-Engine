import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { exportReport, getReportOverview } from "../services/reportService";
import "../styles/reports-workspace.css";
import { validReportRange } from "../utils/validation";

const periods = [["today", "Today"], ["7d", "7 days"], ["30d", "30 days"], ["custom", "Custom"]];
const priorities = ["Hot", "Warm", "Cold", "Other"];
const utc = (value) => new Date(`${value}Z`).toLocaleString(undefined, { timeZone: "UTC", dateStyle: "medium", timeStyle: "short" });

function Events({ items, ranked = false }) {
  const List = ranked ? "ol" : "ul";
  return <List className="reports-list">{items.map((item) => <li key={item.analysis_id}>
    <div>{item.lead_id ? <Link to={`/ai/${item.lead_id}`}>{item.company || "Unnamed Lead"}</Link> : <strong>{item.company || "Historical analysis"}</strong>}
      <small>{utc(item.created_at)} UTC{item.lead_id ? "" : " · Unlinked historical event"}</small></div>
    <div className="reports-result"><strong>{item.score}<small>/100</small></strong><span className={`lf-badge lf-badge-${priorities.includes(item.priority) ? item.priority.toLowerCase() : "data"}`}>{item.priority}</span></div>
  </li>)}</List>;
}

export default function Reports() {
  const { organization } = useAuth();
  const [preset, setPreset] = useState("30d");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [revision, setRevision] = useState(0);
  const invalid = preset === "custom" && !validReportRange(start, end);
  const params = preset === "custom" ? { preset, start, end } : { preset };

  useEffect(() => {
    if (invalid) return;
    let active = true;
    const requestParams = preset === "custom" ? { preset, start, end } : { preset };
    getReportOverview(requestParams).then((result) => { if (active) setData(result); })
      .catch((failure) => { if (active) setError(failure.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [organization?.id, preset, start, end, revision, invalid]);

  async function download() {
    setExporting(true); setExportError("");
    try {
      const blob = await exportReport(params);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `leadforge-report-${data.period.start.slice(0, 10)}-to-${new Date(new Date(`${data.period.end}Z`).getTime() - 1).toISOString().slice(0, 10)}.csv`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (failure) { setExportError(failure.message); }
    finally { setExporting(false); }
  }

  const s = data?.summary;
  const peak = Math.max(1, ...(data?.activity.map((point) => point.analysis_events) || []));
  return <div className="reports-page">
    <header className="reports-header"><div><span className="section-kicker">LEADFORGE / REPORTS</span><h1>Intelligence Reports</h1><p>Review historical Lead intelligence activity and qualification results.</p></div>
      <button className="lf-button lf-button-primary" type="button" onClick={download} disabled={!data || loading || invalid || exporting}>{exporting ? "Preparing CSV…" : "Export CSV"}</button></header>
    <section className="reports-controls" aria-label="Report period"><div className="reports-presets">{periods.map(([value, label]) => <button type="button" key={value} className={preset === value ? "active" : ""} aria-pressed={preset === value} onClick={() => { setData(null); setLoading(true); setError(""); setPreset(value); setRevision((current) => current + 1); }}>{label}</button>)}</div>
      {preset === "custom" && <div className="reports-dates"><label>Start date<input type="date" value={start} onChange={(event) => { setData(null); setLoading(true); setError(""); setStart(event.target.value); }} /></label><label>End date<input type="date" value={end} onChange={(event) => { setData(null); setLoading(true); setError(""); setEnd(event.target.value); }} /></label></div>}
      <p>All report times are UTC. Custom end date is inclusive.</p>{invalid && <p className="reports-validation" role="status">Choose both dates in order, within 365 days.</p>}</section>
    {exportError && <p className="reports-validation" role="alert">Export failed: {exportError}</p>}
    {!invalid && loading && <div className="reports-loading" role="status" aria-live="polite"><span>Loading historical report…</span><div className="reports-kpis">{[1, 2, 3, 4].map((key) => <div key={key} />)}</div><div className="reports-skeleton" /></div>}
    {!invalid && !loading && error && <section className="reports-panel" role="alert"><h2>Report unavailable</h2><p>{error}</p><button type="button" className="lf-button lf-button-secondary" onClick={() => { setLoading(true); setError(""); setRevision((value) => value + 1); }}>Retry</button></section>}
    {!invalid && !loading && data && <><p className="reports-window">{utc(data.period.start)} – {utc(data.period.end)} UTC · Historical analysis events</p>
      {s.analysis_events === 0 ? <section className="reports-panel reports-empty"><h2>No intelligence activity in this period.</h2><p>Try a longer period or analyze a Lead in this workspace.</p><div><Link className="lf-button lf-button-primary" to="/leads">Open Lead Workspace</Link><Link className="lf-button lf-button-secondary" to="/ai">Open AI Intelligence</Link></div></section> : <>
        <div className="reports-kpis"><article><span>Analysis Events</span><strong>{s.analysis_events}</strong><small>Saved assessments in period</small></article><article><span>Unique Analyzed Leads</span><strong>{s.unique_analyzed_leads}</strong><small>Distinct linked Leads</small></article><article><span>Average Analysis Score</span><strong>{s.average_analysis_score === null ? "—" : s.average_analysis_score.toFixed(1)}</strong><small>Across analysis events</small></article><article><span>Hot Assessments</span><strong>{s.hot_events}</strong><small>Historical Hot events</small></article></div>
        <div className="reports-grid"><section className="reports-panel"><span className="section-kicker">ANALYSIS ACTIVITY</span><h2>Activity trend</h2><p>Saved assessments over the selected period.</p><div className="reports-chart" role="img" aria-label={`${s.analysis_events} analysis events across ${data.activity.length} UTC time buckets`}>{data.activity.map((point) => <div key={point.bucket} className="reports-chart-column" title={`${utc(point.bucket)} UTC: ${point.analysis_events} events`}><span style={{ height: `${Math.max(2, point.analysis_events / peak * 100)}%` }} /></div>)}</div><div className="reports-chart-axis"><span>{utc(data.activity[0]?.bucket)}</span><span>{utc(data.activity.at(-1)?.bucket)}</span></div></section>
          <section className="reports-panel"><span className="section-kicker">HISTORICAL ASSESSMENTS</span><h2>Priority distribution</h2><p>Event counts, including repeated analyses of a Lead.</p><div className="reports-priorities">{priorities.map((priority) => <div key={priority}><div><span>{priority}</span><strong>{data.priority_distribution[priority]} <small>({Math.round(data.priority_distribution[priority] / s.analysis_events * 100)}%)</small></strong></div><div className="reports-track"><span className={`reports-fill reports-${priority.toLowerCase()}`} style={{ width: `${data.priority_distribution[priority] / s.analysis_events * 100}%` }} /></div></div>)}</div></section></div>
        <div className="reports-grid"><section className="reports-panel"><span className="section-kicker">LINKED LEADS</span><h2>Top opportunities</h2><p>Highest scored analysis per Lead in this period.</p>{data.top_opportunities.length ? <Events items={data.top_opportunities} ranked /> : <p>No linked Leads in this period.</p>}</section><section className="reports-panel"><span className="section-kicker">EVENT HISTORY</span><h2>Recent intelligence activity</h2><p>Newest saved assessments; a Lead may appear more than once.</p><Events items={data.recent_analysis_events} /></section></div>
      </>}</>}
  </div>;
}
