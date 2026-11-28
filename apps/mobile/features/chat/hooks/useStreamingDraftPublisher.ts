import { useCallback, useEffect, useRef, useSyncExternalStore } from "react";

import { useKeepAwakeWhile } from "@/hooks/useKeepAwakeWhile";
import {
  getStreamingDraft,
  publishStreamingDraft,
  subscribeStreamingDraft,
  type StreamingDraft,
} from "@/features/chat/model/streamingDraftStore";

/** A picture the stream is drawing: Regenerate on a picture, or a send the server draws. */
function drawingPicture(): boolean {
  return getStreamingDraft()?.status === "image_gen";
}

/**
 * Publishes the streaming bubble's draft at most once a frame, so a burst of tokens
 * paints once; null clears it at once, and so does unmounting. While the draft says a
 * picture is being drawn (30 s to 2 minutes), the screen stays on, as it does for one the
 * composer asked for (review H4); the chat renders again only when that changes.
 */
export function useStreamingDraftPublisher(): (draft: StreamingDraft | null) => void {
  const frame = useRef<{ id: number | null; draft: StreamingDraft | null }>({ id: null, draft: null });
  useKeepAwakeWhile("picture", useSyncExternalStore(subscribeStreamingDraft, drawingPicture));
  const publish = useCallback((draft: StreamingDraft | null) => {
    const next = frame.current;
    next.draft = draft;
    if (draft === null) {
      if (next.id != null) cancelAnimationFrame(next.id);
      next.id = null;
      publishStreamingDraft(null);
      return;
    }
    if (next.id == null) {
      next.id = requestAnimationFrame(() => {
        next.id = null;
        publishStreamingDraft(next.draft);
      });
    }
  }, []);
  useEffect(() => () => publish(null), [publish]);
  return publish;
}
