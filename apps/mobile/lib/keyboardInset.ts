/**
 * Keyboard geometry for the chat screen. `keyboardLiftAbove` and
 * `correctedKeyboardHeight` run inside Reanimated worklets, so they carry the
 * 'worklet' directive and read nothing but their arguments; the others run on
 * the JS thread, on every keyboard frame the UI thread forwards there.
 */

/** Reanimated's `KeyboardState.OPEN` and `KeyboardState.CLOSED`. */
export const KEYBOARD_OPEN = 2;
export const KEYBOARD_CLOSED = 4;

/** `heldAt` when no correction holds: Reanimated's height stands. */
export const NO_KEYBOARD_CORRECTION = -1;

/**
 * The height to hand to React state, or null while the keyboard is still
 * moving. React only needs where the keyboard comes to rest: the composer,
 * the list's bottom space and the chrome above the composer follow every
 * frame on the UI thread. `state` is Reanimated's `KeyboardState`, which
 * reports OPEN and CLOSED once the native show or hide has finished.
 */
export function settledKeyboardHeight(state: number, height: number): number | null {
  if (state === KEYBOARD_OPEN) return Math.max(0, height);
  if (state === KEYBOARD_CLOSED) return 0;
  return null;
}

/**
 * An Android keyboard event's height as Reanimated measures it. React Native
 * measures the keyboard above the navigation bar; Reanimated, edge to edge,
 * from the bottom of the screen, the bar included. A floating keyboard covers
 * no bottom edge: 0.
 */
export function keyboardEventHeight(eventHeight: number, navigationBar: number): number {
  return eventHeight > 0 ? eventHeight + navigationBar : 0;
}

/** Which way Reanimated's keyboard has moved since React Native's last keyboard event. */
export type KeyboardMotion = { rose: boolean; fell: boolean };

/**
 * Where the composer should sit when Reanimated's keyboard, at rest, disagrees
 * with the real one, or null when they agree. On Android Reanimated ignores a
 * zero-height inset while it thinks the keyboard is open, and follows
 * keyboard changes without an inset animation only while it is open, so a hide
 * it never saw (an animation cut short, a sheet or another app taking the
 * window) leaves its height where the keyboard's top was. `real` is the
 * keyboard React Native's own events report (null before the first one).
 *
 * Only a keyboard Reanimated has plainly lost is corrected: one it reports up
 * that is down, or down that is up. Two heights that merely differ stay
 * Reanimated's, which measures the inset itself; and so does a keyboard
 * Reanimated has moved toward since the last event (`motion`), since then it
 * is following a show or a hide whose event has not come.
 */
export function keyboardCorrection(
  reported: number,
  real: number | null,
  motion: KeyboardMotion = { rose: false, fell: false },
): number | null {
  if (real === null) return null;
  if (real <= 0) return reported > 0 && !motion.rose ? 0 : null;
  return reported <= 0 && !motion.fell ? real : null;
}

/**
 * The keyboard height the chat draws against. While a correction holds,
 * `heldAt` is the stale height Reanimated keeps reporting and `real` stands
 * in for it; the moment Reanimated reports anything else it is tracking the
 * keyboard again and its height stands.
 */
export function correctedKeyboardHeight(reported: number, heldAt: number, real: number): number {
  "worklet";
  if (heldAt >= 0 && reported === heldAt) return real;
  return reported > 0 ? reported : 0;
}

/**
 * Whether a keyboard frame is a step the thread should follow: the first
 * frame of a show or a hide, every `thresholdPx` of travel, and the frame the
 * keyboard comes to rest on.
 *
 * `lastPushed` is the last height that was a step — not the previous animation
 * frame. Comparing frames at a 48px gate never catches the rest of a smooth
 * iOS curve (~16px/frame), so the thread stopped short of the keyboard.
 */
export function shouldPushKeyboardHeight(
  next: number,
  lastPushed: number,
  thresholdPx: number,
  previousFrame: number = lastPushed,
): boolean {
  const isOpenTransition = (next > 0) !== (lastPushed > 0);
  if (isOpenTransition) return true;
  if (Math.abs(next - lastPushed) >= thresholdPx) return true;
  // Last step of the curve is often under the threshold — still commit rest.
  return next === previousFrame && next !== lastPushed;
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
