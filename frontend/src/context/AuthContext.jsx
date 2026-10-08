import { createContext, useContext, useEffect, useState } from "react";
import api, { configureApi } from "../services/api";

const AuthContext = createContext(null);
const preferenceKey = (userId) => `leadforge-workspace-${userId}`;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [organization, setOrganization] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accessMessage, setAccessMessage] = useState("");

  function clearAuth() {
    setUser(null);
    setOrganizations([]);
    setOrganization(null);
    setAccessMessage("");
  }

  async function loadOrganizations(currentUser, currentId = null) {
    const available = await api.get("/api/organizations");
    setOrganizations(available);
    const preferred = currentId ?? localStorage.getItem(preferenceKey(currentUser.id));
    const valid = available.find((item) => String(item.id) === String(preferred));
    setOrganization(valid || null);
    if (!valid) localStorage.removeItem(preferenceKey(currentUser.id));
    return valid;
  }

  async function restoreSession() {
    setLoading(true);
    setError("");
    try {
      const currentUser = await api.get("/api/auth/me", { handleAuth: false });
      setUser(currentUser);
      await loadOrganizations(currentUser);
    } catch (failure) {
      if (failure.status === 401) clearAuth();
      else setError(failure.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { restoreSession(); }, []);

  async function login(email, password) {
    const result = await api.post("/api/auth/login", { email, password }, { handleAuth: false });
    setUser(result.user);
    setError("");
    setAccessMessage("");
    try {
      await loadOrganizations(result.user);
    } catch (failure) {
      setError(failure.message);
    }
  }

  async function logout() {
    try {
      await api.post("/api/auth/logout", undefined, { handleAuth: false });
    } catch (failure) {
      if (failure.status !== 401) throw failure;
    }
    if (user) localStorage.removeItem(preferenceKey(user.id));
    clearAuth();
  }

  function selectOrganization(id) {
    const selected = organizations.find((item) => String(item.id) === String(id));
    if (!selected) return;
    setOrganization(selected);
    setAccessMessage("");
    localStorage.setItem(preferenceKey(user.id), String(selected.id));
  }

  async function handleForbidden() {
    if (!user) return;
    try {
      const stillAvailable = await loadOrganizations(user, organization?.id);
      setAccessMessage(stillAvailable ? "Access denied for this action." : "Workspace access changed. Choose an available workspace.");
    } catch (failure) {
      if (failure.status !== 401) setError(failure.message);
    }
  }

  configureApi({
    organizationId: organization?.id ?? null,
    unauthorized: () => { clearAuth(); setAccessMessage("Your session has ended. Sign in again to continue."); },
    forbidden: handleForbidden,
  });

  return <AuthContext.Provider value={{
    user, organizations, organization, loading, error, accessMessage,
    login, logout, restoreSession, selectOrganization, clearAuth,
  }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider is required");
  return context;
}
