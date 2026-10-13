import { useSyncExternalStore } from "react";

import type { AccentPreference } from "@/lib/accent";
import { getAccentSnapshot, subscribeAccent } from "@/lib/accentRuntime";

/** The accent color the user picked (Settings → Accent color). */
export function useAccentPreference(): AccentPreference {
  return useSyncExternalStore(subscribeAccent, getAccentSnapshot, getAccentSnapshot);
}
