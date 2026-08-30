import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import {
  getAccessToken,
  clearTokens,
  refreshAccessToken,
  request,
} from "@/api/client";
import { loginWithDev, loginWithGoogle, logoutSession } from "@/api/auth";
import type { User } from "@/api/types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  error: string | null;
  signInWithGoogle: (idToken: string) => Promise<void>;
  signInWithDev: (email?: string, name?: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let token = getAccessToken();
      if (!token) {
        token = await refreshAccessToken();
      }
      if (!token) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const u = await request<User>("/auth/me", token);
        if (!cancelled) setUser(u);
      } catch {
        if (!cancelled) clearTokens();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signInWithGoogle = useCallback(async (idToken: string) => {
    setError(null);
    try {
      const result = await loginWithGoogle(idToken);
      setUser(result.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Google login failed");
      throw e;
    }
  }, []);

  const signInWithDev = useCallback(async (email?: string, name?: string) => {
    setError(null);
    try {
      const result = await loginWithDev(email, name);
      setUser(result.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dev login failed");
      throw e;
    }
  }, []);

  const signOut = useCallback(async () => {
    const access = getAccessToken();
    if (access) await logoutSession(access);
    clearTokens();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, error, signInWithGoogle, signInWithDev, signOut }),
    [user, loading, error, signInWithGoogle, signInWithDev, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
