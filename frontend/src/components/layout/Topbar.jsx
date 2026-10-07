import { useAuth } from "../../context/AuthContext";

export default function TopBar() {
  const { user, organization } = useAuth();
  return <header className="topbar">
    <div className="topbar-left"><span className="topbar-label">WORKSPACE</span><strong>{organization?.name}</strong></div>
    <div className="topbar-right"><span className="topbar-user">{user?.email}</span></div>
  </header>;
}
