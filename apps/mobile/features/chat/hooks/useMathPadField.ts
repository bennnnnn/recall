import { useEffect, type RefObject } from "react";
import { Keyboard, Platform, type TextInputInstance } from "react-native";

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
 * focuses it again, and a phone keyboard that comes up for it anyway is put down. ABC
 * focuses it for typing (`focusForTyping`), which brings the phone's keyboard back.
 */
export function useMathPadField(open: boolean, inputRef: RefObject<TextInputInstance | null>): void {
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
}

/**
 * Focuses the field to type into. On Android `focus()` on a field that already holds focus
 * (with no keyboard, under the pad) does not bring the phone's keyboard up, so the field
 * lets go first; focusing it again shows the keyboard.
 */
export function focusForTyping(input: TextInputInstance | null): void {
  if (!input) return;
  if (Platform.OS === "android" && input.isFocused()) input.blur();
  input.focus();
}
