import { NavLink } from "react-router-dom";

const navigation = [
  {
    label: "Dashboard",
    path: "/",
    icon: "◫",
  },
  {
    label: "Leads",
    path: "/leads",
    icon: "◎",
  },
  {
    label: "Intelligence",
    path: "/intelligence",
    icon: "✦",
  },
  {
    label: "Reports",
    path: "/reports",
    icon: "▤",
  },
  {
    label: "Settings",
    path: "/settings",
    icon: "⚙",
  },
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">
          <span>LF</span>
        </div>

        <div>
          <div className="brand-name">LeadForge</div>
          <div className="brand-version">AI LEAD ENGINE</div>
        </div>
      </div>

      <div className="sidebar-section-label">
        WORKSPACE
      </div>

      <nav className="sidebar-nav">
        {navigation.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `nav-item ${isActive ? "active" : ""}`
            }
            title={item.label}
          >
            <strong>{item.icon}</strong>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="system-status">
          <span className="status-dot" />

          <div>
            <div className="status-title">
              System Online
            </div>

            <div className="status-subtitle">
              Lead intelligence active
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;