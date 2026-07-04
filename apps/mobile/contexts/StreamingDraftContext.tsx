import React, { useEffect, useState } from "react";

import {
  getStreamingDraft,
  subscribeStreamingDraft,
  type StreamingDraft,
} from "@/lib/streamingDraftStore";

export type { StreamingDraft };

/** Optional tree marker; draft state lives in the module store. */
export function StreamingDraftProvider({ children }: { children: React.ReactNode }) {
  return children;
}

export function useStreamingDraft(): StreamingDraft | null {
  const [snapshot, setSnapshot] = useState<StreamingDraft | null>(() => getStreamingDraft());

  useEffect(() => subscribeStreamingDraft(() => setSnapshot(getStreamingDraft())), []);

  return snapshot;
}
