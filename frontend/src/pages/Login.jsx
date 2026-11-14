import { useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login, accessMessage } = useAuth();
  const busyRef = useRef(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(/** @type {string|undefined} */ (""));

  /** @param {import('react').FormEvent<HTMLFormElement>} event @returns {Promise<void>} */
  async function submit(event) {
    event.preventDefault();
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setMessage("");
    try {
      await login(email, password);
    } catch (error) {
      // Preserve absent-error failures and existing status-message precedence.
      if (error === null || error === undefined) throw new TypeError(`Cannot read properties of ${error} (reading 'status')`);
      const failure = typeof error === "object" || typeof error === "function" ? error : undefined;
      const status = failure && "status" in failure ? failure.status : undefined;
      if (status === 401) setMessage("Invalid email or password.");
      else if (status === 429) setMessage("Too many attempts. Wait a minute and try again.");
      else if (status === 422) setMessage("Enter a valid email and password.");
      else {
        const failureMessage = failure && "message" in failure ? failure.message : undefined;
        if (failureMessage !== undefined && typeof failureMessage !== "string") throw error;
        setMessage(failureMessage);
      }
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return <main className="auth-screen">
    <form className="auth-card glass" onSubmit={submit}>
      <span className="section-eyebrow">LEADFORGE / ACCOUNT</span>
      <h1>Sign in</h1>
      <p>Access your workspace.</p>
      {accessMessage && <p role="status">{accessMessage}</p>}
      <label htmlFor="login-email">Email</label>
      <input id="login-email" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
      <label htmlFor="login-password">Password</label>
      <input id="login-password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
      {message && <p role="alert" className="auth-error">{message}</p>}
      <button className="btn-primary" type="submit" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
    </form>
  </main>;
}
