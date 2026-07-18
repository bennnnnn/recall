import { useEffect, useMemo, useRef, useState } from "react";

import type { Message } from "@/lib/api";
import {
  deriveAssistantMessageContent,
  type AssistantMessageContent,
} from "@/lib/assistantMessageContent";
import {
  nextStreamUiFlushDelay,
  STREAM_UI_INTERVAL_MS,
} from "@/lib/streamUiTiming";

type Options = {
  message: Pick<
    Message,
    "id" | "content" | "search_sources" | "context_summarized" | "renderKey"
  >;
  liveContent?: string;
  liveSearchSources?: Message["search_sources"];
  priorUserText?: string | null;
  layoutFrozen: boolean;
  isGenerating: boolean;
  isUser: boolean;
};

export function useAssistantMessageContent({
  message,
  liveContent,
  liveSearchSources,
  priorUserText = null,
  layoutFrozen,
  isGenerating,
  isUser,
}: Options): AssistantMessageContent & { content: string } {
  const content = liveContent ?? message.content;

  // Draft publishes ~rAF; fence strip/parse (quiz/calendar/places/images) is
  // far heavier than painting tokens. Throttle derive inputs to the shared
  // stream UI cadence while generating, and flush immediately when the
  // stream ends so the final reply is never stuck on a stale strip.
  const [deriveContent, setDeriveContent] = useState(content);
  const [deriveSearchSources, setDeriveSearchSources] = useState(liveSearchSources);
  const lastFlushRef = useRef(0);

  useEffect(() => {
    if (!isGenerating) {
      setDeriveContent(content);
      setDeriveSearchSources(liveSearchSources);
      lastFlushRef.current = 0;
      return;
    }
    const elapsed = Date.now() - lastFlushRef.current;
    const wait = nextStreamUiFlushDelay(elapsed, STREAM_UI_INTERVAL_MS);
    if (wait === 0) {
      lastFlushRef.current = Date.now();
      setDeriveContent(content);
      setDeriveSearchSources(liveSearchSources);
      return;
    }
    const id = setTimeout(() => {
      lastFlushRef.current = Date.now();
      setDeriveContent(content);
      setDeriveSearchSources(liveSearchSources);
    }, wait);
    return () => clearTimeout(id);
  }, [content, liveSearchSources, isGenerating]);

  const derived = useMemo(
    () =>
      deriveAssistantMessageContent({
        content: deriveContent,
        layoutFrozen,
        isUser,
        priorUserText,
        storedSearchSources: message.search_sources,
        liveSearchSources: deriveSearchSources,
        contextSummarized: message.context_summarized,
        messageId: message.id,
        isGenerating,
        renderKey: message.renderKey,
      }),
    [
      deriveContent,
      layoutFrozen,
      isUser,
      priorUserText,
      message.search_sources,
      deriveSearchSources,
      message.context_summarized,
      message.id,
      isGenerating,
      message.renderKey,
    ],
  );

  // Live buffer for waiting-indicator / length checks; derived fences stay throttled.
  return {
    ...derived,
    content,
    hasContent: content.trim().length > 0,
  };
}
