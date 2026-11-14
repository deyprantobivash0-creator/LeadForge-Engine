import { useEffect, useRef, useState } from "react";
import { leadFields, apiFieldErrors } from "../../utils/validation";
import { createLead } from "../../services/leadService";

/** @param {{onClose:()=>void,onCreated:()=>void}} props */
export default function AddLeadDialog({ onClose, onCreated }) {
  const dialogRef = useRef(/** @type {HTMLDivElement|null} */ (null));
  const companyRef = useRef(/** @type {HTMLInputElement|null} */ (null));
  const savingRef = useRef(false);
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [source, setSource] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState(/** @type {import('../../utils/validation').LeadFieldErrors} */ ({}));

  useEffect(() => {
    const previousFocus = document.activeElement;
    companyRef.current?.focus();
    /** @param {KeyboardEvent} event */
    function handleKey(event) {
      if (event.key === "Escape" && !savingRef.current) { event.preventDefault(); onClose(); }
      if (event.key !== "Tab") return;
      const dialog = dialogRef.current;
      if (!dialog) return;
      const controls = [...dialog.querySelectorAll("button:not(:disabled), input:not(:disabled)")];
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); if (last instanceof HTMLElement) last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); if (first instanceof HTMLElement) first.focus(); }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      if (previousFocus && "focus" in previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
    };
  }, [onClose]);

  /** @param {import('react').FormEvent<HTMLFormElement>} event @returns {Promise<void>} */
  async function submit(event) {
    event.preventDefault();
    if (savingRef.current) return;
    const invalid = leadFields({ company, email, source });
    setFields(invalid);
    if (Object.keys(invalid).length) {
      const invalidField = dialogRef.current?.querySelector(`#new-lead-${Object.keys(invalid)[0]}`);
      if (invalidField instanceof HTMLElement) invalidField.focus();
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError("");
    try {
      await createLead({ company: company.trim(), email: email.trim(), source: source.trim() });
      onCreated();
    } catch (failure) {
      setFields(apiFieldErrors(failure));
      if (failure === null || (typeof failure !== "object" && typeof failure !== "function") || !("message" in failure) || typeof failure.message !== "string") throw failure;
      setError("status" in failure && failure.status === 409 ? "A lead with this email already exists in this workspace." : failure.message);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  return <div className="lead-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) onClose(); }}>
    <div className="lead-dialog" role="dialog" aria-modal="true" aria-labelledby="add-lead-title" ref={dialogRef}>
      <div className="lead-dialog-header"><div><span className="section-kicker">LEAD WORKSPACE</span><h2 id="add-lead-title">Add a lead</h2></div><button type="button" className="lead-dialog-close" onClick={onClose} disabled={saving} aria-label="Close Add Lead dialog">×</button></div>
      <p className="lead-dialog-intro">Add a company and contact email to this workspace.</p>
      <form onSubmit={submit} className="lead-dialog-form">
        <label htmlFor="new-lead-company">Company</label><input ref={companyRef} id="new-lead-company" aria-invalid={!!fields.company} aria-describedby={fields.company ? "company-error" : undefined} value={company} onChange={(event) => setCompany(event.target.value)} required maxLength={200} autoComplete="organization" />
        <label htmlFor="new-lead-email">Email</label><input id="new-lead-email" aria-invalid={!!fields.email} aria-describedby={fields.email ? "email-error" : undefined} type="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={200} autoComplete="email" />
        <label htmlFor="new-lead-source">Source</label><input id="new-lead-source" aria-invalid={!!fields.source} aria-describedby={fields.source ? "source-error" : undefined} value={source} onChange={(event) => setSource(event.target.value)} required maxLength={100} placeholder="Where this lead came from" />
        {Object.entries(fields).map(([field, message]) => <p id={`${field}-error`} key={field} className="lead-dialog-error" role="alert">{message}</p>)}
        {error && <p role="alert" className="lead-dialog-error">{error}</p>}
        <div className="lead-dialog-actions"><button type="button" className="lf-button lf-button-secondary" onClick={onClose} disabled={saving}>Cancel</button><button type="submit" className="lf-button lf-button-primary" disabled={saving}>{saving ? "Adding..." : "Add Lead"}</button></div>
      </form>
    </div>
  </div>;
}
