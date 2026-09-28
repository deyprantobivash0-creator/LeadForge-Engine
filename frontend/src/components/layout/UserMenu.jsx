import { UserCircle } from "lucide-react";

export default function UserMenu() {
  return (
    <button className="user-menu">
      <UserCircle size={22} />
      <div>
        <strong>Admin</strong>
        <small>LeadForge</small>
      </div>
    </button>
  );
}