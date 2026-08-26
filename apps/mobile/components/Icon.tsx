import type { ComponentProps } from "react";
import { Ionicons } from "@expo/vector-icons";

import { inkIconColor, type IoniconName } from "@/lib/icons";
import { useTheme } from "@/lib/theme";

type Props = {
  /** Ionicons name, rendered as-is. The app standard is **outline** (unfilled):
   *  pass the `-outline` variant (e.g. `"trash-outline"`). Use a filled glyph
   *  only where a filled-vs-outline pair encodes active state (e.g. a pressed
   *  toggle) — not as the default. */
  name: IoniconName;
  /** Pixel size. Defaults to 20 (the settings-row / proposed ladder default). */
  size?: number;
  /** Explicit color. Omit to use the ink default (theme text)
   *  — or set `danger` for the red ink. */
  color?: string;
  /** Use the danger ink color (red) instead of the default ink. */
  danger?: boolean;
  style?: ComponentProps<typeof Ionicons>["style"];
  allowFontScaling?: boolean;
  testID?: string;
};

/**
 * One Ionicons wrapper for the app. Centralizes:
 *  - the **outline** standard — call sites pass `-outline` names and `Icon`
 *   renders them as-is, so the whole app reads as unfilled by default (a
 *   filled glyph is used only where it encodes an active state);
 *  - the ink color default (`inkIconColor`: theme text; red for danger)
 *    instead of a one-off hex.
 *
 * `size` stays a number (not a forced enum): the app uses ~15 distinct icon
 * sizes (9–36) and a 3–4 step ladder would silently change most of them.
 * New code should prefer `Icon`; existing call sites migrate incrementally.
 */
export function Icon({ name, size = 20, color, danger, style, allowFontScaling, testID }: Props) {
  const theme = useTheme();
  return (
    <Ionicons
      name={name}
      size={size}
      color={color ?? inkIconColor(theme, danger)}
      style={style}
      allowFontScaling={allowFontScaling}
      testID={testID}
    />
  );
}
