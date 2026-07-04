import { useCallback, useEffect, useMemo } from "react";

import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import { StreamingChatMessageRow } from "@/components/chat/StreamingChatMessageRow";
import { Message } from "@/lib/api";
import { findLastAssistantId } from "@/lib/chatMessageLogic";
import { inferQuizAnswersFromMessages } from "@/lib/parseVocabQuiz";

type Options = {
  messages: Message[];
  streaming: boolean;
  finalizing: boolean;
  selectedModel: string;
  quizLanguage: string;
  quizVariant: "vocab" | "trivia";
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  creatingRef: React.MutableRefObject<boolean>;
  setMenuVisible: React.Dispatch<React.SetStateAction<boolean>>;
  regenerateResponse: (model: string) => void | Promise<void>;
  handleEditMessage: (message: Message) => void;
  handleFeedback: (messageId: string, next: "up" | "down" | null) => void;
  handleQuizAnswer: (
    messageId: string,
    letter: "A" | "B" | "C" | "D",
    meta?: import("@/lib/parseVocabQuiz").QuizAnswerMeta,
  ) => void;
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
  creatingRef,
  setMenuVisible,
  regenerateResponse,
  handleEditMessage,
  handleFeedback,
  handleQuizAnswer,
}: Options) {
  useEffect(() => {
    if (messages.length === 0) setMenuVisible(false);
  }, [messages.length, setMenuVisible]);
  const quizAnswers = useMemo(
    () => inferQuizAnswersFromMessages(messages),
    [messages],
  );

  const lastAssistantId = useMemo(
    () => findLastAssistantId(messages),
    [messages],
  );

  // Intentionally no chat title in the header (home or active threads).
  // Names live in the drawer and ⋮ menu — do not wire displayChatTitle here.
  const headerTitleLabel = null;

  const sharedRowProps = useMemo(
    () => ({
      messages,
      streaming,
      finalizing,
      lastAssistantId,
      selectedModel,
      quizLanguage,
      quizVariant,
      quizAnswers,
      highlightedMessageId,
      sendingMessageId,
      quizDisabled: streaming || finalizing || creatingRef.current,
      onRegenerate: regenerateResponse,
      onEdit: handleEditMessage,
      onFeedback: handleFeedback,
      onQuizAnswer: handleQuizAnswer,
    }),
    [
      messages,
      streaming,
      finalizing,
      lastAssistantId,
      selectedModel,
      quizLanguage,
      quizVariant,
      quizAnswers,
      highlightedMessageId,
      sendingMessageId,
      regenerateResponse,
      handleEditMessage,
      handleFeedback,
      handleQuizAnswer,
      creatingRef,
    ],
  );

  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) =>
      item.id === "streaming" ? (
        <StreamingChatMessageRow item={item} index={index} {...sharedRowProps} />
      ) : (
        <ChatMessageRow item={item} index={index} {...sharedRowProps} />
      ),
    [sharedRowProps],
  );

  return { quizAnswers, lastAssistantId, headerTitleLabel, renderItem };
}
