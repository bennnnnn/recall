import { useState } from "react";
import {
  runOnJS,
  useAnimatedKeyboard,
  useAnimatedReaction,
  useAnimatedStyle,
  useDerivedValue,
  useSharedValue,
} from "react-native-reanimated";

import { keyboardLiftAbove, settledKeyboardHeight } from "@/lib/keyboardInset";

type Options = {
  /** Bottom padding when the keyboard is hidden (safe area aware). */
  idleBottomPad: number;
};

/**
 * Tracks the OS keyboard for the chat screen. Everything that moves with the
 * keyboard (the composer, the list's bottom space, the chrome above the
 * composer) follows it frame by frame on the UI thread. React state takes the
 * height only once the keyboard has finished opening or closing, so a show or
 * a hide renders the screen once instead of on every step of the curve.
 */
export function useKeyboardInset({ idleBottomPad }: Options) {
  const keyboard = useAnimatedKeyboard();
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const committedHeight = useSharedValue(0);

  useAnimatedReaction(
    () => settledKeyboardHeight(keyboard.state.value, keyboard.height.value),
    (settled) => {
      if (settled === null || settled === committedHeight.value) return;
      committedHeight.value = settled;
      runOnJS(setKeyboardHeight)(settled);
    },
  );

  /** How far the keyboard has lifted the composer above its resting place, this frame. */
  const keyboardLift = useDerivedValue(
    () => keyboardLiftAbove(keyboard.height.value, idleBottomPad),
    [idleBottomPad],
  );

  const composerAnimatedStyle = useAnimatedStyle(() => {
    const open = keyboard.height.value > 0;
    return {
      bottom: Math.max(0, keyboard.height.value),
      paddingBottom: open ? 0 : idleBottomPad,
    };
  }, [idleBottomPad]);

  return { keyboardHeight, keyboardLift, composerAnimatedStyle };
}
