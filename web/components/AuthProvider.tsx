"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  type AuthUser,
} from "@/lib/auth";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  isPro: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const u = await fetchMe();
      setUser(u);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const announce = () =>
    window.dispatchEvent(new CustomEvent("crypto-trends:auth-changed"));

  const login = useCallback(
    async (email: string, password: string) => {
      const u = await apiLogin(email, password);
      setUser(u);
      announce();
    },
    [],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      const u = await apiRegister(email, password);
      setUser(u);
      announce();
    },
    [],
  );

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    announce();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isPro: Boolean(user?.is_pro),
        refresh,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth() called outside <AuthProvider>");
  return ctx;
}
