import { Ionicons } from "@expo/vector-icons";

import type { Theme } from "@/lib/theme";

export type IoniconName = keyof typeof Ionicons.glyphMap;

/** True black in light mode; theme text in dark. Danger stays red. */
export function inkIconColor(theme: Theme, danger?: boolean): string {
  if (danger) return theme.danger;
  return theme.isDark ? theme.text : "#000000";
}
