import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type SetStateAction,
} from "react";

import {
  api,
  loginWithApple,
  loginWithDev,
  loginWithGoogle,
  logoutSession,
  setTokenRefreshHandler,
  setUnauthorizedHandler,
  type User,
  type AuthResult,
} from "@/lib/api";
import { signInWithAppleCredentials } from "@/lib/apple-auth";
import { signInWithGoogleIdToken } from "@/lib/google-auth";
import { ensureLocale } from "@/lib/i18n";
import {
  clearOnboarded,
  clearToken,
  getOnboarded,
  getRefreshToken,
  getSessionGeneration,
  invalidateSession,
  getToken,
  setOnboarded,
  setTokenPair,
} from "@/lib/auth";
import { cachedUserMatchesToken, clearCachedUser, mergeCachedUser, readCachedUser, writeCachedUser } from "@/lib/cachedUser";
import { clearSignedOutAccount } from "@/lib/signOutCleanup";
import { useBootstrapSync } from "@/hooks/useBootstrapSync";
import { AuthLoadingShell } from "@/components/AuthLoadingShell";

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
  /** Pause 401→signOut (account wipe purges sessions before the DELETE finishes). */
  setIgnoreUnauthorized: (value: boolean) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

/** Token-only bag so chat list cells don't re-render on every user/quota patch. */
type AuthTokenBag = { token: string | null };
const AuthTokenContext = createContext<AuthTokenBag | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [startupFailed, setStartupFailed] = useState(false);
  const [hydrationAttempt, setHydrationAttempt] = useState(0);
  const [onboarded, setOnboardedState] = useState(false);
  const [profileValidated, setProfileValidated] = useState(false);
  const userRef = useRef<User | null>(null);
  const tokenRef = useRef<string | null>(null);
  const mountedRef = useRef(true);
  const localCleanupRef = useRef<Promise<void>>(Promise.resolve());
  const ignoreUnauthorizedRef = useRef(false);
  const updateUserGenRef = useRef(0);

  // Keep event-time identity current even before React paints a signout.
  const setCurrentUser = useCallback((value: SetStateAction<User | null>) => {
    const next = typeof value === "function" ? value(userRef.current) : value;
    userRef.current = next;
    setUser(next);
  }, []);
  const setCurrentToken = useCallback((value: string | null) => {
    tokenRef.current = value;
    setTokenState(value);
  }, []);
  const isCurrent = useCallback((generation: number) =>
    mountedRef.current && generation === getSessionGeneration(), []);

  const setIgnoreUnauthorized = useCallback((value: boolean) => {
    ignoreUnauthorizedRef.current = value;
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const generation = getSessionGeneration();
    let cancelled = false;
    const current = () => !cancelled && isCurrent(generation);
    let hasCachedAccount = false;
    void (async () => {
      try {
        const [stored, onb, cachedUser] = await Promise.all([
          getToken(), getOnboarded(), readCachedUser(),
        ]);
        if (!current()) return;
        setOnboardedState(onb);
        if (!stored) return;
        if (cachedUser && cachedUserMatchesToken(cachedUser, stored)) {
          hasCachedAccount = true;
          setCurrentToken(stored);
          setCurrentUser(mergeCachedUser(cachedUser));
          setLoading(false);
        }
        const revision = updateUserGenRef.current;
        const me = await api.me(stored);
        // /me may have rotated credentials. Never put the startup token back.
        const currentToken = await getToken();
        if (!current() || !currentToken) return;
        setCurrentToken(currentToken);
        if (revision === updateUserGenRef.current) {
          setCurrentUser(me);
          setProfileValidated(true);
          void writeCachedUser(me);
        }
      } catch {
        // Offline launches retain a cached account. Without one, keep a
        // recoverable startup screen: read/network failures are not logout.
        if (current() && !hasCachedAccount) setStartupFailed(true);
      } finally {
        if (current()) setLoading(false);
      }
    })();
    return () => { cancelled = true; mountedRef.current = false; };
  }, [hydrationAttempt, isCurrent, setCurrentToken, setCurrentUser]);

  const retryStartup = useCallback(() => {
    setStartupFailed(false);
    setLoading(true);
    setHydrationAttempt((attempt) => attempt + 1);
  }, []);

  const signIn = useCallback(async (login: (current: () => boolean) => Promise<AuthResult | null>) => {
    const generation = invalidateSession();
    ignoreUnauthorizedRef.current = false;
    await localCleanupRef.current.catch(() => {});
    if (!isCurrent(generation)) return;
    const result = await login(() => isCurrent(generation));
    if (!result || !isCurrent(generation)) return;
    // A crash between the credential write and cache write must not pair a
    // newly signed-in account's token with the previous account's display.
    await clearCachedUser();
    if (!isCurrent(generation)) return;
    const saved = await setTokenPair(result.access_token, result.refresh_token, generation);
    if (!saved || !isCurrent(generation)) return;
    setCurrentToken(result.access_token);
    setCurrentUser(result.user);
    setProfileValidated(true);
    setLoading(false);
    void writeCachedUser(result.user);
  }, [isCurrent, setCurrentToken, setCurrentUser]);

  const signInWithGoogle = useCallback(() => signIn(async (current) => {
    const idToken = await signInWithGoogleIdToken();
    return current() ? loginWithGoogle(idToken) : null;
  }), [signIn]);
  const signInWithApple = useCallback(() => signIn(async (current) => {
    const { idToken, name } = await signInWithAppleCredentials();
    return current() ? loginWithApple(idToken, name) : null;
  }), [signIn]);
  const signInWithDev = useCallback(() => signIn(() => loginWithDev()), [signIn]);

  const signOut = useCallback(() => {
    const userId = userRef.current?.id;
    const accessToken = tokenRef.current;
    const refreshToken = getRefreshToken().catch(() => null);
    // clearToken invalidates the shared session synchronously before its disk
    // write, fencing refreshes, startup requests and pending login attempts.
    const clearCredentials = clearToken();
    setCurrentToken(null);
    setCurrentUser(null);
    setProfileValidated(false);
    setOnboardedState(false);
    setLoading(false);
    setStartupFailed(false);
    ignoreUnauthorizedRef.current = false;
    const cleanup = Promise.allSettled([
      clearCredentials,
      clearCachedUser(),
      clearOnboarded(),
      localCleanupRef.current.catch(() => {}),
      clearSignedOutAccount(userId),
    ]).then((results) => {
      // Even a credential-store failure must wait for every local cleanup;
      // otherwise a new login can race a still-running old-account deletion.
      const credentials = results[0];
      if (credentials.status === "rejected") throw credentials.reason;
    });
    localCleanupRef.current = cleanup;
    if (accessToken) {
      void refreshToken.then((refresh) => logoutSession(accessToken, refresh)).catch(() => {});
    }
    return cleanup;
  }, [setCurrentToken, setCurrentUser]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (ignoreUnauthorizedRef.current) return;
      void signOut().catch(() => {
        console.warn("[auth] could not clear saved credentials");
      });
    });
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  useEffect(() => {
    setTokenRefreshHandler((accessToken, refreshedUser) => {
      if (!mountedRef.current) return;
      // The transport only emits after a current-generation secure write.
      // Ignore an impossible identity mismatch rather than merge accounts.
      if (userRef.current && refreshedUser && userRef.current.id !== refreshedUser.id) return;
      setCurrentToken(accessToken);
      if (refreshedUser) {
        setProfileValidated(true);
        setCurrentUser((previous) => previous ? { ...previous, ...refreshedUser } : refreshedUser);
      }
    });
    return () => setTokenRefreshHandler(null);
  }, [setCurrentToken, setCurrentUser]);

  useEffect(() => {
    if (user?.locale) void ensureLocale(user.locale);
  }, [user?.locale]);

  // Cached display fields intentionally omit preferences. Running bootstrap
  // on those defaults would unregister push and overwrite local reminders.
  useBootstrapSync({
    token: profileValidated ? token : null,
    user: profileValidated ? user : null,
    setUser: setCurrentUser,
  });

  // Capturing the render's generation also fences callbacks retained by a
  // dismissed screen, including a fast account A → B → A transition.
  const sessionGeneration = getSessionGeneration();
  const refreshUser = useCallback(async () => {
    if (!token || !isCurrent(sessionGeneration)) return;
    const revision = updateUserGenRef.current;
    const me = await api.me(token);
    if (!isCurrent(sessionGeneration) || revision !== updateUserGenRef.current) return;
    setCurrentUser(me);
    setProfileValidated(true);
    void writeCachedUser(me);
  }, [token, sessionGeneration, isCurrent, setCurrentUser]);

  const completeOnboarding = useCallback(async () => {
    if (!isCurrent(sessionGeneration)) return;
    await setOnboarded();
    if (isCurrent(sessionGeneration)) setOnboardedState(true);
  }, [sessionGeneration, isCurrent]);

  const updateUser = useCallback(async (patch: Partial<User>) => {
    if (!token || !isCurrent(sessionGeneration)) return;
    const revision = ++updateUserGenRef.current;
    const snapshot = userRef.current;
    const snapshotValidated = profileValidated;
    setCurrentUser((previous) => previous ? { ...previous, ...patch } : previous);
    try {
      const updated = await api.updateMe(token, patch);
      if (!isCurrent(sessionGeneration) || revision !== updateUserGenRef.current) return;
      setCurrentUser(updated);
      setProfileValidated(true);
      void writeCachedUser(updated);
    } catch {
      if (!isCurrent(sessionGeneration) || revision !== updateUserGenRef.current) return;
      setCurrentUser(snapshot);
      setProfileValidated(snapshotValidated);
      throw new Error("update failed");
    }
  }, [token, sessionGeneration, profileValidated, isCurrent, setCurrentUser]);

  const mergeUser = useCallback((patch: Partial<User>) => {
    if (!isCurrent(sessionGeneration)) return;
    ++updateUserGenRef.current;
    setCurrentUser((previous) => previous ? { ...previous, ...patch } : previous);
  }, [sessionGeneration, isCurrent, setCurrentUser]);

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
      setIgnoreUnauthorized,
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
      setIgnoreUnauthorized,
    ],
  );

  const tokenBag = useMemo(() => ({ token }), [token]);

  return (
    <AuthTokenContext.Provider value={tokenBag}>
      <AuthContext.Provider value={value}>
        {loading || startupFailed
          ? <AuthLoadingShell failed={startupFailed} onRetry={retryStartup} />
          : children}
      </AuthContext.Provider>
    </AuthTokenContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

/** Prefer this in FlashList / message rows that only need the bearer token. */
export function useAuthToken(): string | null {
  const bag = useContext(AuthTokenContext);
  if (!bag) {
    throw new Error("useAuthToken must be used within AuthProvider");
  }
  return bag.token;
}

export function useAuthOptional() {
  return useContext(AuthContext);
}
