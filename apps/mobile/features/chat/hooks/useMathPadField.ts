import { useCallback, useEffect, useMemo, type RefObject } from "react";
import { AccessibilityInfo, Keyboard, Platform, type TextInputInstance } from "react-native";

import { useLatestRef } from "@/lib/latestRef";
import { symbolA11yLabel, type MathKeyboardSymbol } from "@/lib/math/keyboardCatalog";

/** The composer field's side of the maths pad. */
export type MathPadField = {
  /** The pad's insert: `insertSymbol`, announced on Android. */
  insert: (spec: MathKeyboardSymbol) => void;
  /** After ABC: focus the field to type into, unless the pad is back up by then. */
  focusForTyping: () => void;
  /** Focus the field a frame from now, unless the pad holds it then (Android). */
  focusSoon: () => void;
};

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
 * focuses it again (`focusSoon`), and a phone keyboard that comes up for it anyway is put
 * down. ABC focuses it for typing (`focusForTyping`), which brings the phone's keyboard
 * back. TalkBack reads the new text of a focused field only, so each key the pad types is
 * announced instead.
 *
 * A queued focus looks at the pad when it lands, not when it was asked for: a pad opened
 * again in between keeps the field.
 */
export function useMathPadField(
  open: boolean,
  inputRef: RefObject<TextInputInstance | null>,
  insertSymbol: (spec: MathKeyboardSymbol) => void,
): MathPadField {
  const openRef = useLatestRef(open);

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

  const insert = useCallback(
    (spec: MathKeyboardSymbol) => {
      insertSymbol(spec);
      if (Platform.OS === "android") AccessibilityInfo.announceForAccessibility(symbolA11yLabel(spec));
    },
    [insertSymbol],
  );

  // On Android the focus waits a frame more, so it lands after `showSoftInputOnFocus` is back
  // on and can ask for the keyboard; and a field React Native still counts as focused lets go
  // first, since `focus()` on it sends nothing to the native field (TextInputState.focusTextInput).
  const focusForTyping = useCallback(() => {
    requestAnimationFrame(() => {
      const input = inputRef.current;
      if (!input || openRef.current) return;
      if (Platform.OS !== "android") {
        input.focus();
        return;
      }
      if (input.isFocused()) input.blur();
      requestAnimationFrame(() => {
        if (!openRef.current) input.focus();
      });
    });
  }, [inputRef, openRef]);

  const focusSoon = useCallback(() => {
    requestAnimationFrame(() => {
      if (openRef.current && Platform.OS === "android") return;
      inputRef.current?.focus();
    });
  }, [inputRef, openRef]);

  return useMemo(() => ({ insert, focusForTyping, focusSoon }), [insert, focusForTyping, focusSoon]);
}
