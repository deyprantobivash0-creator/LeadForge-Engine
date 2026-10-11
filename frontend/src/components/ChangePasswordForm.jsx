import { useRef, useState } from "react";
import api from "../services/api";

const emptyPasswords = { current: "", next: "", confirm: "" };

export default function ChangePasswordForm() {
  const [passwords, setPasswords] = useState(emptyPasswords);
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  function edit(field, value) {
    setPasswords((values) => ({ ...values, [field]: value }));
    setErrors({});
    setMessage("");
  }

  async function submit(event) {
    event.preventDefault();
    if (busyRef.current) return;
    const invalid = {};
    if (!passwords.current) invalid.current = "Enter your current password.";
    const length = Array.from(passwords.next).length;
    if (length < 15 || length > 1024 || passwords.next.includes("\u0000")) invalid.next = "New password must contain 15 to 1024 characters and no NUL characters.";
    else if (passwords.next === passwords.current) invalid.next = "New password must differ from current password.";
    if (passwords.confirm !== passwords.next) invalid.confirm = "Passwords do not match.";
    setErrors(invalid);
    setMessage("");
    if (Object.keys(invalid).length) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await api.post("/api/auth/change-password", {
        current_password: passwords.current, new_password: passwords.next,
      });
      setPasswords(emptyPasswords);
      setMessage("Password changed successfully.");
    } catch (failure) {
      if (failure.message === "Current password is incorrect.") setErrors({ current: failure.message });
      else setErrors({ form: failure.message });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return <form className="settings-password-form" onSubmit={submit} noValidate aria-labelledby="change-password-title" aria-busy={busy}>
    <h3 id="change-password-title">Change Password</h3>
    <p id="password-policy">Use 15 to 1024 characters. Other active sessions will be signed out; this session stays active.</p>
    {[["current", "Current password", "current-password"], ["next", "New password", "new-password"], ["confirm", "Confirm new password", "new-password"]].map(([field, label, autocomplete]) =>
      <div className="settings-password-field" key={field}>
        <label htmlFor={`password-${field}`}>{label}</label>
        <input id={`password-${field}`} name={field === "current" ? "current_password" : field === "next" ? "new_password" : "confirm_password"}
          type="password" autoComplete={autocomplete} required disabled={busy} value={passwords[field]}
          aria-invalid={!!errors[field]} aria-describedby={errors[field] ? `password-${field}-error` : field === "next" ? "password-policy" : undefined}
          onChange={(event) => edit(field, event.target.value)} />
        {errors[field] && <p id={`password-${field}-error`} className="settings-error" role="alert">{errors[field]}</p>}
      </div>)}
    {errors.form && <p className="settings-error" role="alert">{errors.form}</p>}
    {message && <p className="settings-password-success" role="status">{message}</p>}
    <button className="lf-button lf-button-primary" type="submit" disabled={busy}>{busy ? "Changing password…" : "Change Password"}</button>
  </form>;
}
