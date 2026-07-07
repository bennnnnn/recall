import { useCallback, useEffect, useMemo } from "react";

import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import { DailyQuizLoadingRow } from "@/components/chat/DailyQuizLoadingRow";
import { StreamingChatMessageRow } from "@/components/chat/StreamingChatMessageRow";
import type { Message } from "@/lib/api";
import { findLastAssistantId, priorUserTextFor } from "@/lib/chatMessageLogic";
import { DAILY_QUIZ_LOADING_ID, isDailyQuizStatusMessageId } from "@/lib/dailyQuizMessage";

type Options = {
  messages: Message[];
  streaming: boolean;
  finalizing: boolean;
  selectedModel: string;
  quizLanguage: string;
  quizVariant: "vocab" | "trivia";
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
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
  quizVariant,
  highlightedMessageId,
  sendingMessageId,
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
      streaming,
      finalizing,
      lastAssistantId,
      selectedModel,
      quizLanguage,
      highlightedMessageId,
      sendingMessageId,
      onRegenerate: regenerateResponse,
      onEdit: handleEditMessage,
      onFeedback: handleFeedback,
    }),
    [
      streaming,
      finalizing,
      lastAssistantId,
      selectedModel,
      quizLanguage,
      highlightedMessageId,
      sendingMessageId,
      regenerateResponse,
      handleEditMessage,
      handleFeedback,
    ],
  );

  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) => {
      if (item.id === DAILY_QUIZ_LOADING_ID) {
        return <DailyQuizLoadingRow quizVariant={quizVariant} />;
      }

      const priorUserText = priorUserTextFor(messages, index);

      if (isDailyQuizStatusMessageId(item.id)) {
        return (
          <ChatMessageRow item={item} priorUserText={priorUserText} {...sharedRowProps} />
        );
      }

      return item.id === "streaming" ? (
        <StreamingChatMessageRow item={item} priorUserText={priorUserText} {...sharedRowProps} />
      ) : (
        <ChatMessageRow item={item} priorUserText={priorUserText} {...sharedRowProps} />
      );
    },
    [sharedRowProps, quizVariant, messages],
  );

  return { lastAssistantId, headerTitleLabel, renderItem };
}
