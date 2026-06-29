import { StyleSheet, View } from "react-native";

import { useTheme } from "@/lib/theme";

type Props = {
  size?: number;
  color?: string;
};

/** Two-line menu icon (ChatGPT-style) — bottom bar shorter. */
export function HamburgerIcon({ size = 22, color }: Props) {
  const theme = useTheme();
  const lineColor = color ?? theme.text;
  const lineHeight = 2.5;
  const gap = 7;
  const shortWidth = Math.round(size * 0.62);

  return (
    <View style={[h.wrap, { width: size, height: lineHeight * 2 + gap, gap }]}>
      <View
        style={[
          h.line,
          { width: size, height: lineHeight, backgroundColor: lineColor },
        ]}
      />
      <View
        style={[
          h.line,
          { width: shortWidth, height: lineHeight, backgroundColor: lineColor },
        ]}
      />
    </View>
  );
}

const h = StyleSheet.create({
  wrap: {
    justifyContent: "center",
  },
  line: {
    borderRadius: 2,
  },
});
