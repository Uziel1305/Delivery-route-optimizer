import { createContext, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.get("/users/me");
      setUser(me);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMe();
  }, []);

  async function login(username, password) {
    const { access_token } = await api.post("/auth/login", { username, password });
    setToken(access_token);
    const me = await api.get("/users/me");
    setUser(me);
    return me;
  }

  async function register(payload) {
    await api.post("/auth/register", payload);
    return login(payload.username, payload.password);
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  async function refreshUser() {
    const me = await api.get("/users/me");
    setUser(me);
    return me;
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
