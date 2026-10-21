/**
 * Keyboard geometry for the chat screen. Both functions run inside Reanimated
 * worklets, so they carry the 'worklet' directive and read nothing but their
 * arguments; under Jest the directive is inert and they are plain functions.
 */

/**
 * The height to hand to React state, or null while the keyboard is still
 * moving. React only needs where the keyboard comes to rest: the composer,
 * the list's bottom space and the chrome above the composer follow every
 * frame on the UI thread. `state` is Reanimated's `KeyboardState`, which
 * reports OPEN and CLOSED once the native show or hide has finished.
 */
export function settledKeyboardHeight(state: number, height: number): number | null {
  "worklet";
  // KeyboardState.OPEN and KeyboardState.CLOSED. A worklet cannot read an
  // imported enum, so the values are spelled out here.
  const open = 2;
  const closed = 4;
  if (state === open) return Math.max(0, height);
  if (state === closed) return 0;
  return null;
}

/**
 * How far the keyboard has raised the composer above its resting place. At
 * rest the composer sits on `idleBottomPad` (the home indicator); with the
 * keyboard up it sits on the keyboard instead, so the rise is the difference.
 */
export function keyboardLiftAbove(keyboardHeight: number, idleBottomPad: number): number {
  "worklet";
  return keyboardHeight > idleBottomPad ? keyboardHeight - idleBottomPad : 0;
}
