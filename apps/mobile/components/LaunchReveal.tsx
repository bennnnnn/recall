/**
 * The launch's first frame draws the native splash again (the same icon, size and page
 * colour, `app.json`'s expo-splash-screen), so when the native splash goes the app takes
 * over without a jump. Then the icon breathes in, grows and fades while the page fades, and
 * the app shows through: the user asked for an icon animation on the first paint
 * (2026-11-07). Reduce Motion: a short fade. Touches pass through while it plays.
 */
import { useEffect, useState, useSyncExternalStore } from "react";
import { Image, StyleSheet, useColorScheme } from "react-native";
import Animated, {
  Easing,
  ReduceMotion,
  runOnJS,
  type SharedValue,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { launchSplashHidden, subscribeLaunchSplashHidden } from "@/lib/launchSplash";
import { useReduceMotionSetting } from "@/lib/motion";

const SPLASH_ICON = require("@/assets/images/splash-icon.png");

/** expo-splash-screen's `backgroundColor` and `dark.backgroundColor` in app.json. */
// eslint-disable-next-line no-restricted-syntax -- the native splash's own colours, held equal to app.json by a test
export const SPLASH_BACKGROUND = { light: "#FCFCFC", dark: "#0F0F10" } as const;
/** expo-splash-screen's default `imageWidth`, in points. */
export const SPLASH_ICON_SIZE = 100;
/** Reduce Motion's reveal: the page fades out over this long. */
export const REDUCED_FADE_MS = 200;
/**
 * The OS answers Reduce Motion long before the splash goes. If it has not by this long
 * after, the reveal takes the short fade rather than staying over the app.
 */
export const SETTING_WAIT_MS = 250;

/**
 * Once per process: the root error boundary's Try again remounts the layout after the
 * splash went, and the app must not open a second time.
 */
let played = false;

/** Tests: a fresh launch. */
export function resetLaunchRevealForTest(): void {
  played = false;
}

type RevealValues = { page: SharedValue<number>; icon: SharedValue<number>; scale: SharedValue<number> };

/**
 * The short fade opts out of Reanimated's own Reduce Motion handling, which would jump it
 * to its end: a hard cut from splash to app. A fade moves nothing, so it plays as one.
 */
function playReveal(values: RevealValues, reduced: boolean, finish: (finished?: boolean) => void): void {
  const { page, icon, scale } = values;
  if (reduced) {
    page.value = withTiming(0, { duration: REDUCED_FADE_MS, reduceMotion: ReduceMotion.Never }, finish);
    return;
  }
  // Breathe in, then grow while still solid, so the pop reads before the fade.
  scale.value = withSequence(
    withTiming(0.88, { duration: 200, easing: Easing.out(Easing.quad) }),
    withTiming(1.3, { duration: 360, easing: Easing.out(Easing.cubic) }),
  );
  icon.value = withDelay(320, withTiming(0, { duration: 260 }));
  page.value = withDelay(340, withTiming(0, { duration: 320, easing: Easing.out(Easing.quad) }, finish));
}

export function LaunchReveal() {
  // The native splash follows the phone's scheme, not Recall's appearance setting.
  const scheme = useColorScheme() === "dark" ? "dark" : "light";
  // `null` until the OS answers: a guessed `false` would start the full motion.
  const reduceMotion = useReduceMotionSetting();
  const splashGone = useSyncExternalStore(subscribeLaunchSplashHidden, launchSplashHidden);
  const [done, setDone] = useState(() => played);
  const page = useSharedValue(1);
  const icon = useSharedValue(1);
  const scale = useSharedValue(1);

  useEffect(() => {
    if (!splashGone || played) return undefined;
    const finish = (finished?: boolean) => {
      "worklet";
      if (finished) runOnJS(setDone)(true);
    };
    const play = (reduced: boolean) => {
      played = true;
      playReveal({ page, icon, scale }, reduced, finish);
    };
    if (reduceMotion !== null) {
      play(reduceMotion);
      return undefined;
    }
    const wait = setTimeout(() => play(true), SETTING_WAIT_MS);
    return () => clearTimeout(wait);
  }, [icon, page, reduceMotion, scale, splashGone]);

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
