import { useEffect } from "react";

import { warmSvgMath } from "@/lib/math/svgMath";
import { scheduleIdleTask } from "@/lib/scheduleIdle";

/** The chat's own first frames and its cold-start work come before the warm-up. */
export const WARM_MATH_AFTER_MS = 2_000;

/**
 * Load the display-maths renderer (MathJax) while the chat is idle, so the
 * first display formula in a reply draws at once instead of waiting for the
 * parser to load.
 */
export function useWarmMathRenderer(): void {
  useEffect(() => {
    let cancelIdle: (() => void) | null = null;
    const timer = setTimeout(() => {
      cancelIdle = scheduleIdleTask(warmSvgMath);
    }, WARM_MATH_AFTER_MS);
    return () => {
      clearTimeout(timer);
      cancelIdle?.();
    };
  }, []);
}
