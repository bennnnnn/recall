import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import {
  api,
  loginWithDev,
  loginWithGoogle,
  setUnauthorizedHandler,
  type User,
} from "@/lib/api";
import { signInWithGoogleIdToken, signOutGoogle } from "@/lib/google-auth";
import i18n from "@/lib/i18n";
import {
  clearToken,
  getOnboarded,
  getToken,
  setOnboarded,
  setToken,
} from "@/lib/auth";
import { isExpoGo } from "@/lib/expoRuntime";
import { useTheme } from "@/lib/theme";

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

function AuthLoadingShell() {
  const theme = useTheme();
  return (
    <View style={authLoadingStyles.shell}>
      <ActivityIndicator size="large" color={theme.primary} />
    </View>
  );
}

const authLoadingStyles = StyleSheet.create({
  shell: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});

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
      const { cancelAllTodoReminders } = await import("@/lib/todoReminders");
      await cancelAllTodoReminders();
    } catch {
      /* best-effort */
    }
    try {
      await signOutGoogle();
    } catch {
      // best-effort — clearing the local token is what matters
    }
    // Server-side integrations (Gmail, Calendar) stay connected until explicitly disconnected.
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

  // Sync i18n language with user preference (including optimistic locale patches).
  useEffect(() => {
    if (user?.locale) {
      void i18n.changeLanguage(user.locale);
    }
  }, [user?.locale]);

  // Keep server timezone in sync with the device for due-date-aware prompts.
  useEffect(() => {
    if (!token || !user) return;
    import("@/lib/deviceTimezone").then(({ getDeviceTimezone }) => {
      const deviceTz = getDeviceTimezone();
      if (user.timezone !== deviceTz) {
        void api.updateMe(token, { timezone: deviceTz }).then(setUser).catch(() => {});
      }
    });
  }, [token, user?.id, user?.timezone]);

  // Keep server location in sync with device GPS (city/region label).
  useEffect(() => {
    if (!token || !user || isExpoGo()) return;
    void import("@/lib/deviceLocation").then(async ({ getDeviceLocationLabel }) => {
      const label = await getDeviceLocationLabel();
      if (label && user.location !== label) {
        void api.updateMe(token, { location: label }).then(setUser).catch(() => {});
      }
    });
  }, [token, user?.id, user?.location]);

  useEffect(() => {
    if (!token) return;
    let cleanup: (() => void) | undefined;
    void import("@/lib/gmailAutoSync").then(({ attachGmailForegroundSync }) => {
      cleanup = attachGmailForegroundSync(token);
    });
    return () => cleanup?.();
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let cleanup: (() => void) | undefined;
    void import("@/lib/pushNotifications").then(({ attachPushForegroundSync }) => {
      cleanup = attachPushForegroundSync(token);
    });
    return () => cleanup?.();
  }, [token]);

  useEffect(() => {
    if (user?.reminder_lead_minutes == null) return;
    void import("@/lib/reminderPrefs").then(({ syncReminderLeadFromServer }) =>
      syncReminderLeadFromServer(user.reminder_lead_minutes),
    );
  }, [user?.reminder_lead_minutes]);

  useEffect(() => {
    if (!user?.id) return;
    void import("@/lib/purchases").then(({ configurePurchases, isPurchasesConfigured }) => {
      if (!isPurchasesConfigured()) return;
      void configurePurchases(user.id);
    });
  }, [user?.id]);

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
