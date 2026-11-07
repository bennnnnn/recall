/**
 * The home's mark above the greeting: Recall's app icon, the R speech bubble the landing and
 * sign-in show, breathing slowly so the empty chat looks awake. Under Reduce Motion it keeps
 * still.
 */
import { useEffect, useMemo } from "react";
import { Image, StyleSheet } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

import { Motion, useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { shadowGlow } from "@/lib/shadow";
import { Theme, useTheme } from "@/lib/theme";

const APP_ICON = require("@/assets/images/icon.png");
/** One breath in or out. */
const BREATH_MS = 2200;
const SIZE = 64;

export function HomeMark() {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const breath = useSharedValue(0);

  useEffect(() => {
    cancelAnimation(breath);
    breath.value = 0;
    if (reduceMotion) return;
    breath.value = withRepeat(withTiming(1, { duration: BREATH_MS, easing: Motion.easing.sway }), -1, true);
  }, [breath, reduceMotion]);

  const animated = useAnimatedStyle(() => ({
    transform: [{ scale: 1 + breath.value * 0.05 }],
  }));

  return (
    <Animated.View style={[s.glow, animated]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Image source={APP_ICON} style={s.icon} />
    </Animated.View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    glow: { alignSelf: "center", borderRadius: Radius.composer, ...shadowGlow(theme, theme.primary) },
    icon: { width: SIZE, height: SIZE, borderRadius: Radius.composer },
  });
}
