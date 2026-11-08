/**
 * The launch's first frame draws the native splash again (the same icon, size and page
 * colour, `app.json`'s expo-splash-screen), so when the native splash goes the app takes
 * over without a jump. Then the icon breathes in, grows and fades while the page fades, and
 * the app shows through: the user asked for an icon animation on the first paint
 * (2026-11-07). Reduce Motion: a short fade. Touches pass through while it plays.
 */
import { useEffect, useState } from "react";
import { Image, StyleSheet, useColorScheme } from "react-native";
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { launchSplashHidden, subscribeLaunchSplashHidden } from "@/lib/launchSplash";
import { useReduceMotion } from "@/lib/motion";

const SPLASH_ICON = require("@/assets/images/splash-icon.png");

/** expo-splash-screen's `backgroundColor` and `dark.backgroundColor` in app.json. */
// eslint-disable-next-line no-restricted-syntax -- the native splash's own colours, held equal to app.json by a test
export const SPLASH_BACKGROUND = { light: "#FCFCFC", dark: "#0F0F10" } as const;
/** expo-splash-screen's default `imageWidth`, in points. */
export const SPLASH_ICON_SIZE = 100;

export function LaunchReveal() {
  // The native splash follows the phone's scheme, not Recall's appearance setting.
  const scheme = useColorScheme() === "dark" ? "dark" : "light";
  const reduceMotion = useReduceMotion();
  const [done, setDone] = useState(false);
  const page = useSharedValue(1);
  const icon = useSharedValue(1);
  const scale = useSharedValue(1);

  useEffect(() => {
    const finish = (finished?: boolean) => {
      "worklet";
      if (finished) runOnJS(setDone)(true);
    };
    const reveal = () => {
      if (reduceMotion) {
        page.value = withTiming(0, { duration: 200 }, finish);
        return;
      }
      // Breathe in, then grow while still solid, so the pop reads before the fade.
      scale.value = withSequence(
        withTiming(0.88, { duration: 200, easing: Easing.out(Easing.quad) }),
        withTiming(1.3, { duration: 360, easing: Easing.out(Easing.cubic) }),
      );
      icon.value = withDelay(320, withTiming(0, { duration: 260 }));
      page.value = withDelay(340, withTiming(0, { duration: 320, easing: Easing.out(Easing.quad) }, finish));
    };
    if (launchSplashHidden()) {
      reveal();
      return undefined;
    }
    return subscribeLaunchSplashHidden(reveal);
  }, [icon, page, reduceMotion, scale]);

  const pageStyle = useAnimatedStyle(() => ({ opacity: page.value }));
  const iconStyle = useAnimatedStyle(() => ({ opacity: icon.value, transform: [{ scale: scale.value }] }));

  if (done) return null;
  return (
    <Animated.View
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[StyleSheet.absoluteFill, styles.page, { backgroundColor: SPLASH_BACKGROUND[scheme] }, pageStyle]}
      testID="launch-reveal"
    >
      <Animated.View style={iconStyle}>
        <Image source={SPLASH_ICON} style={styles.icon} resizeMode="contain" fadeDuration={0} />
      </Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  page: { alignItems: "center", justifyContent: "center" },
  icon: { width: SPLASH_ICON_SIZE, height: SPLASH_ICON_SIZE },
});
