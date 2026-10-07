import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BrainCircuit, CircleAlert, Layers3, Sparkles, Users } from "lucide-react";
import { getDashboardOverview } from "../services/dashboardService";
import { formatAnalysisDate } from "../utils/leadIntelligence";
import "../styles/dashboard-executive.css";

const priorityOrder = ["Hot", "Warm", "Cold", "Unanalyzed"];
const lifecycleOrder = ["New", "Qualified", "Contacted", "Meeting", "Won", "Lost"];
const processingOrder = ["pending", "processing", "completed", "failed"];

function Kpi({ label, value, detail, icon }) {
  return <article className="executive-kpi"><div className="executive-kpi-top"><span>{label}</span>{icon}</div><strong>{value}</strong><small>{detail}</small></article>;
}

function Distribution({ title, eyebrow, values, order, total, tone = "stage", description }) {
  return <section className="executive-panel"><div className="executive-panel-heading"><span className="section-kicker">{eyebrow}</span><h2>{title}</h2><p>{description}</p></div>
    <div className="executive-bars">{order.map((label) => <div className="executive-bar-row" key={label}>
      <div className="executive-bar-label"><span>{label}</span><strong>{values[label] ?? 0}</strong></div>
      <div className="executive-bar-track" role="img" aria-label={`${label}: ${values[label] ?? 0} of ${total} leads`}><span className={`executive-bar-fill executive-bar-${tone}-${label.toLowerCase()}`} style={{ width: total ? `${((values[label] ?? 0) / total) * 100}%` : "0%" }} /></div>
    </div>)}</div>
  </section>;
}

function TopOpportunities({ items }) {
  return <section className="executive-panel executive-top"><div className="executive-panel-heading"><span className="section-kicker">CURRENT LEADS</span><h2>Top opportunities</h2><p>Ranked by each Lead’s latest saved analysis.</p></div>
    {items.length ? <ol className="executive-list">{items.map((lead, index) => <li key={lead.lead_id}><span className="executive-rank">{String(index + 1).padStart(2, "0")}</span><div className="executive-list-main"><Link to={`/ai/${lead.lead_id}`}>{lead.company}<ArrowRight size={15} aria-hidden="true" /></Link><span>{lead.status} · {lead.processing_status}</span></div><div className="executive-list-score"><strong>{lead.lead_score}<small>/100</small></strong><span className={`lf-badge lf-badge-${lead.priority.toLowerCase()}`}>{lead.priority}</span></div></li>)}</ol> : <div className="executive-panel-empty"><p>No current Lead analyses yet.</p><Link to="/leads">Open Lead Workspace <ArrowRight size={15} aria-hidden="true" /></Link></div>}
  </section>;
}

function RecentActivity({ items }) {
  return <section className="executive-panel"><div className="executive-panel-heading"><span className="section-kicker">HISTORY</span><h2>Recent intelligence</h2><p>Saved analysis events. Re-analyzed Leads may appear more than once.</p></div>
    {items.length ? <ol className="executive-list executive-activity">{items.map((event) => <li key={event.analysis_id}><div className="executive-list-main">{event.lead_id ? <Link to={`/ai/${event.lead_id}`}>{event.company}<ArrowRight size={15} aria-hidden="true" /></Link> : <strong>{event.company}</strong>}<span>{formatDate(event.created_at)}{event.lead_id ? "" : " · Historical record"}</span></div><div className="executive-list-score"><strong>{event.lead_score}<small>/100</small></strong><span className={`lf-badge lf-badge-${event.priority.toLowerCase()}`}>{event.priority}</span></div></li>)}</ol> : <p className="executive-panel-empty">No analysis activity has been recorded yet.</p>}
  </section>;
}

function ProcessingHealth({ values, total }) {
  return <section className="executive-panel executive-health"><div className="executive-panel-heading"><span className="section-kicker">OPERATIONS</span><h2>Processing health</h2><p>Current processing state of Leads in this workspace.</p></div>
    <div className="executive-health-grid">{processingOrder.map((status) => <div key={status}><span className={`lf-badge lf-badge-${status}`}>{status[0].toUpperCase() + status.slice(1)}</span><strong>{values[status]}</strong></div>)}</div>
    {values.failed > 0 ? <p className="executive-health-note" role="status"><CircleAlert size={16} aria-hidden="true" /> {values.failed} of {total} Leads have a failed processing status. <Link to="/leads">Review Leads</Link></p> : <p className="executive-health-footnote">No Leads currently have a failed processing status.</p>}
  </section>;
}

