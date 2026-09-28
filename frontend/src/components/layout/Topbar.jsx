import { Search, Bell } from "lucide-react";

export default function TopBar() {
  return (
    <div className="topbar">
      <div className="search-box">
        <Search size={18} />

        <input
          placeholder="Search leads, companies, contacts..."
        />
      </div>

      <button className="notification-btn">
        <Bell size={20} />
      </button>
    </div>
  );
}