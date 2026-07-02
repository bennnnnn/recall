import { useCallback, useEffect, useSyncExternalStore, type ReactNode } from "react";
import { useColorScheme as useSystemColorScheme } from "react-native";

import {
  resolveColorScheme,
  type AppearancePreference,
} from "@/lib/appearance";
import {
  getAppearancePreferenceSnapshot,
  setAppearancePreferenceSnapshot,
  subscribeAppearancePreference,
} from "@/lib/appearanceRuntime";
import {
  getAppearancePreference,
  setAppearancePreference as persistAppearancePreference,
} from "@/lib/appearancePrefs";

export function AppearanceProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    void getAppearancePreference().then(setAppearancePreferenceSnapshot);
  }, []);

  return children;
}

export function useAppearance() {
  const systemScheme = useSystemColorScheme();
  const preference = useSyncExternalStore(
    subscribeAppearancePreference,
    getAppearancePreferenceSnapshot,
    getAppearancePreferenceSnapshot,
  );
  const colorScheme = resolveColorScheme(systemScheme, preference);

  const setPreference = useCallback(async (next: AppearancePreference) => {
    setAppearancePreferenceSnapshot(next);
    await persistAppearancePreference(next);
  }, []);

  return { preference, setPreference, colorScheme };
}
