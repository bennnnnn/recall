import { Ionicons } from "@expo/vector-icons";

import type { Theme } from "@/lib/theme";

export type IoniconName = keyof typeof Ionicons.glyphMap;

/** Repeated chrome icon sizes. Prefer these over raw 20/22/24 on `Icon`.
 *  Domain graphics may keep other pixel sizes. */
export const IconSize = {
  sm: 20,
  md: 22,
  lg: 24,
} as const;


/** Theme text ink. Danger stays red. */
export function inkIconColor(theme: Theme, danger?: boolean): string {
  if (danger) return theme.danger;
  return theme.text;
}
