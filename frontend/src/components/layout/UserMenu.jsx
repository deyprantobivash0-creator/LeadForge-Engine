import { UserCircle } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../../context/AuthContext";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [error, setError] = useState("");
  return (
    <div className="user-menu">
      <UserCircle size={22} />
      <div>
        <strong>{user?.email}</strong>
        <button type="button" onClick={() => logout().catch((failure) => setError(failure.message))}>Sign out</button>
        {error && <small role="alert">{error}</small>}
      </div>
    </div>
  );
}
