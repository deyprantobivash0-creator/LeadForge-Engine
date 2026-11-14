import { createContext, useContext, useEffect, useState } from "react";
import api, { ApiError, configureApi } from "../services/api";

const AuthContext = createContext(/** @type {import('../types/api').AuthContextValue|null} */ (null));
/** @param {number} userId */
const preferenceKey = (userId) => `leadforge-workspace-${userId}`;

/** @param {{children:import('react').ReactNode}} props */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(/** @type {import('../types/api').User|null} */ (null));
  const [organizations, setOrganizations] = useState(/** @type {import('../types/api').Organization[]} */ ([]));
  const [organization, setOrganization] = useState(/** @type {import('../types/api').Organization|null} */ (null));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accessMessage, setAccessMessage] = useState("");

  function clearAuth() {
    setUser(null);
    setOrganizations([]);
    setOrganization(null);
    setAccessMessage("");
  }

  /** @param {import('../types/api').User} currentUser @param {number|null} [currentId] */
  async function loadOrganizations(currentUser, currentId = null) {
    /** @type {import('../types/api').Organization[]} */
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
      /** @type {import('../types/api').User} */
      const currentUser = await api.get("/api/auth/me", { handleAuth: false });
      setUser(currentUser);
      await loadOrganizations(currentUser);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) clearAuth();
      else if (failure instanceof Error) setError(failure.message);
      else throw failure;
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { restoreSession(); }, []);

  /** @param {string} email @param {string} password */
  async function login(email, password) {
    /** @type {import('../types/api').LoginResponse} */
    const result = await api.post("/api/auth/login", { email, password }, { handleAuth: false });
    setUser(result.user);
    setError("");
    setAccessMessage("");
    try {
      await loadOrganizations(result.user);
    } catch (failure) {
      if (failure instanceof Error) setError(failure.message);
      else throw failure;
    }
  }

  async function logout() {
    try {
      await api.post("/api/auth/logout", undefined, { handleAuth: false });
    } catch (failure) {
      if (!(failure instanceof ApiError && failure.status === 401)) throw failure;
    }
    if (user) localStorage.removeItem(preferenceKey(user.id));
    clearAuth();
  }

  /** @param {import('../types/api').ID} id */
  function selectOrganization(id) {
    const selected = organizations.find((item) => String(item.id) === String(id));
    if (!selected || !user) return;
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
      if (failure instanceof ApiError && failure.status === 401) return;
      if (failure instanceof Error) setError(failure.message);
      else throw failure;
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
