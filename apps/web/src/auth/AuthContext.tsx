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
  getRefreshToken,
  clearTokens,
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

  // On mount: if a token is stored, fetch /auth/me to restore the session.
  useEffect(() => {
    let cancelled = false;
    const token = getAccessToken();
    if (!token) {
      setLoading(false);
      return;
    }
    request<User>("/auth/me", token)
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) clearTokens();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
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
    const refresh = getRefreshToken();
    if (access) await logoutSession(access, refresh);
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
