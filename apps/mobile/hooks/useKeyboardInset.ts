import { useState } from "react";
import {
  runOnJS,
  useAnimatedKeyboard,
  useAnimatedReaction,
  useAnimatedStyle,
} from "react-native-reanimated";

import { shouldPushKeyboardHeight } from "@/lib/keyboardInset";

type Options = {
  /** Bottom padding when the keyboard is hidden (safe area aware). */
  idleBottomPad: number;
};

const KEYBOARD_HEIGHT_THRESHOLD_PX = 4;

/** Tracks the OS keyboard curve for the chat composer and layout metrics. */
export function useKeyboardInset({ idleBottomPad }: Options) {
  const keyboard = useAnimatedKeyboard();
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useAnimatedReaction(
    () => keyboard.height.value,
    (height, previousHeight) => {
      const next = Math.max(0, height);
      const previous = Math.max(0, previousHeight ?? 0);
      if (!shouldPushKeyboardHeight(next, previous, KEYBOARD_HEIGHT_THRESHOLD_PX)) {
        return;
      }
      runOnJS(setKeyboardHeight)(next);
    },
  );

  const composerAnimatedStyle = useAnimatedStyle(() => {
    const open = keyboard.height.value > 0;
    return {
      bottom: Math.max(0, keyboard.height.value),
      paddingBottom: open ? 0 : idleBottomPad,
    };
  }, [idleBottomPad]);

  return { keyboardHeight, composerAnimatedStyle };
}
