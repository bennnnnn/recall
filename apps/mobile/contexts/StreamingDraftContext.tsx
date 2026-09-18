import React, { useEffect, useRef, useState } from "react";

import {
  getStreamingDraft,
  subscribeStreamingDraft,
  type StreamingDraft,
} from "@/lib/streamingDraftStore";
import {
  nextStreamUiFlushDelay,
  STREAM_UI_INTERVAL_MS,
} from "@/lib/streamUiTiming";

export type { StreamingDraft };

/** Optional tree marker; draft state lives in the module store. */
export function StreamingDraftProvider({ children }: { children: React.ReactNode }) {
  return children;
}

/**
 * The single throttle at the draft→UI boundary. The store publishes per rAF
 * (~60fps); consumers re-render at the shared ~30fps stream cadence instead,
 * and downstream (row, markdown) parse immediately off this snapshot. A null
 * draft (stream end/reset) flushes immediately so the tail never lags.
 */
export function useStreamingDraft(): StreamingDraft | null {
  const [snapshot, setSnapshot] = useState<StreamingDraft | null>(() => getStreamingDraft());
  const lastFlushRef = useRef(0);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const unsubscribe = subscribeStreamingDraft(() => {
      const next = getStreamingDraft();
      if (next === null) {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        lastFlushRef.current = 0;
        setSnapshot(null);
        return;
      }
      if (timer) return; // one trailing flush already scheduled
      const elapsed = Date.now() - lastFlushRef.current;
      const wait = nextStreamUiFlushDelay(elapsed, STREAM_UI_INTERVAL_MS);
      if (wait === 0) {
        lastFlushRef.current = Date.now();
        setSnapshot(next);
        return;
      }
      timer = setTimeout(() => {
        timer = null;
        lastFlushRef.current = Date.now();
        setSnapshot(getStreamingDraft());
      }, wait);
    });
    return () => {
      unsubscribe();
      if (timer) clearTimeout(timer);
    };
  }, []);

  return snapshot;
}
