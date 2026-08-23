import { Pressable, StyleSheet, View } from "react-native";
import Svg, { Rect } from "react-native-svg";
import { useTranslation } from "react-i18next";

import { useTheme } from "@/lib/theme";

type Props = {
  disabled?: boolean;
  onPress: () => void;
};

/** ChatGPT voice-mode glyph: four rounded vertical bars. */
export function LiveTalkWaveformIcon({ size = 18, color }: { size?: number; color: string }) {
  const w = 2.2;
  const gap = 1.7;
  const bars = [8, 16, 12, 6];
  const total = bars.length * w + (bars.length - 1) * gap;
  const originX = (24 - total) / 2;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      {bars.map((h, i) => (
        <Rect
          key={i}
          x={originX + i * (w + gap)}
          y={(24 - h) / 2}
          width={w}
          height={h}
          rx={1.1}
          fill={color}
        />
      ))}
    </Svg>
  );
}

export function LiveTalkButton({ disabled, onPress }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Pressable
      style={[styles.hit, disabled && styles.dim]}
      onPress={onPress}
      disabled={disabled}
      hitSlop={6}
      accessibilityRole="button"
      accessibilityLabel={t("chat.live_talk_a11y")}
      testID="live-talk-button"
    >
      <View style={[styles.btn, { backgroundColor: theme.text }]}>
        <LiveTalkWaveformIcon size={18} color={theme.isDark ? theme.bg : "#FFFFFF"} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hit: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  dim: { opacity: 0.55 },
  btn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
});
