/**
 * Theme-aware elevation. Prefer these over ad-hoc `#000` + fixed opacity
 * (which reads muddy on dark surfaces).
 */
import type { ViewStyle } from "react-native";

import { withAlpha, type Theme } from "@/lib/theme";

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

type BoxShadowLevel = "fab" | "toast" | "banner";

/**
 * CSS-style `boxShadow` for surfaces already on that path (FAB, toast).
 * Uses `theme.scrim` so dark mode stays readable.
 */
export function boxShadowElevated(
  theme: Theme,
  level: BoxShadowLevel,
): Pick<ViewStyle, "boxShadow" | "elevation"> {
  if (level === "fab") {
    return {
      boxShadow: `0 2 10 0 ${withAlpha(theme.scrim, theme.isDark ? 0.35 : 0.18)}`,
      elevation: 8,
    };
  }
  if (level === "banner") {
    return {
      boxShadow: `0 4 16 0 ${withAlpha(theme.scrim, theme.isDark ? 0.28 : 0.12)}`,
      elevation: 8,
    };
  }
  return {
    boxShadow: `0 8 24 0 ${withAlpha(theme.scrim, theme.isDark ? 0.55 : 0.45)}`,
    elevation: 16,
  };
}
