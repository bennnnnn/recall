import React, { memo } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import { useStreamingDraft } from "@/contexts/StreamingDraftContext";
import type { Message } from "@/lib/api";

type Props = {
  item: Message;
  /** Content of the immediately preceding user message, when `item` is the assistant reply to it. */
  priorUserText: string | null;
  /** Always the real streaming/finalizing value — this row only exists while active. */
  streamVisualActive: boolean;
  /** When true, show the image-generation status label instead of chat stream draft. */
  imageGenPending?: boolean;
  lastAssistantId: string | null;
  selectedModel: string;
  quizLanguage: string;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  onRegenerate: (model: string) => void;
  onEdit: (message: Message) => void;
  onFeedback: (messageId: string, next: "up" | "down" | null) => void;
};

export const StreamingChatMessageRow = memo(function StreamingChatMessageRow({
  item,
  priorUserText,
  streamVisualActive,
  imageGenPending = false,
  lastAssistantId,
  selectedModel,
  quizLanguage,
  highlightedMessageId,
  sendingMessageId,
  onRegenerate,
  onEdit,
  onFeedback,
}: Props) {
  const streamingDraft = useStreamingDraft();
  const isLastAssistant = item.role === "assistant" && item.id === lastAssistantId;

  return (
    <MessageBubble
      message={item}
      priorUserText={priorUserText}
      isGenerating={streamVisualActive}
      liveContent={streamingDraft?.content}
      liveSearchSources={streamingDraft?.search_sources}
      liveReasoning={streamingDraft?.reasoning}
      streamStatus={imageGenPending ? "image_gen" : streamingDraft?.status}
      isLastAssistant={isLastAssistant}
      onRegenerate={
        isLastAssistant && !streamVisualActive ? () => onRegenerate(selectedModel) : undefined
      }
      onEdit={onEdit}
      canEdit={item.role === "user" && !streamVisualActive && !item.id.startsWith("local-")}
      onFeedback={onFeedback}
      quizLanguage={quizLanguage}
      highlighted={item.id === highlightedMessageId}
      isSending={item.id === sendingMessageId}
    />
  );
});
