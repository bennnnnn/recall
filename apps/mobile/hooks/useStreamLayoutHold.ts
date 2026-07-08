import { useEffect, useRef, useState } from "react";

import {
  beginStreamLayoutHold,
  shouldHoldStreamLayoutOnPersistedMount,
} from "@/lib/messageListLayout";

type Options = {
  isGenerating: boolean;
  isUser: boolean;
  renderKey?: string;
};

/**
 * Briefly freeze post-stream rich chrome (sources, cards, full markdown parse)
 * so the list does not bounce when the streaming row is persisted.
 */
export function useStreamLayoutHold({ isGenerating, isUser, renderKey }: Options): boolean {
  const [holdStreamLayout, setHoldStreamLayout] = useState(false);
  const wasGeneratingRef = useRef(false);
  const persistedHoldAppliedRef = useRef(false);

  useEffect(() => {
    if (isGenerating) {
      wasGeneratingRef.current = true;
      setHoldStreamLayout(false);
      return;
    }
    if (!wasGeneratingRef.current) return;
    wasGeneratingRef.current = false;
    return beginStreamLayoutHold(setHoldStreamLayout);
  }, [isGenerating]);

  // StreamingChatMessageRow → ChatMessageRow remounts when id changes from
  // "streaming" to the persisted message id — run the same hold on mount.
  useEffect(() => {
    if (
      !shouldHoldStreamLayoutOnPersistedMount({
        isUser,
        isGenerating,
        renderKey,
        alreadyApplied: persistedHoldAppliedRef.current,
      })
    ) {
      return;
    }
    persistedHoldAppliedRef.current = true;
    return beginStreamLayoutHold(setHoldStreamLayout);
  }, [isUser, isGenerating, renderKey]);

  return holdStreamLayout;
}
