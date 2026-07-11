import React, { memo, useCallback } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import type { Message } from "@/lib/api";

type Props = {
  item: Message;
  /** Content of the immediately preceding user message, when `item` is the assistant reply to it. */
  priorUserText: string | null;
  /**
   * Whether THIS row's own output depends on the active stream state — see
   * streamVisualActiveForRow. Always the real streaming/finalizing value for
   * user rows and the last-assistant row; a stable `false` for every other
   * assistant row, so this row doesn't re-render when a turn starts/ends.
   */
  streamVisualActive: boolean;
  lastAssistantId: string | null;
  activeQuizMessageId: string | null;
  selectedModel: string;
  quizLanguage: string;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  onRegenerate: (model: string) => void;
  onEdit: (message: Message) => void;
  onFeedback: (messageId: string, next: "up" | "down" | null) => void;
  onQuizAnswer?: (letter: string) => void;
};

export const ChatMessageRow = memo(function ChatMessageRow({
  item,
  priorUserText,
  streamVisualActive,
  lastAssistantId,
  activeQuizMessageId,
  selectedModel,
  quizLanguage,
  highlightedMessageId,
  sendingMessageId,
  onRegenerate,
  onEdit,
  onFeedback,
  onQuizAnswer,
}: Props) {
  const isLastAssistant = item.role === "assistant" && item.id === lastAssistantId;
  const isActiveQuiz = item.role === "assistant" && item.id === activeQuizMessageId;

  const handleRegenerate = useCallback(() => {
    onRegenerate(selectedModel);
  }, [onRegenerate, selectedModel]);

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
      onRegenerate={isLastAssistant && !streamVisualActive ? handleRegenerate : undefined}
      onEdit={onEdit}
      canEdit={item.role === "user" && !streamVisualActive && !item.id.startsWith("local-")}
      onFeedback={onFeedback}
      quizLanguage={quizLanguage}
      highlighted={item.id === highlightedMessageId}
      isSending={item.id === sendingMessageId}
      onQuizAnswer={isActiveQuiz && !streamVisualActive ? onQuizAnswer : undefined}
    />
  );
});
