import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/inter";
import "./styles/global.css";
import App from "./App";
import "./styles/workspace.css";
import "./styles/theme.css";
import "./styles/tokens.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);