import { useState } from "react";
import {
  runOnJS,
  useAnimatedKeyboard,
  useAnimatedReaction,
  useAnimatedStyle,
} from "react-native-reanimated";

type Options = {
  /** Bottom padding when the keyboard is hidden (safe area aware). */
  idleBottomPad: number;
};

/** Tracks the OS keyboard curve for the chat composer and layout metrics. */
export function useKeyboardInset({ idleBottomPad }: Options) {
  const keyboard = useAnimatedKeyboard();
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useAnimatedReaction(
    () => keyboard.height.value,
    (height) => {
      runOnJS(setKeyboardHeight)(Math.max(0, height));
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
