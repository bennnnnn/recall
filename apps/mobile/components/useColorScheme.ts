import { useSyncExternalStore } from "react";
import { useColorScheme as useSystemColorScheme } from "react-native";

import { resolveColorScheme } from "@/lib/appearance";
import {
  getAppearancePreferenceSnapshot,
  subscribeAppearancePreference,
} from "@/lib/appearanceRuntime";

export const useColorScheme = (): "light" | "dark" => {
  const systemScheme = useSystemColorScheme();
  const preference = useSyncExternalStore(
    subscribeAppearancePreference,
    getAppearancePreferenceSnapshot,
    getAppearancePreferenceSnapshot,
  );

  return resolveColorScheme(systemScheme, preference);
};
