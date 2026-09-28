import {
  LayoutDashboard,
  Users,
  BarChart3,
  Sparkles,
  Upload,
  Settings,
} from "lucide-react";

import NavItem from "./NavItem";
import OrganizationSwitcher from "./OrganizationSwitcher";
import UserMenu from "./UserMenu";

export default function Sidebar() {
  return (
    <aside className="sidebar">

      <div>

        <div className="logo-area">
          <div className="logo-circle">
            ✦
          </div>

          <div>
            <h3>LeadForge</h3>
            <small>Engine v1.0</small>
          </div>
        </div>

        <OrganizationSwitcher />

        <nav className="sidebar-nav">

          <NavItem
            icon={<LayoutDashboard size={20} />}
            label="Dashboard"
            active
          />

          <NavItem
            icon={<Users size={20} />}
            label="Leads"
          />

          <NavItem
            icon={<Sparkles size={20} />}
            label="AI Intelligence"
          />

          <NavItem
            icon={<Upload size={20} />}
            label="Import"
          />

          <NavItem
            icon={<BarChart3 size={20} />}
            label="Reports"
          />

          <NavItem
            icon={<Settings size={20} />}
            label="Settings"
          />

        </nav>

      </div>

      <UserMenu />

    </aside>
  );
}