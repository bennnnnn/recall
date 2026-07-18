/**
 * Shared motion scale for Reanimated (and duration ms for RN Animated).
 * Prefer these over one-off copy-pasted durations/easings.
 */
import { useEffect, useState } from "react";
import { AccessibilityInfo } from "react-native";
import { Easing } from "react-native-reanimated";

export { motionMs } from "@/lib/motionDuration";

export const Motion = {
  duration: {
    /** Fade / banner enter-exit */
    snappy: 200,
    /** Short UI settle (e.g. stream layout hold) */
    short: 280,
    /** Cursor blink half-cycle */
    pulse: 450,
    /** Skeleton opacity breathe half-cycle */
    breathe: 600,
    /** Soft pulse (typing / mic / image-gen) */
    soft: 700,
    /** Pendulum / sway half-cycle */
    sway: 650,
  },
  easing: {
    inOut: Easing.inOut(Easing.ease),
    sway: Easing.inOut(Easing.sin),
    out: Easing.out(Easing.ease),
    in: Easing.in(Easing.ease),
  },
} as const;

/** Subscribe to the OS Reduce Motion setting. */
export function useReduceMotion(): boolean {
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    let mounted = true;
    void AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (mounted) setReduceMotion(enabled);
    });
    const sub = AccessibilityInfo.addEventListener("reduceMotionChanged", setReduceMotion);
    return () => {
      mounted = false;
      sub.remove();
    };
  }, []);

  return reduceMotion;
}
