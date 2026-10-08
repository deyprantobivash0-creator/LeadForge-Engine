import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Plus, Search, X } from "lucide-react";
import AddLeadDialog from "../components/leads/AddLeadDialog";
import LeadDetails from "../components/leads/LeadDetails";
import { getLeads, searchLeads } from "../services/leadService";
import "../styles/leads-workspace.css";

const PAGE_SIZE = 20;
const initialFilters = { status: "", priority: "", processing_status: "", analysis_state: "" };
const lifecycleOptions = ["New", "Qualified", "Contacted", "Meeting", "Won", "Lost"];
const priorityOptions = ["Hot", "Warm", "Cold"];
const processingOptions = ["pending", "processing", "completed", "failed"];

function Badge({ value, kind }) {
  if (!value) return <span className="lead-workspace-muted">—</span>;
  const label = kind === "processing" ? value[0].toUpperCase() + value.slice(1) : value;
  return <span className={`lead-workspace-badge lead-workspace-badge-${kind}-${value.toLowerCase()}`}>{kind === "processing" && value === "processing" && <span className="lead-processing-dot" aria-hidden="true" />}{label}</span>;
}

function Score({ analysis }) {
  if (!analysis) return <span className="lead-workspace-muted">Not analyzed</span>;
  return <span className="lead-workspace-score"><strong>{analysis.lead_score}</strong><span>/100</span></span>;
}

function LeadActions({ lead, onOpen }) {
  return <div className="lead-workspace-actions"><button type="button" onClick={() => onOpen(lead.id)} aria-label={`Open ${lead.company} details`}>Open Lead</button><Link to={`/ai/${lead.id}`} aria-label={`View intelligence for ${lead.company}`}>Intelligence <ArrowRight size={14} aria-hidden="true" /></Link></div>;
}

function LeadTable({ leads, onOpen }) {
  return <div className="lead-workspace-desktop"><table className="lead-workspace-table"><thead><tr><th scope="col">Company</th><th scope="col">Contact</th><th scope="col">Lifecycle</th><th scope="col">AI score</th><th scope="col">Priority</th><th scope="col">Processing</th><th scope="col">Source</th><th scope="col">Actions</th></tr></thead><tbody>
    {leads.map((lead) => <tr key={lead.id}>
      <td className="lead-company-cell"><button type="button" onClick={() => onOpen(lead.id)} title={lead.company}>{lead.company}</button></td>
      <td className="lead-email-cell"><a href={`mailto:${lead.email}`} title={lead.email}>{lead.email}</a></td>
      <td><Badge kind="lifecycle" value={lead.status} /></td>
      <td><Score analysis={lead.current_analysis} /></td>
      <td>{lead.current_analysis ? <Badge kind="priority" value={lead.current_analysis.priority} /> : <span className="lead-workspace-muted">Unanalyzed</span>}</td>
      <td><Badge kind="processing" value={lead.processing_status} /></td>
      <td className="lead-source-cell"><span title={lead.source}>{lead.source}</span></td>
      <td><LeadActions lead={lead} onOpen={onOpen} /></td>
    </tr>)}
  </tbody></table></div>;
}

function LeadCards({ leads, onOpen }) {
  return <div className="lead-workspace-mobile">{leads.map((lead) => <article className="lead-mobile-card" key={lead.id}>
    <div className="lead-mobile-identity"><button type="button" onClick={() => onOpen(lead.id)}>{lead.company}</button><a href={`mailto:${lead.email}`}>{lead.email}</a></div>
    <div className="lead-mobile-meta"><Badge kind="lifecycle" value={lead.status} /><Badge kind="processing" value={lead.processing_status} /></div>
    <div className="lead-mobile-intelligence"><Score analysis={lead.current_analysis} />{lead.current_analysis ? <Badge kind="priority" value={lead.current_analysis.priority} /> : null}</div>
    <div className="lead-mobile-source">Source: <span title={lead.source}>{lead.source}</span></div>
    <LeadActions lead={lead} onOpen={onOpen} />
  </article>)}</div>;
}

function LoadingRows() {
  return <div className="lead-workspace-loading" role="status" aria-live="polite"><span>Loading leads...</span><div /><div /><div /><div /></div>;
}