function LoadingDashboard() {
  return <div className="executive-dashboard" role="status" aria-live="polite"><header className="executive-header"><span className="section-kicker">LEADFORGE / DASHBOARD</span><h1>Revenue Intelligence Dashboard</h1><p>Loading current workspace intelligence...</p></header><div className="executive-kpis executive-loading"><div /><div /><div /><div /></div><div className="executive-grid executive-loading"><div /><div /></div></div>;
}

function formatDate(value) {
  return formatAnalysisDate(value);
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    getDashboardOverview().then((result) => { if (active) { setData(result); setError(false); } })
      .catch(() => { if (active) setError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);

  if (loading) return <LoadingDashboard />;
  if (error) return <div className="executive-dashboard"><header className="executive-header"><span className="section-kicker">LEADFORGE / DASHBOARD</span><h1>Revenue Intelligence Dashboard</h1></header><div className="executive-panel executive-error" role="alert"><strong>Dashboard unavailable</strong><p>Current workspace intelligence could not be loaded. Try again.</p><button type="button" className="lf-button lf-button-secondary" onClick={() => { setLoading(true); setRevision((value) => value + 1); }}>Retry</button></div></div>;

  const { pipeline, priority_distribution: priorities, lifecycle_distribution: lifecycle, processing_distribution: processing } = data;
  return <div className="executive-dashboard">
    <header className="executive-header"><div><span className="section-kicker">LEADFORGE / DASHBOARD</span><h1>Revenue Intelligence Dashboard</h1><p>Current Lead intelligence and operational health in this workspace.</p></div><Link className="lf-button lf-button-secondary" to="/leads">Open Lead Workspace <ArrowRight size={16} aria-hidden="true" /></Link></header>
    {pipeline.total_leads === 0 ? <section className="executive-panel executive-onboarding"><span className="executive-onboarding-icon"><Users size={27} aria-hidden="true" /></span><h2>No leads in this workspace yet.</h2><p>Add a Lead in the Lead Workspace to begin building your current intelligence snapshot.</p><Link className="lf-button lf-button-primary" to="/leads">Go to Leads <ArrowRight size={16} aria-hidden="true" /></Link></section> : <>
      <div className="executive-kpis"><Kpi label="Total Leads" value={pipeline.total_leads} detail="Current workspace records" icon={<Users size={20} aria-hidden="true" />} /><Kpi label="Analyzed Leads" value={pipeline.analyzed_leads} detail={`${pipeline.unanalyzed_leads} awaiting analysis`} icon={<BrainCircuit size={20} aria-hidden="true" />} /><Kpi label="Hot Leads" value={priorities.Hot} detail="Current AI priority" icon={<Sparkles size={20} aria-hidden="true" />} /><Kpi label="Average AI Score" value={pipeline.average_current_score === null ? "—" : pipeline.average_current_score.toFixed(1)} detail="Current analyzed Leads only" icon={<Layers3 size={20} aria-hidden="true" />} /></div>
      {pipeline.analyzed_leads === 0 && <div className="executive-unanalysed"><BrainCircuit size={20} aria-hidden="true" /><p>These Leads have no saved intelligence yet. <Link to="/leads">Open Lead Workspace</Link> to analyze one.</p></div>}
      <div className="executive-grid"><Distribution title="Priority distribution" eyebrow="CURRENT INTELLIGENCE" values={priorities} order={priorityOrder} total={pipeline.total_leads} tone="priority" description="Each Lead appears once at its current priority." /><Distribution title="Lifecycle overview" eyebrow="CURRENT PIPELINE" values={lifecycle} order={lifecycleOrder} total={pipeline.total_leads} description="Operational stages across all Leads." /></div>
      <TopOpportunities items={data.top_opportunities} />
      <div className="executive-grid executive-bottom"><RecentActivity items={data.recent_analysis_activity} /><ProcessingHealth values={processing} total={pipeline.total_leads} /></div>
    </>}
  </div>;
}
