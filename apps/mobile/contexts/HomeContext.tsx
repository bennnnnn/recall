import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AppState, type AppStateStatus } from "react-native";

import { useAuthOptional } from "@/contexts/AuthContext";
import { api, type HomeScreen } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";
import { instantHomePlaceholder } from "@/lib/homeWelcome";

type HomeContextValue = {
  screen: HomeScreen | null;
  loading: boolean;
  hasFetched: boolean;
  refresh: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
};

const HomeContext = createContext<HomeContextValue | null>(null);

export function HomeProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const token = auth?.token;
  const userName = auth?.user?.name;
  const [screen, setScreen] = useState<HomeScreen | null>(null);
  const [hasFetched, setHasFetched] = useState(false);
  const [loading, setLoading] = useState(true);
  const resourceRef = useRef(
    new StaleResourceCache<string, HomeScreen>(CONTEXT_REFRESH_STALE_MS),
  );
  const screenRef = useRef(screen);
  screenRef.current = screen;

  const refresh = useCallback(
    async (opts?: { silent?: boolean; force?: boolean }) => {
      if (!token) {
        setScreen(null);
        setHasFetched(false);
        setLoading(false);
        resourceRef.current.clear();
        return;
      }
      if (
        !opts?.force &&
        screenRef.current &&
        resourceRef.current.isFresh(token)
      ) {
        return;
      }
      if (!opts?.silent) {
        setLoading(true);
      }

      try {
        const data = await resourceRef.current.fetch(
          token,
          async () => {
            try {
              return await api.getHomeScreen(token, getDeviceTimezone());
            } catch {
          // Keep a good screen on silent refresh failure — only fall back when
          // we have nothing to show yet.
              if (screenRef.current) throw new Error("Home refresh failed");
              return instantHomePlaceholder();
            }
          },
          opts,
        );
        setScreen(data);
        setHasFetched(true);
      } catch {
        // Keep the last successful screen.
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [token],
  );

  useEffect(() => {
    if (!token) {
      setScreen(null);
      setHasFetched(false);
      setLoading(false);
      resourceRef.current.clear();
      return;
    }
    // Paint greeting + starters immediately — first sign-in must not sit on a
    // blank ActivityIndicator while /home is in flight.
    setScreen(instantHomePlaceholder());
    void refresh({ force: true });
  }, [refresh, token]);

  // Greeting comes from /home. Don't force a second fetch when the name
  // arrives — join the in-flight login request or wait for the stale window.
  useEffect(() => {
    if (!token || !userName) return;
    void refresh({ silent: true });
  }, [refresh, token, userName]);

  // Focus refresh lives on chat / Learning screens — this provider wraps the
  // whole stack and must not refetch on every route change.
  useEffect(() => {
    if (!token) return;
    const onAppState = (state: AppStateStatus) => {
      if (state === "active") void refresh({ silent: true });
    };
    const sub = AppState.addEventListener("change", onAppState);
    return () => sub.remove();
  }, [refresh, token]);

  const value = useMemo<HomeContextValue>(
    () => ({
      screen,
      loading,
      hasFetched,
      refresh,
    }),
    [screen, loading, hasFetched, refresh],
  );

  return <HomeContext.Provider value={value}>{children}</HomeContext.Provider>;
}

export function useHome() {
  const ctx = useContext(HomeContext);
  if (!ctx) {
    throw new Error("useHome must be used within HomeProvider");
  }
  return ctx;
}
