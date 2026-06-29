import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AppState, type AppStateStatus } from "react-native";
import { useFocusEffect } from "expo-router";

import { useAuthOptional } from "@/contexts/AuthContext";
import { api, type HomeScreen } from "@/lib/api";
import { loadHomeFallback } from "@/lib/homeFallback";

type HomeContextValue = {
  screen: HomeScreen | null;
  loading: boolean;
  refresh: (opts?: { silent?: boolean }) => Promise<void>;
};

const HomeContext = createContext<HomeContextValue | null>(null);

export function HomeProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const token = auth?.token;
  const [screen, setScreen] = useState<HomeScreen | null>(null);
  const [loading, setLoading] = useState(true);
  const inflightRef = useRef<Promise<void> | null>(null);
  const screenRef = useRef(screen);
  screenRef.current = screen;

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token) {
        setScreen(null);
        setLoading(false);
        return;
      }
      if (inflightRef.current) {
        await inflightRef.current;
        return;
      }
      if (!opts?.silent) {
        setLoading(true);
      }

      const task = (async () => {
        try {
          const data = await api.getHomeScreen(token);
          setScreen(data);
        } catch {
          setScreen(await loadHomeFallback(token));
        } finally {
          if (!opts?.silent) {
            setLoading(false);
          }
        }
      })();

      inflightRef.current = task;
      try {
        await task;
      } finally {
        inflightRef.current = null;
      }
    },
    [token],
  );

  useEffect(() => {
    if (!token) {
      setScreen(null);
      setLoading(false);
      return;
    }
    void refresh();
  }, [refresh, token]);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: screenRef.current !== null });
    }, [refresh]),
  );

  useEffect(() => {
    if (!token) return;
    const onAppState = (state: AppStateStatus) => {
      if (state === "active") void refresh({ silent: true });
    };
    const sub = AppState.addEventListener("change", onAppState);
    return () => sub.remove();
  }, [refresh, token]);

  const value: HomeContextValue = {
    screen,
    loading,
    refresh,
  };

  return <HomeContext.Provider value={value}>{children}</HomeContext.Provider>;
}

export function useHome() {
  const ctx = useContext(HomeContext);
  if (!ctx) {
    throw new Error("useHome must be used within HomeProvider");
  }
  return ctx;
}
