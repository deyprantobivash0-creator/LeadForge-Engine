import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, BrainCircuit, Clock3, Database, Sparkles } from "lucide-react";
import { getAnalysisHistory, getLead, getLeads, processLead } from "../services/leadService";
import { formatAnalysisDate, presentAnalysis } from "../utils/leadIntelligence";

const HISTORY_LIMIT = 8;
const processingErrors = {
  provider_not_configured: "Analysis is not configured for this workspace.",
  provider_timeout: "Analysis timed out. Try again later.",
  provider_unavailable: "The analysis provider is unavailable. Try again later.",
  malformed_provider_output: "The analysis response could not be used. Try again later.",
  validation_failure: "The analysis response could not be validated. Try again later.",
  processing_failure: "Analysis could not be completed. Try again later.",
};

function StateMessage({ title, children, retry, error = false }) {
  return <div className={`intelligence-state ${error ? "is-error" : ""}`} role={error ? "alert" : "status"}>
    <strong>{title}</strong><p>{children}</p>
    {retry && <button className="lf-button lf-button-secondary" type="button" onClick={retry}>Try again</button>}
  </div>;
}

function Badge({ children, tone = "neutral" }) {
  return <span className={`lf-badge lf-badge-${tone}`}>{children}</span>;
}

function Score({ analysis }) {
  return <section className="intelligence-card score-panel" aria-label="AI Score">
    <div className="section-kicker">AI SCORE</div>
    {analysis?.score !== null && analysis?.score !== undefined ? <>
      <div className="score-display"><strong>{analysis.score}</strong><span>/100</span></div>
      <div className="score-meter" role="meter" aria-label="AI Score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={analysis.score}>
        <span style={{ width: `${analysis.score}%` }} />
      </div>
      <div className="score-footer"><span>Backend analysis</span>{analysis.priority && <Badge tone={analysis.priority.toLowerCase()}>{analysis.priority} priority</Badge>}</div>
    </> : <StateMessage title="Not analyzed">Run an analysis to see a score and priority.</StateMessage>}
  </section>;
}

function Dimension({ dimension }) {
  return <article className="intelligence-card dimension-card">
    <div className="dimension-heading"><h3>{dimension.label}</h3><strong>{dimension.score === null ? "Unavailable" : `${dimension.score}/100`}</strong></div>
    <p>{dimension.summary || "No assessment available."}</p>
    {dimension.evidence.length > 0 && <span className="dimension-evidence-count">{dimension.evidence.length} evidence item{dimension.evidence.length === 1 ? "" : "s"}</span>}
  </article>;
}

function Evidence({ dimensions }) {
  const entries = dimensions.flatMap((dimension) => dimension.evidence.map((item, index) => ({ ...item, dimension: dimension.label, key: `${dimension.key}-${index}` })));
  return <section className="intelligence-card evidence-section">
    <div className="section-heading"><div><span className="section-kicker">PROVENANCE</span><h2>AI evidence</h2></div><Database size={20} aria-hidden="true" /></div>
    {entries.length === 0 ? <p className="intelligence-muted">No supporting evidence is available for this analysis.</p> : <div className="evidence-list">
      {entries.map((item) => <article className="evidence-item" key={item.key}>
        <div className="evidence-item-head"><span>{item.dimension}</span><Badge tone={item.source === "lead_data" ? "data" : "derived"}>{item.source === "lead_data" ? "Lead data" : "Derived inference"}</Badge></div>
        <p className="evidence-value"><strong>{item.field.replaceAll("_", " ")}:</strong> {item.value}</p>
        <p>{item.reasoning}</p>
      </article>)}
    </div>}
  </section>;
}

