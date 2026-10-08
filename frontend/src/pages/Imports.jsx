import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Download, FileSpreadsheet, Upload } from "lucide-react";
import { previewLeadCsv, confirmLeadImport } from "../services/importService";
import "../styles/import-center.css";

export default function Imports() {
  const inputRef = useRef(null);
  const busyRef = useRef(false);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);

  function selectFile(next) {
    if (busyRef.current) return;
    setError(""); setPreview(null); setResult(null);
    if (!next) return;
    if (next.size === 0) { setFile(null); setError("This CSV is empty. Add a header and at least one lead row."); return; }
    if (!next.name.toLowerCase().endsWith(".csv")) { setFile(null); setError("Choose a .csv file."); return; }
    if (next.size > 1024 * 1024) { setFile(null); setError("CSV file exceeds the 1 MB limit."); return; }
    setFile(next);
  }

  async function run(action) {
    if (busyRef.current || !file) return;
    busyRef.current = true; setBusy(action); setError("");
    try {
      if (action === "preview") setPreview(await previewLeadCsv(file));
      else { setResult(await confirmLeadImport(file, preview.token)); setPreview(null); }
    } catch (caught) { setError(caught.message); }
    finally { busyRef.current = false; setBusy(""); }
  }

  function reset() { setFile(null); setPreview(null); setResult(null); setError(""); if (inputRef.current) inputRef.current.value = ""; }
  function downloadTemplate() {
    const url = URL.createObjectURL(new Blob(["company,email,source\n"], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "leadforge-leads-template.csv"; anchor.click();
    URL.revokeObjectURL(url);
  }

  const step = result ? 3 : preview ? 2 : 1;
  return <div className="import-center">
    <header className="import-hero"><div><span className="section-kicker">LEADFORGE / IMPORT CENTER</span><h1>Bring your leads into focus.</h1><p>Review every row before it enters this workspace. Imported leads wait for your decision to analyze them.</p></div><button className="lf-button lf-button-secondary" type="button" onClick={downloadTemplate}><Download size={16} /> Download CSV template</button></header>
    <ol className="import-steps" aria-label="Import progress">{["Upload", "Review", "Result"].map((label, index) => <li key={label} className={step === index + 1 ? "current" : step > index + 1 ? "complete" : ""} aria-current={step === index + 1 ? "step" : undefined}><span>{index + 1}</span>{label}</li>)}</ol>
    {error && <div className="import-error" role="alert">{error}</div>}
    <div className="import-live" role="status" aria-live="polite">{busy === "preview" ? "Checking your CSV…" : busy === "confirm" ? "Importing leads…" : ""}</div>
    {step === 1 && <section className="intelligence-card import-panel" aria-labelledby="import-upload-title">
      <div className="import-panel-heading"><span className="import-icon"><FileSpreadsheet size={24} /></span><div><span className="section-kicker">STEP 01</span><h2 id="import-upload-title">Upload a CSV</h2><p>Company, email, and source are required. Up to 1 MB and 1,000 data rows.</p></div></div>
      <div className={`import-drop ${dragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); selectFile(event.dataTransfer.files[0]); }}>
        <Upload size={28} aria-hidden="true" /><strong>{file ? file.name : "Drop your CSV here"}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KB selected` : "or choose a file from your computer"}</span><label htmlFor="lead-import-file" className="lf-button lf-button-secondary">Choose CSV</label><input id="lead-import-file" ref={inputRef} type="file" disabled={!!busy} accept=".csv,text/csv" aria-label="Choose CSV file" onChange={(event) => selectFile(event.target.files[0])} />
      </div><div className="import-footer"><p>Only valid, unique rows will be imported. Existing leads are never overwritten.</p><button className="lf-button lf-button-primary" type="button" disabled={!file || !!busy} onClick={() => run("preview")}>{busy === "preview" ? "Checking CSV…" : "Preview import"}<ArrowRight size={16} /></button></div>
    </section>}
    {step === 2 && <><section className="intelligence-card import-panel" aria-labelledby="import-review-title"><span className="section-kicker">STEP 02 / {file?.name}</span><h2 id="import-review-title">Review before importing</h2><p>Duplicates and invalid rows will be skipped. This preview has not created any leads.</p><div className="import-summary">{[["Total rows", preview.summary.total], ["Ready", preview.summary.ready], ["Duplicates", preview.summary.duplicates], ["Invalid", preview.summary.invalid]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>{preview.ignored_headers.length > 0 && <p className="import-notice">Ignored columns: {preview.ignored_headers.join(", ")}</p>}</section>
      <section className="intelligence-card import-panel" aria-labelledby="import-rows-title"><div><h2 id="import-rows-title">Row preview</h2><p>Showing first {preview.rows.length} of {preview.summary.total} rows.</p></div><div className="import-table-wrap"><table><thead><tr><th scope="col">Row</th><th scope="col">Company</th><th scope="col">Email</th><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Issue</th></tr></thead><tbody>{preview.rows.map((row, index) => <tr key={`${row.row_number}-${index}`}><td data-label="Row">{row.row_number}</td><td data-label="Company">{row.company || "—"}</td><td data-label="Email">{row.email || "—"}</td><td data-label="Source">{row.source || "—"}</td><td data-label="Status"><span className={`import-status ${row.status}`}>{row.status}</span></td><td data-label="Issue">{row.errors.join(" ") || "—"}</td></tr>)}</tbody></table></div><div className="import-footer"><button type="button" className="lf-button lf-button-secondary" disabled={!!busy} onClick={reset}>Choose another file</button><button type="button" className="lf-button lf-button-secondary" disabled={!!busy} onClick={() => run("preview")}>Refresh preview</button><button type="button" className="lf-button lf-button-primary" disabled={!!busy || preview.summary.ready === 0} onClick={() => run("confirm")}>{busy === "confirm" ? "Importing…" : `Import ${preview.summary.ready} ${preview.summary.ready === 1 ? "lead" : "leads"}`}</button></div></section></>}
    {step === 3 && <section className="intelligence-card import-panel import-result" aria-labelledby="import-result-title"><span className="section-kicker">STEP 03 / COMPLETE</span><h2 id="import-result-title">Import complete</h2><p>The leads are available in your workspace. No AI analysis was started.</p><div className="import-summary">{[["Imported", result.imported], ["Duplicates skipped", result.duplicates], ["Invalid skipped", result.invalid]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div><div className="import-footer"><button type="button" className="lf-button lf-button-secondary" onClick={reset}>Import another file</button><Link className="lf-button lf-button-primary" to="/leads">View leads <ArrowRight size={16} /></Link></div></section>}
  </div>;
}
