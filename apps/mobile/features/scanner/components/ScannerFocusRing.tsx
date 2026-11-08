import { useEffect, useMemo } from "react";
import { StyleSheet } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withDelay, withTiming } from "react-native-reanimated";

import { Motion, motionMs, useReduceMotion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";

const RING = 64;
/** How long the ring stays before it fades: about as long as a camera takes to focus. */
const HOLD_MS = 700;

/** Where the camera was asked to focus; `id` restarts the ring on a second tap at the same spot. */
export type FocusPoint = { x: number; y: number; id: number };

/** A ring at the tapped point while the camera focuses there. */
export function ScannerFocusRing({ point }: { point: FocusPoint | null }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const opacity = useSharedValue(0);
  const scale = useSharedValue(1);

  useEffect(() => {
    if (!point) return;
    opacity.value = 1;
    opacity.value = withDelay(HOLD_MS, withTiming(0, { duration: motionMs(Motion.duration.short, reduceMotion) }));
    scale.value = reduceMotion ? 1 : 1.25;
    scale.value = withTiming(1, { duration: motionMs(Motion.duration.standard, reduceMotion) });
  }, [opacity, point, reduceMotion, scale]);

  const ringStyle = useAnimatedStyle(() => ({ opacity: opacity.value, transform: [{ scale: scale.value }] }));

  if (!point) return null;
  return (
    <Animated.View
      pointerEvents="none"
      testID="math-scanner-focus-ring"
      style={[s.ring, { left: point.x - RING / 2, top: point.y - RING / 2 }, ringStyle]}
    />
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    ring: {
      position: "absolute",
      width: RING,
      height: RING,
      borderRadius: RING / 2,
      borderWidth: 1.5,
      borderColor: theme.onMedia,
    },
  });
}
