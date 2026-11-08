import { useEffect, useState } from "react";
import { Keyboard, Platform } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { keyboardEventHeight } from "@/lib/keyboardInset";

/**
 * The OS keyboard's height, from the bottom edge of the screen, via Keyboard events
 * (which reach Modals too). Nothing resizes for the keyboard: Android apps are edge to
 * edge (enforced from Android 15), so `adjustResize` no longer shrinks the window, a
 * Modal's included, and whatever avoids the keyboard lifts itself by this height.
 * iOS measures the keyboard from the screen's edge; Android measures it above the
 * navigation bar, which an edge-to-edge window draws under, so the bar is added back.
 * When `enabled` is false, height resets to 0.
 */
export function useKeyboardHeight(enabled = true): number {
  const insets = useSafeAreaInsets();
  // Only Android adds the bar back; iOS re-subscribing on an inset change (iPad) could
  // re-apply stale keyboard metrics.
  const navigationBar = Platform.OS === "android" ? insets.bottom : 0;
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setKeyboardHeight(0);
      return;
    }
    const fromScreenEdge = (height: number) =>
      Platform.OS === "android" ? keyboardEventHeight(height, navigationBar) : Math.max(0, height);
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, (e) => {
      setKeyboardHeight(fromScreenEdge(e.endCoordinates.height));
    });
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    const metrics = Keyboard.metrics();
    if (metrics?.height) setKeyboardHeight(fromScreenEdge(metrics.height));
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, [enabled, navigationBar]);

  return keyboardHeight;
}
