import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { api, loginWithDev, loginWithGoogle, setUnauthorizedHandler, type User } from '@/lib/api';
import { clearToken, getOnboarded, getToken, setOnboarded, setToken } from '@/lib/auth';

type AuthContextValue = {
  user: User | null;
  token: string | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithDev: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updateUser: (patch: Partial<User>) => Promise<void>;
  onboarded: boolean;
  completeOnboarding: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [onboarded, setOnboardedState] = useState(false);

  const hydrate = useCallback(async () => {
    const [stored, onb] = await Promise.all([getToken(), getOnboarded()]);
    setOnboardedState(onb);
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
    try {
      const { signOutGoogle } = await import('@/lib/google-auth');
      await signOutGoogle();
    } catch {
      // best-effort — clearing the local token is what matters
    }
    await clearToken();
    setTokenState(null);
    setUser(null);
  }, []);

  // Sign out automatically when any authenticated request returns 401.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      void signOut();
    });
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  const refreshUser = useCallback(async () => {
    if (!token) return;
    const me = await api.me(token);
    setUser(me);
  }, [token]);

  const completeOnboarding = useCallback(async () => {
    await setOnboarded();
    setOnboardedState(true);
  }, []);

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
      onboarded,
      completeOnboarding,
    }),
    [
      user,
      token,
      loading,
      signInWithGoogle,
      signInWithDev,
      signOut,
      refreshUser,
      updateUser,
      onboarded,
      completeOnboarding,
    ],
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
