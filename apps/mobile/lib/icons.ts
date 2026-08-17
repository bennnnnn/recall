import { Ionicons } from "@expo/vector-icons";

import type { Theme } from "@/lib/theme";

export type IoniconName = keyof typeof Ionicons.glyphMap;

/** Prefer the filled glyph so thin outline strokes don't read as gray. */
export function filledIconName(name: IoniconName): IoniconName {
  if (!name.endsWith("-outline")) return name;
  const filled = name.slice(0, -"-outline".length) as IoniconName;
  return Ionicons.glyphMap[filled] ? filled : name;
}

/** True black in light mode; theme text in dark. Danger stays red. */
export function inkIconColor(theme: Theme, danger?: boolean): string {
  if (danger) return theme.danger;
  return theme.isDark ? theme.text : "#000000";
}
