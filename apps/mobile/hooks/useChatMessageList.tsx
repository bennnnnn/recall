import { useCallback, useEffect, useMemo } from "react";

import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import type { StreamingDraft } from "@/hooks/useChat";
import { Message } from "@/lib/api";
import { findLastAssistantId } from "@/lib/chatMessageLogic";
import { inferQuizAnswersFromMessages } from "@/lib/parseVocabQuiz";

type Options = {
  messages: Message[];
  streaming: boolean;
  streamingDraft: StreamingDraft | null;
  selectedModel: string;
  quizLanguage: string;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  creatingRef: React.MutableRefObject<boolean>;
  setMenuVisible: React.Dispatch<React.SetStateAction<boolean>>;
  regenerateResponse: (model: string) => void | Promise<void>;
  handleEditMessage: (message: Message) => void;
  handleFeedback: (messageId: string, next: "up" | "down" | null) => void;
  handleQuizAnswer: (messageId: string, letter: "A" | "B" | "C" | "D") => void;
};

export function useChatMessageList({
  messages,
  streaming,
  streamingDraft,
  selectedModel,
  quizLanguage,
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

  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) => (
      <ChatMessageRow
        item={item}
        index={index}
        messages={messages}
        streaming={streaming}
        streamingDraft={streamingDraft}
        lastAssistantId={lastAssistantId}
        selectedModel={selectedModel}
        quizLanguage={quizLanguage}
        quizAnswers={quizAnswers}
        highlightedMessageId={highlightedMessageId}
        sendingMessageId={sendingMessageId}
        quizDisabled={streaming || creatingRef.current}
        onRegenerate={regenerateResponse}
        onEdit={handleEditMessage}
        onFeedback={handleFeedback}
        onQuizAnswer={handleQuizAnswer}
      />
    ),
    [
      messages,
      streaming,
      streamingDraft,
      lastAssistantId,
      selectedModel,
      quizLanguage,
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

  return { quizAnswers, lastAssistantId, headerTitleLabel, renderItem };
}
