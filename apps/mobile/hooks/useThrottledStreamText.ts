import { useEffect, useRef, useState } from "react";

import {
  nextStreamUiFlushDelay,
  STREAM_UI_INTERVAL_MS,
} from "@/lib/streamUiTiming";

/**
 * Draft publishes ~rAF; paint stream chrome (reasoning, status) at the shared
 * ~20fps cadence so the streaming row does not re-render every frame.
 * Flushes immediately when generation ends so the last token is not stuck.
 */
export function useThrottledStreamText(
  value: string | undefined,
  isGenerating: boolean,
): string | undefined {
  const [shown, setShown] = useState(value);
  const lastFlushRef = useRef(0);

  useEffect(() => {
    if (!isGenerating) {
      setShown(value);
      lastFlushRef.current = 0;
      return;
    }
    const elapsed = Date.now() - lastFlushRef.current;
    const wait = nextStreamUiFlushDelay(elapsed, STREAM_UI_INTERVAL_MS);
    if (wait === 0) {
      lastFlushRef.current = Date.now();
      setShown(value);
      return;
    }
    const id = setTimeout(() => {
      lastFlushRef.current = Date.now();
      setShown(value);
    }, wait);
    return () => clearTimeout(id);
  }, [value, isGenerating]);

  return shown;
}
