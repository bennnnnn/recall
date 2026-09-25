import { Ionicons } from "@expo/vector-icons";

import type { Theme } from "@/lib/theme";

export type IoniconName = keyof typeof Ionicons.glyphMap;

/**
 * Icon catalog, next to `theme` (color) and `Type` (fonts).
 *
 * Outline icons from the shared set: `<Icon name="…-outline" />`.
 * Artwork for that set lives in `assets/bold-icons`.
 * Drawings the set does not include are exported below: `EditIcon`, `MenuIcon`.
 */
export { EditIcon, MenuIcon } from "./glyphs";
export { IconSize } from "./sizes";

/** Theme text ink. Danger stays red. */
export function inkIconColor(theme: Theme, danger?: boolean): string {
  if (danger) return theme.danger;
  return theme.text;
}
