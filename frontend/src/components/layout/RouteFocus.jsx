import { useEffect } from "react";
import { useLocation } from "react-router-dom";

export default function RouteFocus() {
  const { pathname } = useLocation();
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const heading = document.querySelector("main h1");
      document.title = `${heading?.textContent || (pathname.startsWith("/ai/") ? "Lead Intelligence" : "Workspace")} | LeadForge`;
      const main = document.getElementById("main-content");
      main?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [pathname]);
  return null;
}