export default function Leads() {
  const [searchField, setSearchField] = useState("company");
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [sourceInput, setSourceInput] = useState("");
  const [sourceTerm, setSourceTerm] = useState("");
  const [filters, setFilters] = useState(initialFilters);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [response, setResponse] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [notice, setNotice] = useState("");
  const closeAdd = useCallback(() => setShowAdd(false), []);
  const closeDetails = useCallback(() => setSelectedId(null), []);

  useEffect(() => {
    const timer = setTimeout(() => setSearchTerm(searchInput.trim()), 350);
    return () => clearTimeout(timer);
  }, [searchInput]);
  useEffect(() => {
    const timer = setTimeout(() => setSourceTerm(sourceInput.trim()), 350);
    return () => clearTimeout(timer);
  }, [sourceInput]);

  const queryKey = JSON.stringify({ page, page_size: PAGE_SIZE, ...filters, source: sourceTerm, searchField, searchTerm });
  useEffect(() => {
    let active = true;
    const { searchField: field, searchTerm: term, ...params } = JSON.parse(queryKey);
    const request = term ? searchLeads({ ...params, [field]: term }) : getLeads(params);
    request.then((data) => { if (active) setResponse({ key: queryKey, data, error: "" }); })
      .catch((failure) => { if (active) setResponse((previous) => ({ key: queryKey, data: previous?.key === queryKey ? previous.data : null, error: failure.message })); })
      .finally(() => { if (active) setRefreshing(false); });
    return () => { active = false; };
  }, [queryKey, revision]);

  function updateFilter(name, value) {
    setFilters((previous) => ({ ...previous, [name]: value }));
    setPage(1);
  }
  function resetFilters() {
    setFilters(initialFilters);
    setSourceInput("");
    setSourceTerm("");
    setSearchInput("");
    setSearchTerm("");
    setPage(1);
  }
  function refresh() { setRefreshing(true); setRevision((value) => value + 1); }
  function leadCreated() {
    setShowAdd(false);
    resetFilters();
    setNotice("Lead added to this workspace.");
    refresh();
  }

  const current = response?.key === queryKey ? response : null;
  const data = current?.data;
  const error = current?.error;
  const initialLoading = !current;
  const activeFilters = Boolean(searchTerm || sourceTerm || Object.values(filters).some(Boolean));
  const firstResult = data?.total ? (data.page - 1) * data.page_size + 1 : 0;
  const lastResult = data?.total ? Math.min(data.page * data.page_size, data.total) : 0;

  return <div className="lead-workspace">
    <header className="lead-workspace-header"><div><span className="section-kicker">WORKSPACE / LEADS</span><h1>Lead Workspace</h1><p>Manage, qualify, and prioritize leads in the selected workspace.</p></div><button type="button" className="lf-button lf-button-primary" onClick={() => setShowAdd(true)}><Plus size={17} aria-hidden="true" /> Add Lead</button></header>
    {notice && <p className="lead-workspace-notice" role="status">{notice}</p>}
    <section className="lead-workspace-toolbar" aria-label="Search and filter leads">
      <form className="lead-workspace-search" role="search" onSubmit={(event) => { event.preventDefault(); setSearchTerm(searchInput.trim()); setPage(1); }}><label htmlFor="lead-search-input">Search leads</label><div className="lead-search-control"><Search size={18} aria-hidden="true" /><input id="lead-search-input" maxLength={searchField === "email" ? 254 : 200} value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} placeholder={searchField === "company" ? "Search company" : "Search email"} />{searchInput && <button type="button" aria-label="Clear search" onClick={() => { setSearchInput(""); setSearchTerm(""); setPage(1); }}><X size={16} aria-hidden="true" /></button>}</div></form>
      <label className="lead-workspace-filter lead-search-field">Search field<select value={searchField} onChange={(event) => { setSearchField(event.target.value); setPage(1); }}><option value="company">Company</option><option value="email">Email</option></select></label>
      <label className="lead-workspace-filter">Lifecycle<select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}><option value="">All stages</option>{lifecycleOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label className="lead-workspace-filter">Priority<select value={filters.priority} onChange={(event) => updateFilter("priority", event.target.value)}><option value="">All priorities</option>{priorityOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label className="lead-workspace-filter">Processing<select value={filters.processing_status} onChange={(event) => updateFilter("processing_status", event.target.value)}><option value="">All states</option>{processingOptions.map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select></label>
      <label className="lead-workspace-filter">Analysis<select value={filters.analysis_state} onChange={(event) => updateFilter("analysis_state", event.target.value)}><option value="">All leads</option><option value="analyzed">Analyzed</option><option value="unanalyzed">Unanalyzed</option></select></label>
      <label className="lead-workspace-filter lead-source-filter">Source contains<input value={sourceInput} onChange={(event) => { setSourceInput(event.target.value); setPage(1); }} maxLength={100} placeholder="Any source" /></label>
      {activeFilters && <button type="button" className="lead-reset-button" onClick={resetFilters}>Reset filters</button>}
    </section>
    <section className="lead-workspace-results" aria-label="Lead results">
      <div className="lead-results-heading"><div><span className="section-kicker">LEAD DIRECTORY</span><h2>{data ? `${data.total} ${activeFilters ? "matching" : "total"} lead${data.total === 1 ? "" : "s"}` : "Leads"}</h2><p>{activeFilters ? "Results reflect the selected search and filters." : "Newest leads first."}</p></div>{refreshing && data && <span role="status" className="lead-refresh-label">Refreshing...</span>}</div>
      {initialLoading && <LoadingRows />}
      {error && <div className="lead-workspace-error" role="alert"><strong>Could not load leads.</strong><p>{error}</p><button type="button" className="lf-button lf-button-secondary" onClick={refresh}>Try again</button></div>}
      {data?.items?.length === 0 && !error && <div className="lead-workspace-empty"><strong>{activeFilters ? "No leads match these criteria." : "No leads in this workspace yet."}</strong><p>{activeFilters ? "Try another search or reset your filters." : "Add your first lead to begin managing this workspace."}</p>{activeFilters ? <button type="button" className="lf-button lf-button-secondary" onClick={resetFilters}>Reset filters</button> : <button type="button" className="lf-button lf-button-primary" onClick={() => setShowAdd(true)}>Add Lead</button>}</div>}
      {data?.items?.length > 0 && <><LeadTable leads={data.items} onOpen={setSelectedId} /><LeadCards leads={data.items} onOpen={setSelectedId} /></>}
      {data?.total > 0 && <nav className="lead-workspace-pagination" aria-label="Lead pages"><span>Showing {firstResult}–{lastResult} of {data.total}</span><div><button type="button" className="lf-button lf-button-secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {data.page} of {data.pages}</span><button type="button" className="lf-button lf-button-secondary" disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)}>Next</button></div></nav>}
    </section>
    {selectedId && <LeadDetails leadId={selectedId} onClose={closeDetails} onSaved={refresh} />}
    {showAdd && <AddLeadDialog onClose={closeAdd} onCreated={leadCreated} />}
  </div>;
}
