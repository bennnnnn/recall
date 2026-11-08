import { useCallback, useEffect, useRef, type RefObject } from "react";
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
/**
 * A frame this soon after a keyboard event is the tail of the move the event cut short (it
 * was on its way to JS), not a move toward a keyboard whose event has not come: it does not
 * count as `motion`, so a hide that stops part of the way after it is still corrected.
 */
export const KEYBOARD_EVENT_TAIL_MS = 100;

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
 * layout, whatever moved the keyboard (Back, the hide key, a swipe, a sheet's own field,
 * another app). Once Reanimated has been still for `KEYBOARD_CHECK_MS` and the two
 * disagree, the composer glides to the real keyboard and `onCorrect` hands the thread and
 * React state that height. A correction holds until Reanimated reports a new height (it is
 * tracking again: the UI thread lets go in the same frame) or a later reading agrees with
 * Reanimated (the composer glides back onto Reanimated's height, and React takes it). iOS
 * keeps Reanimated's tracking untouched.
 */
export function useKeyboardCorrection(
  reported: SharedValue<number>,
  onCorrect: (height: number) => void,
): KeyboardCorrection {
  const { bottom: navigationBar } = useSafeAreaInsets();
  const navigationBarRef = useLatestRef(navigationBar);
  const heldAt = useSharedValue(NO_KEYBOARD_CORRECTION);
  const real = useSharedValue(0);
  /**
   * React Native's last keyboard event, as it measures it (above the navigation bar, 0 for a
   * hide), and when it came; null before any. It is measured against the bar at check time,
   * so a bar that changes re-measures it.
   */
  const lastEvent = useRef<KeyboardReading | null>(null);
  /** JS's copy of the correction the UI thread holds. */
  const held = useRef<{ stale: number; target: number } | null>(null);
  const lastFrame = useRef(0);
  /** How Reanimated has moved since the last keyboard event. */
  const motion = useRef<KeyboardMotion>({ rose: false, fell: false });
  const timer = useRef<TimeoutHandle>(null);
  const onCorrectRef = useLatestRef(onCorrect);

  /** The UI thread moved the composer to `target`: JS mirrors it, and React takes the height. */
  const corrected = useCallback(
    (stale: number, target: number) => {
      held.current = target === stale ? null : { stale, target };
      onCorrectRef.current(target);
    },
    [onCorrectRef],
  );

  const check = useCallback(() => {
    const stale = lastFrame.current;
    const holding = held.current;
    const event = lastEvent.current;
    const actual = event === null ? null : keyboardEventHeight(event.height, navigationBarRef.current);
    // The real keyboard; or, once a held correction agrees with Reanimated again, Reanimated's height.
    const target = keyboardCorrection(stale, actual, motion.current) ?? (holding ? stale : null);
    if (target === null) return;
    if (holding !== null && holding.stale === stale && holding.target === target) return;
    runOnUI((from: number, to: number) => {
      // Reanimated has moved since that frame: it is tracking the keyboard again.
      if (reported.value !== from) return;
      // A new correction starts where the composer is drawn (Reanimated's height); a held one
      // glides on from wherever it is.
      if (heldAt.value !== from) real.set(from);
      heldAt.set(from);
      real.set(
        withTiming(to, { duration: KEYBOARD_CORRECTION_MS }, (finished) => {
          // Back on Reanimated's height: nothing is left to hold.
          if (finished && to === from && heldAt.value === from) heldAt.set(NO_KEYBOARD_CORRECTION);
        }),
      );
      runOnJS(corrected)(from, to);
    })(stale, target);
  }, [corrected, heldAt, navigationBarRef, real, reported]);

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
      const tail = lastEvent.current !== null && Date.now() - lastEvent.current.at < KEYBOARD_EVENT_TAIL_MS;
      if (!tail && height > lastFrame.current) motion.current.rose = true;
      if (!tail && height < lastFrame.current) motion.current.fell = true;
      lastFrame.current = height;
      scheduleTimeout(timer, KEYBOARD_CHECK_MS, check);
      return held.current ? held.current.target : height;
    },
    [check, heldAt],
  );

  const scheduleCheck = useCallback(() => scheduleTimeout(timer, KEYBOARD_CHECK_MS, check), [check]);
  // A reading is checked once Reanimated is still. A correction it ends glides back then;
  // letting go at once could reach the UI thread before Reanimated's first frame does and
  // flash the stale height.
  const onReading = useCallback(() => {
    motion.current = { rose: false, fell: false };
    scheduleCheck();
  }, [scheduleCheck]);
  useKeyboardReadings(lastEvent, navigationBar, onReading, scheduleCheck);
  useEffect(() => () => clearScheduledTimeout(timer), []);

  return { heldAt, real, onFrame };
}

/** React Native's keyboard event as it measured it (above the navigation bar, 0 for a hide), and when it came. */
type KeyboardReading = { height: number; at: number };

/**
 * React Native's keyboard events, Android only: each is kept in `lastEvent`, then `onReading`
 * runs. A new navigation bar re-measures the last one (it is measured against the bar when
 * checked), so `onRemeasure` runs.
 */
function useKeyboardReadings(
  lastEvent: RefObject<KeyboardReading | null>,
  navigationBar: number,
  onReading: () => void,
  onRemeasure: () => void,
): void {
  useEffect(() => {
    if (Platform.OS !== "android") return;
    const learn = (height: number) => {
      lastEvent.current = { height, at: Date.now() };
      onReading();
    };
    const shown = Keyboard.addListener("keyboardDidShow", (event) => learn(event.endCoordinates.height));
    const hidden = Keyboard.addListener("keyboardDidHide", () => learn(0));
    return () => {
      shown.remove();
      hidden.remove();
    };
  }, [lastEvent, onReading]);

  useEffect(() => {
    if (Platform.OS !== "android" || lastEvent.current === null) return;
    onRemeasure();
  }, [lastEvent, navigationBar, onRemeasure]);
}
