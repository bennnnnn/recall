/**
 * Shared motion scale for Reanimated (and duration ms for RN Animated).
 * Prefer these over one-off copy-pasted durations/easings.
 */
import { Easing } from "react-native-reanimated";

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
