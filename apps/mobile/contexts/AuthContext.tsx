import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { api, loginWithDev, loginWithGoogle, type User } from '@/lib/api';
import { clearToken, getToken, setToken } from '@/lib/auth';
import { config } from '@/lib/config';

type AuthContextValue = {
  user: User | null;
  token: string | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithDev: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updateUser: (patch: Partial<User>) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const hydrate = useCallback(async () => {
    const stored = await getToken();
    if (!stored) {
      setLoading(false);
      return;
    }
    try {
      const me = await api.me(stored);
      setTokenState(stored);
      setUser(me);
    } catch {
      await clearToken();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const signInWithGoogle = useCallback(async () => {
    const { signInWithGoogleIdToken } = await import('@/lib/google-auth');
    const idToken = await signInWithGoogleIdToken();
    const result = await loginWithGoogle(idToken);
    await setToken(result.access_token);
    setTokenState(result.access_token);
    setUser(result.user);
  }, []);

  const signInWithDev = useCallback(async () => {
    const result = await loginWithDev();
    await setToken(result.access_token);
    setTokenState(result.access_token);
    setUser(result.user);
  }, []);

  const signOut = useCallback(async () => {
    await clearToken();
    setTokenState(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!token) return;
    const me = await api.me(token);
    setUser(me);
  }, [token]);

  const updateUser = useCallback(
    async (patch: Partial<User>) => {
      if (!token) return;
      const updated = await api.updateMe(token, patch);
      setUser(updated);
    },
    [token],
  );

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      signInWithGoogle,
      signInWithDev,
      signOut,
      refreshUser,
      updateUser,
    }),
    [user, token, loading, signInWithGoogle, signInWithDev, signOut, refreshUser, updateUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}

export function useAuthOptional() {
  return useContext(AuthContext);
}
