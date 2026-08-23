import React, { memo, useCallback } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import type { Message } from "@/lib/api";

type Props = {
  item: Message;
  /** Content of the immediately preceding user message, when `item` is the assistant reply to it. */
  priorUserText: string | null;
  /** User row: this letter is answering an in-progress A–D quiz. */
  isQuizReply: boolean;
  /**
   * Whether THIS row's own output depends on the active stream state — see
   * streamVisualActiveForRow. Always the real streaming/finalizing value for
   * user rows and the last-assistant row; a stable `false` for every other
   * assistant row, so this row doesn't re-render when a turn starts/ends.
   */
  streamVisualActive: boolean;
  /**
   * Global stream state (streaming || finalizing). Only passed as `true` for
   * the active quiz row so quiz chips can be disabled during any in-flight
   * turn without re-rendering the entire list. Stable `false` for all other
   * rows. (LANG-UI-001)
   */
  chatStreamActive: boolean;
  lastAssistantId: string | null;
  activeQuizMessageId: string | null;
  selectedModel: string;
  quizLanguage: string;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  onRegenerate: (model: string) => void;
  regenerating?: boolean;
  onEdit: (message: Message) => void;
  onFeedback: (messageId: string, next: "up" | "down" | null) => void;
  lessonProjectId?: string | null;
  onOpenLesson?: (projectId: string) => void;
  onRetryImageGen?: () => void;
};

export const ChatMessageRow = memo(function ChatMessageRow({
  item,
  priorUserText,
  isQuizReply,
  streamVisualActive,
  chatStreamActive,
  lastAssistantId,
  activeQuizMessageId,
  selectedModel,
  quizLanguage,
  highlightedMessageId,
  sendingMessageId,
  onRegenerate,
  regenerating = false,
  onEdit,
  onFeedback,
  lessonProjectId = null,
  onOpenLesson,
  onRetryImageGen,
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
      isQuizReply={isQuizReply}
      isGenerating={false}
      liveContent={undefined}
      liveSearchSources={undefined}
      liveReasoning={undefined}
      streamStatus={undefined}
      isLastAssistant={isLastAssistant}
      onRegenerate={
        isLastAssistant && !streamVisualActive && !item.image_gen_failure
          ? handleRegenerate
          : undefined
      }
      regenerating={isLastAssistant && regenerating}
      onRetryImageGen={item.image_gen_failure ? onRetryImageGen : undefined}
      onEdit={onEdit}
      canEdit={item.role === "user" && !streamVisualActive && !item.id.startsWith("local-")}
      onFeedback={onFeedback}
      quizLanguage={quizLanguage}
      highlighted={item.id === highlightedMessageId}
      isSending={item.id === sendingMessageId}
      lessonProjectId={lessonProjectId}
      onOpenLesson={isLastAssistant || isActiveQuiz ? onOpenLesson : undefined}
    />
  );
});
