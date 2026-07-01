import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle } from "react-native-svg";

import { Avatar } from "@/components/Avatar";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  name: string | null;
  uri?: string | null;
  size?: number;
  /** Remaining daily quota 0–100, or null while loading. */
  remainingPct: number | null;
};

const RING_WIDTH = 3;
const RING_GAP = 2;

export function AvatarUsageRing({
  name,
  uri,
  size = 64,
  remainingPct,
}: Props) {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const outer = size + (RING_WIDTH + RING_GAP) * 2;
  const radius = size / 2 + RING_GAP + RING_WIDTH / 2;
  const center = outer / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = remainingPct ?? 100;
  const dashOffset = circumference * (1 - pct / 100);
  const ringColor =
    remainingPct != null && pct <= 10
      ? theme.warning
      : remainingPct != null && pct <= 25
        ? theme.warning
        : theme.primary;
  const label = remainingPct != null ? `${Math.round(pct)}%` : null;
  const badgeFontSize = size >= 56 ? 11 : 9;

  return (
    <View style={[styles.wrap, { width: outer, height: outer }]}>
      <Svg width={outer} height={outer} style={StyleSheet.absoluteFill}>
        <Circle
          cx={center}
          cy={center}
          r={radius}
          stroke={theme.border}
          strokeWidth={RING_WIDTH}
          fill="none"
        />
        {remainingPct != null ? (
          <Circle
            cx={center}
            cy={center}
            r={radius}
            stroke={ringColor}
            strokeWidth={RING_WIDTH}
            fill="none"
            strokeDasharray={`${circumference} ${circumference}`}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            transform={`rotate(-90 ${center} ${center})`}
          />
        ) : null}
      </Svg>
      <Avatar name={name} uri={uri} size={size} />
      {label ? (
        <View style={[styles.badge, { backgroundColor: ringColor }]}>
          <Text style={[styles.badgeText, { fontSize: badgeFontSize, color: theme.onPrimary }]}>
            {label}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(_theme: Theme) {
  return StyleSheet.create({
    wrap: {
      alignItems: "center",
      justifyContent: "center",
    },
    badge: {
      position: "absolute",
      bottom: 0,
      borderRadius: 8,
      paddingHorizontal: 5,
      paddingVertical: 1,
      minWidth: 30,
      alignItems: "center",
    },
    badgeText: {
      fontWeight: "700",
    },
  });
}
