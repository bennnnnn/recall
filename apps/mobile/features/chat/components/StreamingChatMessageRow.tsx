import { memo, useCallback } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import { useStreamingDraft } from "@/contexts/StreamingDraftContext";
import { MessageRowErrorBoundary } from "@/features/chat/components/MessageRowErrorBoundary";
import { StreamSilenceHint } from "@/features/chat/components/StreamSilenceHint";
import { useStreamSilence } from "@/features/chat/hooks/useStreamSilence";
import type { Message } from "@/lib/api";
import { messageListKey } from "@/lib/messageListLayout";

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
  onRegenerate: (model: string) => void;
  regenerating?: boolean;
  onFeedback: (messageId: string, next: "up" | "down" | null) => void;
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
  onRegenerate,
  regenerating = false,
  onFeedback,
  onRetryImageGen,
}: Props) {
  // Already throttled once at the store→UI boundary (useStreamingDraft) —
  // read directly; a second throttle here would only add latency.
  const streamingDraft = useStreamingDraft();
  const liveContent = streamingDraft?.content;
  const streamStatus = imageGenPending ? "image_gen" : streamingDraft?.status;
  const streamStatusDetail = imageGenPending ? undefined : streamingDraft?.statusDetail;
  const isLastAssistant = item.role === "assistant" && item.id === lastAssistantId;
  const handleRegenerate = useCallback(() => {
    onRegenerate(selectedModel);
  }, [onRegenerate, selectedModel]);
  const stalled = useStreamSilence(liveContent?.length ?? 0, streamVisualActive && !imageGenPending);

  return (
    <MessageRowErrorBoundary resetKey={messageListKey(item)}>
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
          isLastAssistant && !streamVisualActive ? handleRegenerate : undefined
        }
        regenerating={isLastAssistant && regenerating}
        onRetryImageGen={item.image_gen_failure ? onRetryImageGen : undefined}
        onFeedback={onFeedback}
        highlighted={item.id === highlightedMessageId}
        isSending={item.id === sendingMessageId}
      />
      {stalled ? <StreamSilenceHint /> : null}
    </MessageRowErrorBoundary>
  );
});
