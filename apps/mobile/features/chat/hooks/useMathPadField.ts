import { useCallback, useEffect, type RefObject } from "react";
import { AccessibilityInfo, Keyboard, Platform, type TextInputInstance } from "react-native";

import { symbolA11yLabel, type MathKeyboardSymbol } from "@/lib/math/keyboardCatalog";

/**
 * The composer field while the maths pad is up: one keyboard at a time, the pad in the
 * phone keyboard's place and the composer right above it.
 *
 * iOS keeps the field focused under an empty input view (`showSoftInputOnFocus` off), so
 * the phone's keyboard stays down and ABC brings it back on the same field.
 *
 * Android has no empty input view: `showSoftInputOnFocus` only keeps a focus call from
 * asking for the keyboard, and a field that holds focus is one the phone's keyboard can
 * still come up for (it did, under the pad, the two stacked over the whole thread). So
 * there the field holds no focus while the pad is up: opening the pad blurs it, nothing
 * focuses it again (`focusUnlessPadIsUp`), and a phone keyboard that comes up for it anyway
 * is put down. ABC focuses it for typing (`focusForTyping`), which brings the phone's
 * keyboard back. TalkBack reads the new text of a focused field only, so each key the pad
 * types is announced instead.
 *
 * Returns the pad's insert, `insertSymbol` with that announcement.
 */
export function useMathPadField(
  open: boolean,
  inputRef: RefObject<TextInputInstance | null>,
  insertSymbol: (spec: MathKeyboardSymbol) => void,
): (spec: MathKeyboardSymbol) => void {
  useEffect(() => {
    if (!open) return;
    if (Platform.OS === "android") {
      const letGo = () => {
        if (inputRef.current?.isFocused()) inputRef.current.blur();
      };
      letGo();
      const sub = Keyboard.addListener("keyboardDidShow", letGo);
      return () => sub.remove();
    }
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open, inputRef]);

  return useCallback(
    (spec: MathKeyboardSymbol) => {
      insertSymbol(spec);
      if (Platform.OS === "android") AccessibilityInfo.announceForAccessibility(symbolA11yLabel(spec));
    },
    [insertSymbol],
  );
}

/** Focuses the field, except on Android under the pad, where focus would bring the phone's keyboard up. */
export function focusUnlessPadIsUp(input: TextInputInstance | null, padOpen: boolean): void {
  if (padOpen && Platform.OS === "android") return;
  input?.focus();
}

/**
 * Focuses the field to type into, once ABC has closed the pad. On Android it waits one more
 * frame, so the focus lands after `showSoftInputOnFocus` is back on and can ask for the
 * keyboard; and a field React Native still counts as focused lets go first, since `focus()`
 * on it sends nothing to the native field (TextInputState.focusTextInput).
 */
export function focusForTyping(input: TextInputInstance | null): void {
  if (!input) return;
  if (Platform.OS !== "android") {
    input.focus();
    return;
  }
  if (input.isFocused()) input.blur();
  requestAnimationFrame(() => input.focus());
}
