import { Ionicons } from "@expo/vector-icons";

import type { Theme } from "@/lib/theme";

export type IoniconName = keyof typeof Ionicons.glyphMap;

/** Theme text ink. Danger stays red. */
export function inkIconColor(theme: Theme, danger?: boolean): string {
  if (danger) return theme.danger;
  return theme.text;
}
