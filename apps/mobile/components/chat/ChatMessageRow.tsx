import React, { memo } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import type { Message } from "@/lib/api";

type Props = {
  item: Message;
  /** Content of the immediately preceding user message, when `item` is the assistant reply to it. */
  priorUserText: string | null;
  streaming: boolean;
  finalizing: boolean;
  lastAssistantId: string | null;
  selectedModel: string;
  quizLanguage: string;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  onRegenerate: (model: string) => void;
  onEdit: (message: Message) => void;
  onFeedback: (messageId: string, next: "up" | "down" | null) => void;
};

export const ChatMessageRow = memo(function ChatMessageRow({
  item,
  priorUserText,
  streaming,
  finalizing,
  lastAssistantId,
  selectedModel,
  quizLanguage,
  highlightedMessageId,
  sendingMessageId,
  onRegenerate,
  onEdit,
  onFeedback,
}: Props) {
  const isLastAssistant = item.role === "assistant" && item.id === lastAssistantId;
  const streamVisualActive = streaming || finalizing;

  return (
    <MessageBubble
      message={item}
      priorUserText={priorUserText}
      isGenerating={false}
      liveContent={undefined}
      liveSearchSources={undefined}
      liveReasoning={undefined}
      streamStatus={undefined}
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
