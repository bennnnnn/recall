import type { ComponentProps } from "react";
import { Image, type ImageStyle, type StyleProp } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { boldIcons, type BoldIconName } from "@/assets/bold-icons";
import { IconSize, inkIconColor, type IoniconName } from "@/lib/icons";
import { useTheme } from "@/lib/theme";

type Props = {
  /** Ionicons name, rendered as-is. The app standard is **outline** (unfilled):
   *  pass the `-outline` variant (e.g. `"trash-outline"`). Use a filled glyph
   *  only where a filled-vs-outline pair encodes active state (e.g. a pressed
   *  toggle) — not as the default. */
  name: IoniconName;
  /** Pixel size. Defaults to `IconSize.sm` (settings-row / proposed ladder). */
  size?: number;
  /** Explicit color. Omit to use the ink default (theme text)
   *  — or set `danger` for the red ink. */
  color?: string;
  /** Use the danger ink color (red) instead of the default ink. */
  danger?: boolean;
  style?: ComponentProps<typeof Ionicons>["style"];
  testID?: string;
};

/**
 * One icon treatment for the app: a single solid glyph at the same weight as
 * the menu artwork. The stroke is thickened once (not stacked copies).
 */
export function Icon({ name, size = IconSize.sm, color, danger, style, testID }: Props) {
  const theme = useTheme();
  const ink = color ?? inkIconColor(theme, danger);
  const source = boldIcons[name as BoldIconName];
  if (!source) {
    return <Ionicons name={name} size={size} color={ink} style={style} testID={testID} />;
  }
  return (
    <Image
      source={source}
      resizeMode="contain"
      accessible={false}
      testID={testID}
      style={[{ width: size, height: size, tintColor: ink }, style as StyleProp<ImageStyle>]}
      {...({ name, size, color: ink } as Record<string, unknown>)}
    />
  );
}
