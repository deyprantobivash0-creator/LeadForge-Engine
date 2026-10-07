import { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function WorkspaceSelection() {
  const { organizations, selectOrganization, logout, accessMessage } = useAuth();
  const [error, setError] = useState("");
  return <main className="auth-screen">
    <section className="auth-card glass">
      <span className="section-eyebrow">WORKSPACE</span>
      <h1>Select a workspace</h1>
      {accessMessage && <p role="alert" className="auth-error">{accessMessage}</p>}
      {organizations.length === 0 ? <p>No active workspaces are available for this account.</p> :
        <div className="workspace-options">{organizations.map((item) =>
          <button type="button" key={item.id} onClick={() => selectOrganization(item.id)}>{item.name} <small>{item.role}</small></button>
        )}</div>}
      <button type="button" onClick={() => logout().catch((failure) => setError(failure.message))}>Sign out</button>
      {error && <p role="alert" className="auth-error">{error}</p>}
    </section>
  </main>;
}