function History({ data, loading, error, onRetry, onMore, currentId }) {
  return <section className="intelligence-card history-section">
    <div className="section-heading"><div><span className="section-kicker">RECORD</span><h2>Analysis history</h2></div><Clock3 size={20} aria-hidden="true" /></div>
    {data?.items?.length > 0 && <ol className="history-list">{data.items.map((item) => <li key={item.id}>
      <div><strong>{formatAnalysisDate(item.created_at)}</strong><span>{item.id === currentId ? "Current analysis" : "Earlier analysis"}</span></div>
      <div className="history-result"><strong>{item.lead_score}/100</strong><Badge tone={item.priority?.toLowerCase()}>{item.priority}</Badge></div>
    </li>)}</ol>}
    {loading && <p role="status" className="intelligence-muted">Loading analysis history...</p>}
    {error && <StateMessage title="History unavailable" retry={onRetry} error>{error}</StateMessage>}
    {!loading && !error && data?.items?.length === 0 && <p className="intelligence-muted">No analyses have been saved for this lead.</p>}
    {!loading && !error && data && data.items.length < data.total && <button type="button" className="lf-button lf-button-secondary history-more" onClick={onMore}>Load more history</button>}
  </section>;
}

function LeadSelection() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    getLeads({ page: 1, page_size: 6 }).then((result) => { if (active) { setData(result); setError(""); } })
      .catch((failure) => { if (active) setError(failure.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);
  return <div className="intelligence-page">
    <header className="intelligence-page-header"><span className="section-kicker">LEADFORGE / INTELLIGENCE</span><h1>Lead Intelligence Center</h1><p>Explore the latest saved assessment for a lead in this workspace.</p></header>
    <section className="intelligence-card selection-card"><span className="selection-icon"><BrainCircuit size={28} aria-hidden="true" /></span><h2>Select a lead to view AI intelligence.</h2><p>Open a recent lead below or browse the Lead workspace.</p><Link className="lf-button lf-button-secondary" to="/leads">Browse all leads <ArrowRight size={16} aria-hidden="true" /></Link></section>
    <section className="intelligence-card selection-list"><div className="section-heading"><div><span className="section-kicker">THIS WORKSPACE</span><h2>Recent leads</h2></div></div>
      {loading && <p role="status" className="intelligence-muted">Loading leads...</p>}
      {!loading && error && <StateMessage title="Leads unavailable" retry={() => { setLoading(true); setRevision((value) => value + 1); }} error>{error}</StateMessage>}
      {!loading && !error && data?.items?.length === 0 && <p className="intelligence-muted">There are no leads in this workspace yet.</p>}
      {!loading && !error && data?.items?.length > 0 && <ul className="selection-leads">{data.items.map((lead) => <li key={lead.id}><Link to={`/ai/${lead.id}`}><span><strong>{lead.company}</strong><small>{lead.email}</small></span><ArrowRight size={18} aria-hidden="true" /></Link></li>)}</ul>}
    </section>
  </div>;
}

function SelectedLead({ leadId }) {
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [history, setHistory] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [historyRevision, setHistoryRevision] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState("");
  const [processMessage, setProcessMessage] = useState("");

  useEffect(() => {
    let active = true;
    getLead(leadId).then((result) => { if (active) { setLead(result); setError(""); } })
      .catch((failure) => { if (active) setError(failure.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [leadId, revision]);
  useEffect(() => {
    let active = true;
    getAnalysisHistory(leadId, { limit: HISTORY_LIMIT, offset }).then((result) => {
      if (!active) return;
      setHistory((previous) => ({ leadId, items: offset === 0 || previous?.leadId !== leadId ? result.items : [...previous.items, ...result.items], total: result.total }));
      setHistoryError("");
    }).catch((failure) => { if (active) setHistoryError(failure.message); })
      .finally(() => { if (active) setHistoryLoading(false); });
    return () => { active = false; };
  }, [leadId, offset, historyRevision]);

  async function analyze() {
    if (processing) return;
    setProcessing(true);
    setProcessError("");
    setProcessMessage("");
    try {
      await processLead(leadId);
      setProcessMessage("Lead intelligence updated.");
      setHistoryLoading(true);
      setOffset(0);
      setRevision((value) => value + 1);
      setHistoryRevision((value) => value + 1);
    } catch (failure) {
      setProcessError(processingErrors[failure.message] || failure.message);
      // A failed attempt may update processing_status, but the prior analysis stays visible.
      getLead(leadId).then(setLead).catch(() => {});
    } finally {
      setProcessing(false);
    }
  }

  const analysis = presentAnalysis(lead?.current_analysis);
  const dimensions = analysis?.dimensions || [];
  return <div className="intelligence-page">
    <Link className="intelligence-back" to="/ai"><ArrowLeft size={16} aria-hidden="true" /> All intelligence</Link>
    {loading && !lead && <StateMessage title="Loading lead">Retrieving lead details and current intelligence...</StateMessage>}
    {!loading && error && !lead && <StateMessage title="Lead unavailable" retry={() => { setLoading(true); setRevision((value) => value + 1); }} error>{error}</StateMessage>}
    {lead && <>
      <header className="intelligence-hero intelligence-card">
        <div className="intelligence-hero-main"><span className="section-kicker">LEAD INTELLIGENCE / {lead.id}</span><h1>{lead.company}</h1><p>{lead.email}{lead.source ? ` · ${lead.source}` : ""}</p>
          <div className="intelligence-badges"><Badge>{lead.status}</Badge><Badge tone={lead.processing_status}>{lead.processing_status}</Badge>{analysis?.priority && <Badge tone={analysis.priority.toLowerCase()}>{analysis.priority} priority</Badge>}</div>
          <span className="analysis-time">Last analyzed: {formatAnalysisDate(analysis?.createdAt)}</span>
        </div>
        <div className="intelligence-hero-actions"><button type="button" className="lf-button lf-button-primary" onClick={analyze} disabled={processing || lead.processing_status === "processing"}><Sparkles size={17} aria-hidden="true" />{processing ? "Analyzing..." : analysis ? "Re-analyze Lead" : "Analyze Lead"}</button>{lead.processing_status === "processing" && !processing && <small>Analysis is already in progress.</small>}</div>
      </header>
      {processing && <p className="intelligence-notice" role="status">Processing this lead. Results will refresh when the request completes.</p>}
      {processMessage && <p className="intelligence-notice success" role="status">{processMessage}</p>}
      {processError && <p className="intelligence-notice error" role="alert">Analysis failed: {processError}{analysis ? " Previous intelligence remains available." : ""}</p>}
      {error && <p className="intelligence-notice error" role="alert">Could not refresh lead details: {error}</p>}
      <div className="intelligence-overview"><Score analysis={analysis} /><section className="intelligence-card action-panel"><span className="section-kicker">NEXT BEST ACTION</span><h2>{analysis?.recommendedAction || "No action available"}</h2><p>{analysis ? "From the latest saved Lead Brain decision." : "Analyze this lead to see its saved recommendation."}</p></section></div>
      {analysis ? <>
        <section className="intelligence-section"><div className="section-heading"><div><span className="section-kicker">LEAD BRAIN</span><h2>Intelligence dimensions</h2></div></div><div className="dimension-grid">{dimensions.map((dimension) => <Dimension key={dimension.key} dimension={dimension} />)}</div></section>
        <section className="intelligence-card reasoning-section"><span className="section-kicker">WHY THIS LEAD MATTERS</span><h2>Assessment summary</h2><div className="reasoning-grid">{dimensions.map((dimension) => <div key={dimension.key}><strong>{dimension.label}</strong><p>{dimension.summary || "No summary available."}</p></div>)}</div></section>
        <Evidence dimensions={dimensions} />
      </> : <section className="intelligence-card"><StateMessage title="No saved intelligence">This lead has not been analyzed yet. Use Analyze Lead to create its first assessment.</StateMessage></section>}
      <History data={history} loading={historyLoading} error={historyError} currentId={analysis?.id} onRetry={() => { setHistoryLoading(true); setHistoryRevision((value) => value + 1); }} onMore={() => { setHistoryLoading(true); setOffset((value) => value + HISTORY_LIMIT); }} />
    </>}
  </div>;
}

export default function Intelligence() {
  const { leadId } = useParams();
  return leadId ? <SelectedLead key={leadId} leadId={leadId} /> : <LeadSelection />;
}
