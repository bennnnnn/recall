import { useCallback, useEffect, useState, type ReactNode } from "react";

import {
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
import { useResolvedColorScheme } from "@/hooks/useResolvedColorScheme";

export function AppearanceProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    void getAppearancePreference().then(setAppearancePreferenceSnapshot);
  }, []);

  return children;
}

export function useAppearance() {
  const colorScheme = useResolvedColorScheme();
  const [preference, setPreferenceState] = useState(getAppearancePreferenceSnapshot);

  useEffect(() => {
    return subscribeAppearancePreference(() => {
      setPreferenceState(getAppearancePreferenceSnapshot());
    });
  }, []);

  const setPreference = useCallback(async (next: AppearancePreference) => {
    setAppearancePreferenceSnapshot(next);
    setPreferenceState(next);
    await persistAppearancePreference(next);
  }, []);

  return { preference, setPreference, colorScheme };
}
