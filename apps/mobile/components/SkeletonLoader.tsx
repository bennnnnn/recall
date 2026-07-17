import { useEffect, useMemo } from "react";
import { StyleSheet, View, type ViewStyle } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { Motion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";

type SkeletonBlockProps = {
  width?: number | `${number}%`;
  height: number;
  borderRadius?: number;
  style?: ViewStyle;
};

/** A single pulsing placeholder rectangle. */
export function SkeletonBlock({
  width = "100%",
  height,
  borderRadius = 6,
  style,
}: SkeletonBlockProps) {
  const theme = useTheme();
  const opacity = useSharedValue(0.5);

  useEffect(() => {
    opacity.value = withRepeat(
      withSequence(
        withTiming(1, {
          duration: Motion.duration.breathe,
          easing: Motion.easing.inOut,
        }),
        withTiming(0.5, {
          duration: Motion.duration.breathe,
          easing: Motion.easing.inOut,
        }),
      ),
      -1,
      false,
    );
  }, [opacity]);

  const animatedStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));

  return (
    <Animated.View
      style={[
        {
          width,
          height,
          borderRadius,
          backgroundColor: theme.border,
        },
        animatedStyle,
        style,
      ]}
    />
  );
}

/** Placeholder for a single list row: a leading circle plus two text lines. */
export function SkeletonRow() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.row}>
      <SkeletonBlock width={36} height={36} borderRadius={18} />
      <View style={s.lines}>
        <SkeletonBlock width="70%" height={14} />
        <SkeletonBlock width="45%" height={12} style={s.secondLine} />
      </View>
    </View>
  );
}

/** Stacks `count` skeleton rows — for History/Search/Todos/Memory first-load states. */
export function SkeletonList({ count = 6 }: { count?: number }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.list}>
      {Array.from({ length: count }, (_, i) => (
        <SkeletonRow key={i} />
      ))}
    </View>
  );
}

const BUBBLE_WIDTHS: { align: "left" | "right"; width: `${number}%` }[] = [
  { align: "left", width: "60%" },
  { align: "right", width: "45%" },
  { align: "left", width: "70%" },
];

/** A few alternating bubble-shaped placeholders — for the chat message list's first load. */
export function SkeletonChatBubbles() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.bubbles}>
      {BUBBLE_WIDTHS.map((bubble, i) => (
        <View
          key={i}
          style={[s.bubbleRow, bubble.align === "right" ? s.bubbleRowRight : null]}
        >
          <SkeletonBlock width={bubble.width} height={16} borderRadius={12} />
        </View>
      ))}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    list: {
      paddingHorizontal: 16,
      paddingVertical: 8,
      gap: 4,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      paddingVertical: 10,
      gap: 12,
    },
    lines: {
      flex: 1,
      gap: 8,
    },
    secondLine: {
      backgroundColor: theme.border,
    },
    bubbles: {
      paddingHorizontal: 16,
      paddingVertical: 12,
      gap: 14,
    },
    bubbleRow: {
      flexDirection: "row",
    },
    bubbleRowRight: {
      justifyContent: "flex-end",
    },
  });
}
