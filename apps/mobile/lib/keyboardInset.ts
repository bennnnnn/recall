/**
 * Gate for pushing a new keyboard height from the UI thread to JS state.
 * Called from inside a `useAnimatedReaction` callback, so it must carry the
 * 'worklet' directive to run on the UI thread — it also works fine as a
 * plain pure function under Jest, where the directive is inert.
 */
/**
 * `lastPushed` is the last height we sent to JS — not the previous animation
 * frame. Comparing frames at a 48px gate never catches the rest of a smooth
 * iOS curve (~16px/frame), so list pad stayed at the first 1–20px and
 * messages sat under the composer.
 */
export function shouldPushKeyboardHeight(
  next: number,
  lastPushed: number,
  thresholdPx: number,
  previousFrame: number = lastPushed,
): boolean {
  "worklet";
  const isOpenTransition = (next > 0) !== (lastPushed > 0);
  if (isOpenTransition) return true;
  if (Math.abs(next - lastPushed) >= thresholdPx) return true;
  // Last step of the curve is often under the threshold — still commit rest.
  return next === previousFrame && next !== lastPushed;
}
