import {
  BrowserRouter,
  Routes,
  Route,
  Link,
} from "react-router-dom";

import Sidebar from "./components/layout/Sidebar";
import Topbar from "./components/layout/Topbar";
import PageContainer from "./components/layout/PageContainer";

import Dashboard from "./pages/Dashboard";
import Leads from "./pages/Leads";
import Intelligence from "./pages/Intelligence";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import Imports from "./pages/Imports";
import Login from "./pages/Login";
import WorkspaceSelection from "./pages/WorkspaceSelection";
import { AuthProvider, useAuth } from "./context/AuthContext";

import "./App.css";
import "./styles/leadforge.css";

function NotFound() {
  return <section className="route-not-found"><span className="section-kicker">LEADFORGE / NAVIGATION</span><h1>Page not found</h1><p>This address does not match a LeadForge workspace page.</p><Link className="lf-button lf-button-secondary" to="/">Open Dashboard</Link></section>;
}
function AppContent() {
  const { user, organization, loading, error, accessMessage, restoreSession } = useAuth();
  if (loading) return <main className="auth-screen">Restoring session...</main>;
  if (error) return <main className="auth-screen"><div className="auth-card glass" role="alert"><p>{error}</p><button onClick={restoreSession}>Retry</button></div></main>;
  if (!user) return <Login />;
  if (!organization) return <WorkspaceSelection />;
  return (
      <div className="app-shell" key={organization.id}>
        <div className="bg-orb orb-purple"></div>
        <div className="bg-orb orb-blue"></div>
        <div className="bg-orb orb-sage"></div>
        <Sidebar />

        <div className="main-area">
          <Topbar />
          {accessMessage && <p role="alert" className="auth-error">{accessMessage}</p>}

          <PageContainer>
            <Routes>
              <Route path="/" element={<Dashboard />} />

              <Route
                path="/leads"
                element={<Leads />}
              />
              <Route path="/imports" element={<Imports />} />

              <Route
                path="/ai"
                element={<Intelligence />}
              />
              <Route path="/ai/:leadId" element={<Intelligence />} />

              <Route
                path="/reports"
                element={<Reports />}
              />

              <Route
                path="/settings"
                element={<Settings />}
              />

              <Route
                path="*"
                element={<NotFound />}
              />
            </Routes>
          </PageContainer>
        </div>
      </div>
  );
}

function App() {
  return <BrowserRouter><AuthProvider><AppContent /></AuthProvider></BrowserRouter>;
}

export default App;
