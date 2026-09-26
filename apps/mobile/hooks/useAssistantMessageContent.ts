import { useMemo } from "react";

import type { Message } from "@/lib/api";
import {
  deriveAssistantMessageContent,
  type AssistantMessageContent,
} from "@/lib/markdown/assistantMessageContent";

type Options = {
  message: Pick<Message, "id" | "content" | "search_sources" | "renderKey">;
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

  // Streaming input is already throttled once at the draft→UI boundary
  // (useStreamingDraft, ~32ms), so derive runs straight off the incoming
  // content — a second throttle here would only add latency. The expensive
  // fence parsers defer themselves until the stream settles (see
  // deriveAssistantMessageContent).
  const derived = useMemo(
    () =>
      deriveAssistantMessageContent({
        content,
        layoutFrozen,
        isUser,
        priorUserText,
        storedSearchSources: message.search_sources,
        liveSearchSources,
        messageId: message.id,
        isGenerating,
        renderKey: message.renderKey,
      }),
    [
      content,
      layoutFrozen,
      isUser,
      priorUserText,
      message.search_sources,
      liveSearchSources,
      message.id,
      isGenerating,
      message.renderKey,
    ],
  );

  return {
    ...derived,
    content,
    hasContent: content.trim().length > 0,
  };
}
