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

import { useAuthOptional } from "@/contexts/AuthContext";
import { api, type ModelInfo } from "@/lib/api";

export const AUTO_MODEL_ID = "auto";

const FALLBACK_MODELS: ModelInfo[] = [
  {
    id: "free-chat",
    label: "DeepSeek Chat",
    provider: "deepseek",
    tier: "fast",
    plan_access: "free",
    description: "",
    available: true,
    input_price_per_m: null,
    output_price_per_m: null,
  },
  {
    id: "smart-chat",
    label: "DeepSeek Reasoner",
    provider: "deepseek",
    tier: "smart",
    plan_access: "pro",
    description: "",
    available: true,
    input_price_per_m: null,
    output_price_per_m: null,
  },
];

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
  const [models, setModels] = useState<ModelInfo[]>(FALLBACK_MODELS);
  const inflightRef = useRef<Promise<void> | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    if (inflightRef.current) {
      await inflightRef.current;
      return;
    }
    const task = (async () => {
      try {
        setModels(await api.listModels(token));
      } catch {
        /* keep fallback list */
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
