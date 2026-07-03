import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ActivityIndicator, Alert, StyleSheet, View } from "react-native";

import {
  api,
  loginWithApple,
  loginWithDev,
  loginWithGoogle,
  logoutSession,
  setTokenRefreshHandler,
  setUnauthorizedHandler,
  type User,
} from "@/lib/api";
import { signInWithAppleCredentials } from "@/lib/apple-auth";
import { signInWithGoogleIdToken, signOutGoogle } from "@/lib/google-auth";
import i18n from "@/lib/i18n";
import {
  clearToken,
  getOnboarded,
  getRefreshToken,
  getToken,
  setOnboarded,
  setTokenPair,
} from "@/lib/auth";
import { useBootstrapSync } from "@/hooks/useBootstrapSync";
import { useTheme } from "@/lib/theme";

type AuthContextValue = {
  user: User | null;
  token: string | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithApple: () => Promise<void>;
  signInWithDev: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updateUser: (patch: Partial<User>) => Promise<void>;
  mergeUser: (patch: Partial<User>) => void;
  onboarded: boolean;
  completeOnboarding: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function AuthLoadingShell() {
  const theme = useTheme();
  const s = useMemo(
    () =>
      StyleSheet.create({
        shell: {
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: theme.bg,
        },
      }),
    [theme],
  );
  return (
    <View style={s.shell}>
      <ActivityIndicator size="large" color={theme.primary} />
    </View>
  );
}

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
      Alert.alert(i18n.t("login.sign_in_failed"), i18n.t("auth.session_expired"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const signInWithGoogle = useCallback(async () => {
    const idToken = await signInWithGoogleIdToken();
    const result = await loginWithGoogle(idToken);
    await setTokenPair(result.access_token, result.refresh_token);
    setTokenState(result.access_token);
    setUser(result.user);
  }, []);

  const signInWithApple = useCallback(async () => {
    const { idToken, name } = await signInWithAppleCredentials();
    const result = await loginWithApple(idToken, name);
    await setTokenPair(result.access_token, result.refresh_token);
    setTokenState(result.access_token);
    setUser(result.user);
  }, []);

  const signInWithDev = useCallback(async () => {
    const result = await loginWithDev();
    await setTokenPair(result.access_token, result.refresh_token);
    setTokenState(result.access_token);
    setUser(result.user);
  }, []);

  const signOut = useCallback(async () => {
    const userId = user?.id;
    const accessToken = token;
    const refreshToken = await getRefreshToken();
    try {
      const { cancelAllTodoReminders } = await import("@/lib/todoReminders");
      await cancelAllTodoReminders();
    } catch {
      /* best-effort */
    }
    try {
      const { clearReminderLeadPrefs } = await import("@/lib/reminderPrefs");
      await clearReminderLeadPrefs();
    } catch {
      /* best-effort */
    }
    if (userId) {
      try {
        const { clearSeenReminderIds } = await import("@/lib/reminderSeen");
        await clearSeenReminderIds(userId);
      } catch {
        /* best-effort */
      }
    }
    try {
      await signOutGoogle();
    } catch {
      // best-effort — clearing the local token is what matters
    }
    if (accessToken) {
      await logoutSession(accessToken, refreshToken);
    }
    // Server-side integrations (Gmail, Calendar) stay connected until explicitly disconnected.
    await clearToken();
    setTokenState(null);
    setUser(null);
  }, [user?.id, token]);

  // Sign out automatically when any authenticated request returns 401.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      void signOut();
    });
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  // Keep in-memory token in sync when api.ts silently refreshes after a 401.
  useEffect(() => {
    setTokenRefreshHandler((accessToken) => {
      setTokenState(accessToken);
    });
    return () => setTokenRefreshHandler(null);
  }, []);

  // Sync i18n language with user preference (including optimistic locale patches).
  useEffect(() => {
    if (user?.locale) {
      void i18n.changeLanguage(user.locale);
    }
  }, [user?.locale]);

  useBootstrapSync({ token, user, setUser });

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
      let snapshot: User | null = null;
      setUser((current) => {
        snapshot = current;
        return current ? { ...current, ...patch } : current;
      });
      try {
        const updated = await api.updateMe(token, patch);
        setUser(updated);
      } catch {
        setUser(snapshot);
        throw new Error("update failed");
      }
    },
    [token],
  );

  const mergeUser = useCallback((patch: Partial<User>) => {
    setUser((current) => (current ? { ...current, ...patch } : current));
  }, []);

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      signInWithGoogle,
      signInWithApple,
      signInWithDev,
      signOut,
      refreshUser,
      updateUser,
      mergeUser,
      onboarded,
      completeOnboarding,
    }),
    [
      user,
      token,
      loading,
      signInWithGoogle,
      signInWithApple,
      signInWithDev,
      signOut,
      refreshUser,
      updateUser,
      mergeUser,
      onboarded,
      completeOnboarding,
    ],
  );

  return (
    <AuthContext.Provider value={value}>
      {loading ? <AuthLoadingShell /> : children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export function useAuthOptional() {
  return useContext(AuthContext);
}
