import {
  LayoutDashboard,
  Users,
  BarChart3,
  Sparkles,
  Settings,
  Upload,
} from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";

import NavItem from "./NavItem";
import OrganizationSwitcher from "./organizationSwitcher";
import UserMenu from "./UserMenu";

export default function Sidebar() {
   const navigate = useNavigate();
   const location = useLocation();

  return (
    <aside className="sidebar">

      <div>

        <div className="logo-area">
          <div className="logo-circle glow-purple">
            ✦
          </div>

          <div>
            <h3>LeadForge</h3>
            <small>Revenue intelligence</small>
          </div>
        </div>

        <OrganizationSwitcher />

          <nav className="sidebar-nav" aria-label="Main navigation">

             <NavItem
              icon={<LayoutDashboard size={20}/>}
              label="Dashboard"
             active={location.pathname === "/"}
             onClick={() => navigate("/")}
            />

            <NavItem
              icon={<Users size={20}/>}
              label="Leads"
              active={location.pathname === "/leads"}
              onClick={() => navigate("/leads")}
            />

            <NavItem
              icon={<Upload size={20}/>}
              label="Import"
              active={location.pathname === "/imports"}
              onClick={() => navigate("/imports")}
            />

            <NavItem
             icon={<Sparkles size={20}/>}
             label="AI Intelligence"
             active={location.pathname === "/ai" || location.pathname.startsWith("/ai/")}
             onClick={() => navigate("/ai")}
            />

            <NavItem
              icon={<BarChart3 size={20}/>}
              label="Reports"
             active={location.pathname === "/reports"}
             onClick={() => navigate("/reports")}
            />

            <NavItem
                icon={<Settings size={20}/>}
                label="Settings"
               active={location.pathname === "/settings"}
               onClick={() => navigate("/settings")}
            />

          </nav>

         
         

      </div>

      <UserMenu />

    </aside>
  );
}
