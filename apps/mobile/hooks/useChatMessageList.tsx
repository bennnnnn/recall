import { useCallback, useEffect, useMemo } from "react";

import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import { StreamingChatMessageRow } from "@/components/chat/StreamingChatMessageRow";
import type { Message } from "@/lib/api";
import {
  findLastAssistantId,
  isChatStreamActive,
  priorUserTextFor,
  streamVisualActiveForRow,
} from "@/lib/chatMessageLogic";

type Options = {
  messages: Message[];
  streaming: boolean;
  finalizing: boolean;
  selectedModel: string;
  quizLanguage: string;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  imageGenPendingId?: string | null;
  setMenuVisible: React.Dispatch<React.SetStateAction<boolean>>;
  regenerateResponse: (model: string) => void | Promise<void>;
  handleEditMessage: (message: Message) => void;
  handleFeedback: (messageId: string, next: "up" | "down" | null) => void;
};

export function useChatMessageList({
  messages,
  streaming,
  finalizing,
  selectedModel,
  quizLanguage,
  highlightedMessageId,
  sendingMessageId,
  imageGenPendingId = null,
  setMenuVisible,
  regenerateResponse,
  handleEditMessage,
  handleFeedback,
}: Options) {
  useEffect(() => {
    if (messages.length === 0) setMenuVisible(false);
  }, [messages.length, setMenuVisible]);

  const lastAssistantId = useMemo(
    () => findLastAssistantId(messages),
    [messages],
  );

  const headerTitleLabel = null;

  const sharedRowProps = useMemo(
    () => ({
      lastAssistantId,
      selectedModel,
      quizLanguage,
      highlightedMessageId,
      sendingMessageId,
      imageGenPendingId,
      onRegenerate: regenerateResponse,
      onEdit: handleEditMessage,
      onFeedback: handleFeedback,
    }),
    [
      lastAssistantId,
      selectedModel,
      quizLanguage,
      highlightedMessageId,
      sendingMessageId,
      imageGenPendingId,
      regenerateResponse,
      handleEditMessage,
      handleFeedback,
    ],
  );

  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) => {
      const priorUserText = priorUserTextFor(messages, index);

      if (item.id === "streaming") {
        return (
          <StreamingChatMessageRow
            item={item}
            priorUserText={priorUserText}
            streamVisualActive={isChatStreamActive(streaming, finalizing)}
            {...sharedRowProps}
          />
        );
      }

      const streamVisualActive = streamVisualActiveForRow(
        item.role,
        item.id,
        lastAssistantId,
        streaming,
        finalizing,
      );
      return (
        <ChatMessageRow
          item={item}
          priorUserText={priorUserText}
          streamVisualActive={streamVisualActive}
          {...sharedRowProps}
        />
      );
    },
    [sharedRowProps, messages, streaming, finalizing, lastAssistantId, imageGenPendingId],
  );

  return { lastAssistantId, headerTitleLabel, renderItem };
}
