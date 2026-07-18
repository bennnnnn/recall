/**
 * Theme-aware elevation. Prefer these over ad-hoc `#000` + fixed opacity
 * (which reads muddy on dark surfaces).
 *
 * Uses classic shadow* props only — no import of `withAlpha` from theme
 * (that created a Metro init cycle where ActionBanner crashed with
 * "Property 'withAlpha' doesn't exist").
 */
import type { ViewStyle } from "react-native";

import type { Theme } from "@/lib/theme";

/** Soft raised surface — quota nudge, light cards. */
export function shadowRaised(theme: Theme): ViewStyle {
  return {
    shadowColor: "#000",
    shadowOpacity: theme.isDark ? 0.4 : 0.08,
    shadowRadius: theme.isDark ? 8 : 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  };
}

/** Floating menu / popover panel. */
export function shadowOverlay(theme: Theme): ViewStyle {
  return {
    shadowColor: "#000",
    shadowOpacity: theme.isDark ? 0.55 : 0.28,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 },
    elevation: 20,
  };
}

type ElevatedLevel = "fab" | "toast" | "banner";

/** Stronger float — FAB, toast banner, inline error. */
export function shadowElevated(theme: Theme, level: ElevatedLevel): ViewStyle {
  if (level === "fab") {
    return {
      shadowColor: "#000",
      shadowOpacity: theme.isDark ? 0.35 : 0.18,
      shadowRadius: 10,
      shadowOffset: { width: 0, height: 2 },
      elevation: 8,
    };
  }
  if (level === "banner") {
    return {
      shadowColor: "#000",
      shadowOpacity: theme.isDark ? 0.28 : 0.12,
      shadowRadius: 16,
      shadowOffset: { width: 0, height: 4 },
      elevation: 8,
    };
  }
  return {
    shadowColor: "#000",
    shadowOpacity: theme.isDark ? 0.55 : 0.45,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
    elevation: 16,
  };
}
