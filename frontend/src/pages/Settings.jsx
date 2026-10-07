import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getSettingsOverview } from "../services/settingsService";
import "../styles/settings-workspace.css";

const statusLabel = {
  development_only: "Development only",
  configuration_ready: "Configuration present",
  configuration_required: "Configuration required",
  not_available: "Not available",
};

function Capability({ name, available, description, to, action }) {
  return <div className="settings-capability"><div><h3>{name}</h3><p>{description}</p></div><div><span className={`settings-state ${available ? "is-available" : ""}`}>{available ? "Available" : "Not available"}</span>{to && <Link to={to}>{action}</Link>}</div></div>;
}

export default function Settings() {
  const { organization, logout } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [logoutError, setLogoutError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    getSettingsOverview().then((result) => { if (active) setData(result); })
      .catch((failure) => { if (active) setError(failure.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [organization?.id, revision]);

  async function signOut() {
    setSigningOut(true);
    setLogoutError("");
    try { await logout(); }
    catch (failure) { setLogoutError(failure.message); setSigningOut(false); }
  }

  return <div className="settings-page">
    <header className="settings-header"><span className="section-kicker">LEADFORGE / SETTINGS</span><h1>Settings &amp; Integrations</h1><p>Manage workspace information and review LeadForge system capabilities.</p></header>
    {loading && <div className="settings-loading" role="status" aria-live="polite"><p>Loading workspace settings…</p><div /><div /></div>}
    {!loading && error && <section className="settings-panel" role="alert"><h2>Settings unavailable</h2><p>{error}</p><button type="button" className="lf-button lf-button-secondary" onClick={() => { setLoading(true); setError(""); setData(null); setRevision((value) => value + 1); }}>Retry</button></section>}
    {!loading && data && <>
      <nav className="settings-nav" aria-label="Settings sections"><a href="#settings-overview">Overview</a><a href="#settings-workspace">Workspace</a><a href="#settings-ai">AI processing</a><a href="#settings-data">Data &amp; reporting</a><a href="#settings-integrations">Integrations</a><a href="#settings-security">Security &amp; account</a></nav>
      <section id="settings-overview" className="settings-panel"><span className="section-kicker">CAPABILITY STATUS</span><h2>Workspace overview</h2><p>Current capabilities for this workspace. These labels do not indicate external provider connectivity.</p><div className="settings-status-grid"><div><span>Lead management</span><strong>Available</strong></div><div><span>CSV import</span><strong>{data.capabilities.csv_import ? "Available" : "Not available"}</strong></div><div><span>AI processing</span><strong>{statusLabel[data.ai.status]}</strong></div><div><span>Historical reports</span><strong>{data.capabilities.historical_reports ? "Available" : "Not available"}</strong></div></div></section>
      <div className="settings-grid"><section id="settings-workspace" className="settings-panel"><span className="section-kicker">ACTIVE WORKSPACE</span><h2>Workspace</h2><dl className="settings-facts"><div><dt>Name</dt><dd>{data.workspace.name}</dd></div><div><dt>Slug</dt><dd>{data.workspace.slug}</dd></div><div><dt>Your role</dt><dd className="settings-capitalize">{data.workspace.role}</dd></div><div><dt>Access</dt><dd>Authorized</dd></div></dl></section>
        <section id="settings-ai" className="settings-panel"><span className="section-kicker">SERVER CONFIGURATION</span><h2>AI processing</h2><p>Provider selection is managed on the server. Settings does not test provider connectivity or use provider credits.</p><dl className="settings-facts"><div><dt>Provider</dt><dd>{data.ai.display_name}</dd></div><div><dt>Status</dt><dd><span className={`settings-state ${data.ai.processing_available ? "is-available" : ""}`}>{statusLabel[data.ai.status]}</span></dd></div></dl><p className="settings-note">{data.ai.detail}</p></section></div>
      <div className="settings-grid"><section id="settings-data" className="settings-panel"><span className="section-kicker">DATA &amp; REPORTING</span><h2>Working with LeadForge data</h2><div className="settings-capabilities"><Capability name="CSV Import" available={data.capabilities.csv_import} description="UTF-8 CSV with company, email, and source. Up to 1 MiB and 1,000 rows. Imported Leads await analysis." to="/imports" action="Open Import Center" /><Capability name="Historical Intelligence Reports" available={data.capabilities.historical_reports} description="Review saved analysis events by UTC period and export the selected report as CSV." to="/reports" action="Open Reports" /></div></section>
        <section id="settings-integrations" className="settings-panel"><span className="section-kicker">INTEGRATIONS</span><h2>Integration availability</h2><p>Planned integrations cannot be connected in this release.</p><div className="settings-capabilities"><Capability name="HubSpot CRM" available={false} description="CRM synchronization is planned for a later release." /><Capability name="OpenClaw Automation" available={false} description="Workflow automation is planned for a later release." /></div></section></div>
      <section id="settings-security" className="settings-panel settings-account"><div><span className="section-kicker">SECURITY &amp; ACCOUNT</span><h2>Your account</h2><p>Authenticated access to this selected workspace.</p><dl className="settings-facts"><div><dt>Email</dt><dd>{data.account.email}</dd></div><div><dt>Session</dt><dd>Active browser session</dd></div><div><dt>Workspace access</dt><dd>Authorized membership</dd></div></dl></div><div><button type="button" className="lf-button lf-button-secondary" onClick={signOut} disabled={signingOut}>{signingOut ? "Signing out…" : "Sign out"}</button>{logoutError && <p className="settings-error" role="alert">{logoutError}</p>}</div></section>
    </>}
  </div>;
}
