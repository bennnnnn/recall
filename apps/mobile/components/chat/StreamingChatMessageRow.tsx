import React, { memo } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import { useStreamingDraft } from "@/contexts/StreamingDraftContext";
import { canEditUserMessage } from "@/lib/chatEditLogic";
import { useThrottledStreamText } from "@/hooks/useThrottledStreamText";
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
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  lastUserMessageId: string | null;
  onRegenerate: (model: string) => void;
  regenerating?: boolean;
  onEdit: (message: Message) => void;
  onFeedback: (messageId: string, next: "up" | "down" | null) => void;
  lessonProjectId?: string | null;
  onOpenLesson?: (projectId: string) => void;
  onRetryImageGen?: () => void;
};

export const StreamingChatMessageRow = memo(function StreamingChatMessageRow({
  item,
  priorUserText,
  streamVisualActive,
  imageGenPending = false,
  lastAssistantId,
  selectedModel,
  highlightedMessageId,
  sendingMessageId,
  lastUserMessageId,
  onRegenerate,
  regenerating = false,
  onEdit,
  onFeedback,
  lessonProjectId = null,
  onOpenLesson,
  onRetryImageGen,
}: Props) {
  const streamingDraft = useStreamingDraft();
  const liveContent = useThrottledStreamText(streamingDraft?.content, streamVisualActive);
  const streamStatus = useThrottledStreamText(
    imageGenPending ? "image_gen" : streamingDraft?.status,
    streamVisualActive,
  );
  const streamStatusDetail = useThrottledStreamText(
    imageGenPending ? undefined : streamingDraft?.statusDetail,
    streamVisualActive,
  );
  const isLastAssistant = item.role === "assistant" && item.id === lastAssistantId;

  return (
    <MessageBubble
      message={item}
      priorUserText={priorUserText}
      isGenerating={streamVisualActive}
      liveContent={liveContent}
      liveSearchSources={streamingDraft?.search_sources}
      streamStatus={streamStatus}
      streamStatusDetail={streamStatusDetail}
      isLastAssistant={isLastAssistant}
      onRegenerate={
        isLastAssistant && !streamVisualActive ? () => onRegenerate(selectedModel) : undefined
      }
      regenerating={isLastAssistant && regenerating}
      onRetryImageGen={item.image_gen_failure ? onRetryImageGen : undefined}
      onEdit={onEdit}
      canEdit={canEditUserMessage({
        role: item.role,
        messageId: item.id,
        lastUserMessageId,
        streamVisualActive,
      })}
      onFeedback={onFeedback}
      highlighted={item.id === highlightedMessageId}
      isSending={item.id === sendingMessageId}
      lessonProjectId={lessonProjectId}
      onOpenLesson={isLastAssistant ? onOpenLesson : undefined}
    />
  );
});
