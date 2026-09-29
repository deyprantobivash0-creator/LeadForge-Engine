import {
  LayoutDashboard,
  Users,
  BarChart3,
  Sparkles,
  Upload,
  Settings,
} from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";

import NavItem from "./NavItem";
import OrganizationSwitcher from "./OrganizationSwitcher";
import UserMenu from "./UserMenu";

export default function Sidebar({ page, setPage }) {
   const navigate = useNavigate();
   const location = useLocation();

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
              icon={<LayoutDashboard size={20}/>}
              label="Dashboard"
             active={location.pathname === "/dashboard"}
             onClick={() => navigate("/")}
            />

            <NavItem
              icon={<Users size={20}/>}
              label="Leads"
              active={location.pathname === "/leads"}
              onClick={() => navigate("/leads")}
            />

            <NavItem
             icon={<Sparkles size={20}/>}
             label="AI Intelligence"
             active={location.pathname === "/ai"}
             onClick={() => navigate("/ai")}
            />

            <NavItem
              icon={<Upload size={20}/>}
              label="Import"
              active={location.pathname === "/imports"}
              onClick={() => navigate("/imports")}
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