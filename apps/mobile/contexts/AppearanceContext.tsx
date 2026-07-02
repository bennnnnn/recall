import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useColorScheme as useSystemColorScheme } from "react-native";

import {
  AppearanceContext,
  type AppearanceContextValue,
} from "@/lib/appearanceContext";
import {
  resolveColorScheme,
  type AppearancePreference,
} from "@/lib/appearance";
import {
  getAppearancePreference,
  setAppearancePreference as persistAppearancePreference,
} from "@/lib/appearancePrefs";

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const systemScheme = useSystemColorScheme();
  const [preference, setPreferenceState] = useState<AppearancePreference>("system");

  useEffect(() => {
    void getAppearancePreference().then(setPreferenceState);
  }, []);

  const setPreference = useCallback(async (next: AppearancePreference) => {
    setPreferenceState(next);
    await persistAppearancePreference(next);
  }, []);

  const colorScheme = resolveColorScheme(systemScheme, preference);

  const value = useMemo(
    () => ({ preference, setPreference, colorScheme }),
    [preference, setPreference, colorScheme],
  );

  return (
    <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>
  );
}

export function useAppearance(): AppearanceContextValue {
  const ctx = useContext(AppearanceContext);
  if (!ctx) {
    throw new Error("useAppearance must be used within AppearanceProvider");
  }
  return ctx;
}
