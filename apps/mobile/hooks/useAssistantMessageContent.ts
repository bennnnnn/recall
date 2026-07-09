import { useMemo } from "react";

import type { Message } from "@/lib/api";
import {
  deriveAssistantMessageContent,
  type AssistantMessageContent,
} from "@/lib/assistantMessageContent";

type Options = {
  message: Pick<
    Message,
    "id" | "content" | "search_sources" | "context_summarized" | "recalled" | "renderKey"
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

  const derived = useMemo(
    () =>
      deriveAssistantMessageContent({
        content,
        layoutFrozen,
        isUser,
        priorUserText,
        storedSearchSources: message.search_sources,
        liveSearchSources,
        contextSummarized: message.context_summarized,
        recalled: message.recalled,
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
      message.context_summarized,
      message.recalled,
      message.id,
      isGenerating,
      message.renderKey,
    ],
  );

  return { ...derived, content };
}
