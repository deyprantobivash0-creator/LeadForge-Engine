import { useLocation } from "react-router-dom";

const pageDetails = {
  "/": {
    title: "Dashboard",
    subtitle: "Lead pipeline and intelligence overview",
  },
  "/leads": {
    title: "Lead Management",
    subtitle: "Manage, qualify and track your leads",
  },
  "/intelligence": {
    title: "AI Intelligence",
    subtitle: "Explore lead insights and recommendations",
  },
  "/reports": {
    title: "Reports",
    subtitle: "Performance and lead intelligence reports",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Configure your LeadForge workspace",
  },
};

function Topbar() {
  const location = useLocation();

  const page =
    pageDetails[location.pathname] || {
      title: "LeadForge",
      subtitle: "Autonomous lead intelligence platform",
    };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-page-info">
          <strong>{page.title}</strong>
          <span>{page.subtitle}</span>
        </div>
      </div>

      <div className="topbar-right">
        <div className="search-box">
          <span>⌕</span>

          <input
            type="text"
            placeholder="Search leads, companies..."
            aria-label="Search"
          />
        </div>

        <div className="connection-status">
          <span className="status-dot" />
          <span>API Connected</span>
        </div>

        <button
          className="icon-button"
          type="button"
          title="Notifications"
          aria-label="Notifications"
        >
          ◉
        </button>

        <div className="user-profile">
          <div className="user-avatar">
            PD
          </div>

          <div>
            <div className="user-name">
              Pranto Dey
            </div>

            <div className="user-role">
              Workspace Owner
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

export default Topbar;