import { Component } from "react";

export default class ReleaseErrorBoundary extends Component {
  state = { failed: false, reference: "" };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() {
    const reference = crypto.randomUUID();
    this.setState({ reference });
    // Allowlisted diagnostics only: error messages/stacks can contain customer data.
    console.warn(JSON.stringify({ event: "ui.render.failed", reference, surface: "application" }));
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return <main className="auth-screen"><section className="auth-card glass" role="alert">
      <h1>We could not display this page.</h1><p>Your saved workspace data has not been changed. Reload to try again.</p>
      {this.state.reference && <p>Support reference: {this.state.reference}</p>}
      <button className="btn-primary" type="button" onClick={() => window.location.reload()}>Reload application</button>
    </section></main>;
  }
}
