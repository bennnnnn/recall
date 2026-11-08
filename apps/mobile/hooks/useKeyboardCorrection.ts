import { useCallback, useEffect, useRef } from "react";
import { Keyboard, Platform } from "react-native";
import {
  runOnJS,
  runOnUI,
  useAnimatedReaction,
  useSharedValue,
  withTiming,
  type SharedValue,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  keyboardCorrection,
  keyboardEventHeight,
  NO_KEYBOARD_CORRECTION,
  type KeyboardMotion,
} from "@/lib/keyboardInset";
import { useLatestRef } from "@/lib/latestRef";
import { clearScheduledTimeout, scheduleTimeout, type TimeoutHandle } from "@/lib/scheduleTimeout";

/**
 * How long Reanimated's keyboard sits still before it is checked against the real one.
 * Every frame of a show or a hide starts the wait again, so a keyboard Reanimated follows
 * is never checked mid-way.
 */
export const KEYBOARD_CHECK_MS = 150;
/** The composer glides onto the real keyboard rather than jumping. */
const KEYBOARD_CORRECTION_MS = 180;

export type KeyboardCorrection = {
  /** The stale height Reanimated keeps reporting, or `NO_KEYBOARD_CORRECTION`. */
  heldAt: SharedValue<number>;
  /** Where the keyboard really is, while `heldAt` holds. */
  real: SharedValue<number>;
  /**
   * Each height Reanimated reports, on the JS thread; returns the height JS takes for it
   * (the real one while a correction holds). The check waits until the frames stop.
   */
  onFrame: (reported: number) => number;
};

/**
 * Android only: keeps the chat on the keyboard that is really there. Reanimated tracks the
 * keyboard frame by frame, but its Android tracker can lose it (see `keyboardCorrection`);
 * React Native's keyboardDidShow / keyboardDidHide read the window's insets on every
 * layout, whatever closed the keyboard (Back, the hide key, a swipe, a sheet, another
 * app). Once Reanimated has been still for `KEYBOARD_CHECK_MS` and the two disagree, the
 * composer glides to the real keyboard and `onCorrect` hands the thread and React state
 * that height. iOS keeps Reanimated's tracking untouched.
 */
export function useKeyboardCorrection(
  reported: SharedValue<number>,
  onCorrect: (height: number) => void,
): KeyboardCorrection {
  const { bottom: navigationBar } = useSafeAreaInsets();
  const heldAt = useSharedValue(NO_KEYBOARD_CORRECTION);
  const real = useSharedValue(0);
  /** The keyboard React Native last reported, in Reanimated's measure; null before any event. */
  const actual = useRef<number | null>(null);
  /** Bumped by each keyboard event: a correction decided before it no longer applies. */
  const reading = useRef(0);
  /** JS's copy of the correction the UI thread holds. */
  const held = useRef<{ stale: number; target: number } | null>(null);
  const lastFrame = useRef(0);
  /** How Reanimated has moved since the last keyboard event. */
  const motion = useRef<KeyboardMotion>({ rose: false, fell: false });
  const timer = useRef<TimeoutHandle>(null);
  const onCorrectRef = useLatestRef(onCorrect);

  const corrected = useCallback(
    (stale: number, target: number, at: number) => {
      if (at !== reading.current) return;
      held.current = { stale, target };
      onCorrectRef.current(target);
    },
    [onCorrectRef],
  );

  const check = useCallback(() => {
    const target = keyboardCorrection(lastFrame.current, actual.current, motion.current);
    if (target === null || held.current?.stale === lastFrame.current) return;
    runOnUI((stale: number, to: number, at: number) => {
      // Reanimated has moved since that frame: it is tracking the keyboard again.
      if (reported.value !== stale) return;
      heldAt.set(stale);
      real.set(stale);
      real.set(withTiming(to, { duration: KEYBOARD_CORRECTION_MS }));
      runOnJS(corrected)(stale, to, at);
    })(lastFrame.current, target, reading.current);
  }, [corrected, heldAt, real, reported]);

  // Reanimated reports a new height: it is tracking the keyboard again, the correction ends.
  useAnimatedReaction(
    () => reported.value,
    (height) => {
      const stale = heldAt.value;
      if (stale >= 0 && height !== stale) heldAt.set(NO_KEYBOARD_CORRECTION);
    },
  );

  const onFrame = useCallback(
    (height: number) => {
      if (Platform.OS !== "android") return height;
      if (held.current && held.current.stale !== height) {
        held.current = null;
        heldAt.set(NO_KEYBOARD_CORRECTION);
      }
      if (height > lastFrame.current) motion.current.rose = true;
      if (height < lastFrame.current) motion.current.fell = true;
      lastFrame.current = height;
      scheduleTimeout(timer, KEYBOARD_CHECK_MS, check);
      return held.current ? held.current.target : height;
    },
    [check, heldAt],
  );

  useEffect(() => {
    if (Platform.OS !== "android") return;
    const learn = (height: number) => {
      actual.current = height;
      motion.current = { rose: false, fell: false };
      reading.current += 1;
      // A fresh reading: Reanimated leads again until it settles and is checked.
      held.current = null;
      heldAt.set(NO_KEYBOARD_CORRECTION);
      scheduleTimeout(timer, KEYBOARD_CHECK_MS, check);
    };
    const shown = Keyboard.addListener("keyboardDidShow", (event) =>
      learn(keyboardEventHeight(event.endCoordinates.height, navigationBar)),
    );
    const hidden = Keyboard.addListener("keyboardDidHide", () => learn(0));
    return () => {
      shown.remove();
      hidden.remove();
      clearScheduledTimeout(timer);
    };
  }, [check, heldAt, navigationBar]);

  return { heldAt, real, onFrame };
}
