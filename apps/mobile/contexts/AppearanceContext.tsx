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
import { useAccentPreference } from "@/hooks/useAccentPreference";
import { useResolvedColorScheme } from "@/hooks/useResolvedColorScheme";
import type { AccentPreference } from "@/lib/accent";
import {
  getAccentPreference,
  setAccentPreference as persistAccentPreference,
} from "@/lib/accentPrefs";
import { setAccentSnapshot } from "@/lib/accentRuntime";

export function AppearanceProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    void getAppearancePreference().then(setAppearancePreferenceSnapshot);
    void getAccentPreference().then(setAccentSnapshot);
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

/** The accent color and a setter that applies it now and saves it. */
export function useAccent() {
  const accent = useAccentPreference();
  const setAccent = useCallback(async (next: AccentPreference) => {
    setAccentSnapshot(next);
    await persistAccentPreference(next);
  }, []);
  return { accent, setAccent };
}
