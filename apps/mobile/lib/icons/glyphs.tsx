import { StyleSheet, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { useTheme } from "@/lib/theme";

type GlyphProps = {
  /** Defaults to IconSize.sm (20). */
  size?: number;
  color: string;
};

/**
 * Square with a pencil through the corner (Feather `edit` / SF `square.and.pencil`).
 * New chat, memory edit, and the email card all use this drawing.
 */
export function EditIcon({ size = 20, color }: GlyphProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/** Two-line menu mark. The bottom bar is shorter. */
export function MenuIcon({ size = 20, color }: { size?: number; color?: string }) {
  const theme = useTheme();
  const lineColor = color ?? theme.text;
  const lineHeight = 2.5;
  const gap = 7;
  const shortWidth = Math.round(size * 0.62);

  return (
    <View style={[menu.wrap, { width: size, height: lineHeight * 2 + gap, gap }]}>
      <View style={[menu.line, { width: size, height: lineHeight, backgroundColor: lineColor }]} />
      <View
        style={[menu.line, { width: shortWidth, height: lineHeight, backgroundColor: lineColor }]}
      />
    </View>
  );
}

const menu = StyleSheet.create({
  wrap: { justifyContent: "center" },
  line: { borderRadius: 2 },
});
