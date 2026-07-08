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
import { api, type ModelInfo } from "@/lib/api";
import { MODEL_CATALOG_FALLBACK } from "@/lib/modelCatalogFallback";
import { shouldRefreshModels } from "@/lib/modelRefresh";

export const AUTO_MODEL_ID = "auto";

const MODEL_REFRESH_TTL_MS = 5 * 60 * 1000;

export function defaultModelPreferences(
  models: ModelInfo[],
  isPro: boolean,
): string[] {
  const ids = models
    .filter((m) => m.available && (isPro || m.plan_access === "free"))
    .map((m) => m.id);
  return [AUTO_MODEL_ID, ...ids];
}

export function buildModelPreferences(
  auto: boolean,
  modelIds: Iterable<string>,
): string[] {
  const ids = [...modelIds];
  return auto ? [AUTO_MODEL_ID, ...ids] : ids;
}

type ModelsContextValue = {
  models: ModelInfo[];
  loading: boolean;
  refresh: () => Promise<void>;
  labelFor: (id: string | null | undefined) => string;
  isPro: boolean;
  autoEnabled: boolean;
  modelEnabledSet: Set<string>;
  enabledSet: Set<string>;
  preferences: string[];
  AUTO_MODEL_ID: string;
};

const ModelsContext = createContext<ModelsContextValue | null>(null);

export function ModelsProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const token = auth?.token;
  const user = auth?.user;
  const [models, setModels] = useState<ModelInfo[]>(MODEL_CATALOG_FALLBACK);
  const [loading, setLoading] = useState(false);
  const inflightRef = useRef<Promise<void> | null>(null);
  const lastFetchedAtRef = useRef<number>(0);

  const refresh = useCallback(async () => {
    if (!token) return;
    if (inflightRef.current) {
      await inflightRef.current;
      return;
    }
    setLoading(true);
    const task = (async () => {
      try {
        const fetched = await api.listModels(token);
        if (fetched.length > 0) {
          setModels(fetched);
        }
        lastFetchedAtRef.current = Date.now();
      } catch {
        /* keep last list (fallback or prior fetch) */
      } finally {
        setLoading(false);
      }
    })();
    inflightRef.current = task;
    try {
      await task;
    } finally {
      inflightRef.current = null;
    }
  }, [token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!token) return;
    const onAppState = (state: AppStateStatus) => {
      if (
        state === "active" &&
        shouldRefreshModels(lastFetchedAtRef.current, Date.now(), MODEL_REFRESH_TTL_MS)
      ) {
        void refresh();
      }
    };
    const sub = AppState.addEventListener("change", onAppState);
    return () => sub.remove();
  }, [refresh, token]);

  const isPro = user?.plan === "pro";

  const preferences = useMemo(
    () => user?.enabled_models ?? defaultModelPreferences(models, isPro),
    [user?.enabled_models, models, isPro],
  );

  const autoEnabled = preferences.includes(AUTO_MODEL_ID);

  const modelEnabledSet = useMemo(() => {
    return new Set(preferences.filter((id) => id !== AUTO_MODEL_ID));
  }, [preferences]);

  const labelFor = useCallback(
    (id: string | null | undefined) => {
      if (!id) return "";
      return models.find((model) => model.id === id)?.label ?? id;
    },
    [models],
  );

  const value = useMemo(
    () => ({
      models,
      loading,
      refresh,
      labelFor,
      isPro,
      autoEnabled,
      modelEnabledSet,
      enabledSet: modelEnabledSet,
      preferences,
      AUTO_MODEL_ID,
    }),
    [
      models,
      loading,
      refresh,
      labelFor,
      isPro,
      autoEnabled,
      modelEnabledSet,
      preferences,
    ],
  );

  return (
    <ModelsContext.Provider value={value}>{children}</ModelsContext.Provider>
  );
}

export function useModelsContext() {
  const ctx = useContext(ModelsContext);
  if (!ctx) {
    throw new Error("useModelsContext must be used within ModelsProvider");
  }
  return ctx;
}

export function useModelsOptional() {
  return useContext(ModelsContext);
}
