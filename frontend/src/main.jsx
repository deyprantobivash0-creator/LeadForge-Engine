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

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ReleaseErrorBoundary><App /></ReleaseErrorBoundary>
  </React.StrictMode>
);