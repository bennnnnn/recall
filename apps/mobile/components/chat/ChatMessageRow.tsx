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
  selectedModel: string;
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
  streamVisualActive,
  lastAssistantId,
  selectedModel,
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
      highlighted={item.id === highlightedMessageId}
      isSending={item.id === sendingMessageId}
      lessonProjectId={lessonProjectId}
      onOpenLesson={isLastAssistant ? onOpenLesson : undefined}
    />
  );
});
