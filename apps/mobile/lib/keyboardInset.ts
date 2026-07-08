/**
 * Gate for pushing a new keyboard height from the UI thread to JS state.
 * Called from inside a `useAnimatedReaction` callback, so it must carry the
 * 'worklet' directive to run on the UI thread — it also works fine as a
 * plain pure function under Jest, where the directive is inert.
 */
export function shouldPushKeyboardHeight(
  next: number,
  previous: number,
  thresholdPx: number,
): boolean {
  "worklet";
  const isOpenTransition = (next > 0) !== (previous > 0);
  if (isOpenTransition) return true;
  return Math.abs(next - previous) >= thresholdPx;
}
