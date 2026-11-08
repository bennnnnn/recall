import { useCallback, useEffect, useRef, useState } from "react";
import {
  runOnJS,
  useAnimatedKeyboard,
  useAnimatedReaction,
  useAnimatedStyle,
  useDerivedValue,
} from "react-native-reanimated";

import { useKeyboardCorrection } from "@/hooks/useKeyboardCorrection";
import {
  correctedKeyboardHeight,
  KEYBOARD_CLOSED,
  KEYBOARD_OPEN,
  keyboardLiftAbove,
  settledKeyboardHeight,
  shouldPushKeyboardHeight,
} from "@/lib/keyboardInset";
import { createListenerSet } from "@/lib/listenerSet";
import { clearScheduledTimeout, scheduleTimeout, type TimeoutHandle } from "@/lib/scheduleTimeout";

type Options = {
  /** Bottom padding when the keyboard is hidden (safe area aware). */
  idleBottomPad: number;
};

/** The thread follows the keyboard in steps of about this much travel. */
const KEYBOARD_STEP_PX = 48;
/**
 * A keyboard that has not moved for this long has settled, whatever
 * Reanimated's state says: on Android that state comes from a transition
 * counter that can stick when a listener attaches mid-animation.
 */
const KEYBOARD_STILL_MS = 100;

/** The keyboard's steps as plain events, for the thread to follow while the keyboard moves. */
export type KeyboardSteps = { subscribe: (listener: (height: number) => void) => () => void };

/**
 * Tracks the OS keyboard for the chat screen. Everything drawn against the
 * keyboard (the composer, the list's bottom space, the chrome above the
 * composer) follows it frame by frame on the UI thread. Each frame also
 * reaches JS, where none of them renders: every ~48 pt of travel is a step the
 * thread scrolls along with, and React state takes the height only once the
 * keyboard has settled, so a show or a hide renders the screen once. On
 * Android a keyboard Reanimated lost is put right by `useKeyboardCorrection`:
 * all of it draws against the corrected height, never Reanimated's alone.
 */
export function useKeyboardInset({ idleBottomPad }: Options) {
  const keyboard = useAnimatedKeyboard();
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const [steps] = useState(() => createListenerSet<[number]>());
  const tracked = useRef({ committed: 0, step: 0, frame: 0 });
  const stillTimer = useRef<TimeoutHandle>(null);

  const commit = useCallback((height: number) => {
    clearScheduledTimeout(stillTimer);
    if (tracked.current.committed === height) return;
    tracked.current.committed = height;
    setKeyboardHeight(height);
  }, []);

  /** A correction lands at once: the thread steps to it and React takes it. */
  const settle = useCallback(
    (height: number) => {
      tracked.current.step = height;
      tracked.current.frame = height;
      steps.emit(height);
      commit(height);
    },
    [commit, steps],
  );
  const { heldAt, real, onFrame } = useKeyboardCorrection(keyboard.height, settle);

  const onKeyboardFrame = useCallback(
    (reportedState: number, reported: number) => {
      const height = onFrame(reported);
      // A correction holds: the keyboard is at rest where it really is.
      const state = height === reported ? reportedState : height > 0 ? KEYBOARD_OPEN : KEYBOARD_CLOSED;
      const last = tracked.current;
      if (shouldPushKeyboardHeight(height, last.step, KEYBOARD_STEP_PX, last.frame)) {
        last.step = height;
        steps.emit(height);
      }
      last.frame = height;
      const settled = settledKeyboardHeight(state, height);
      if (settled !== null) commit(settled);
      else scheduleTimeout(stillTimer, KEYBOARD_STILL_MS, () => commit(height));
    },
    [commit, onFrame, steps],
  );

  useAnimatedReaction(
    () => [keyboard.state.value, keyboard.height.value],
    ([state, height]) => {
      runOnJS(onKeyboardFrame)(state, Math.max(0, height));
    },
  );

  useEffect(() => () => clearScheduledTimeout(stillTimer), []);

  /** The keyboard's height this frame: Reanimated's, or the real one while a correction holds. */
  const height = useDerivedValue(() =>
    correctedKeyboardHeight(keyboard.height.value, heldAt.value, real.value),
  );
  /** How far the keyboard has lifted the composer above its resting place, this frame. */
  const keyboardLift = useDerivedValue(
    () => keyboardLiftAbove(height.value, idleBottomPad),
    [idleBottomPad],
  );

  const composerAnimatedStyle = useAnimatedStyle(() => {
    const open = height.value > 0;
    return {
      bottom: height.value,
      paddingBottom: open ? 0 : idleBottomPad,
    };
  }, [idleBottomPad]);

  const keyboardSteps: KeyboardSteps = steps;
  return { keyboardHeight, keyboardLift, keyboardSteps, composerAnimatedStyle };
}
