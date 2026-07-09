import { useEffect, useLayoutEffect, useRef, useState } from "react";

import {
  beginStreamLayoutHold,
  shouldHoldStreamLayoutOnPersistedMount,
} from "@/lib/messageListLayout";

type Options = {
  isGenerating: boolean;
  isUser: boolean;
  renderKey?: string;
};

function shouldStartPersistedHold(
  isUser: boolean,
  isGenerating: boolean,
  renderKey?: string,
): boolean {
  return shouldHoldStreamLayoutOnPersistedMount({
    isUser,
    isGenerating,
    renderKey,
    alreadyApplied: false,
  });
}

/**
 * Briefly freeze post-stream rich chrome (sources, cards, full markdown parse)
 * so the list does not bounce when the streaming row is persisted.
 */
export function useStreamLayoutHold({ isGenerating, isUser, renderKey }: Options): boolean {
  const [holdStreamLayout, setHoldStreamLayout] = useState(() =>
    shouldStartPersistedHold(isUser, isGenerating, renderKey),
  );
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
  // "streaming" to the persisted message id — start hold before paint so the
  // first persisted frame does not flash full chrome + feedback icons.
  useLayoutEffect(() => {
    if (persistedHoldAppliedRef.current) return;
    if (!shouldStartPersistedHold(isUser, isGenerating, renderKey)) return;
    persistedHoldAppliedRef.current = true;
    setHoldStreamLayout(true);
    return beginStreamLayoutHold(setHoldStreamLayout);
  }, [isUser, isGenerating, renderKey]);

  return holdStreamLayout;
}
