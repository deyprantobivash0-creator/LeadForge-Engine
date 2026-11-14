import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/inter";
import "./styles/global.css";
import App from "./App";
import ReleaseErrorBoundary from "./components/common/ReleaseErrorBoundary";
import "./styles/workspace.css";
import "./styles/theme.css";
import "./styles/tokens.css";
import "./styles/release-hardening.css";

const rootContainer = document.getElementById("root");
if (rootContainer === null) {
  // Preserve the installed ReactDOM failure in development and production.
  throw new Error(
    import.meta.env.PROD
      ? "Minified React error #299; visit https://react.dev/errors/299 for the full message or use the non-minified dev environment for full errors and additional helpful warnings."
      : "Target container is not a DOM element."
  );
}

ReactDOM.createRoot(rootContainer).render(
  <React.StrictMode>
    <ReleaseErrorBoundary><App /></ReleaseErrorBoundary>
  </React.StrictMode>
);