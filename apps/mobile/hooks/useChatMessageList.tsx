import { useCallback, useEffect, useMemo } from "react";

import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import type { StreamingDraft } from "@/hooks/useChat";
import { Message } from "@/lib/api";
import { displayChatTitle } from "@/lib/chatTitle";
import { findLastAssistantId } from "@/lib/chatMessageLogic";
import { inferQuizAnswersFromMessages } from "@/lib/parseVocabQuiz";

type Options = {
  messages: Message[];
  streaming: boolean;
  streamingDraft: StreamingDraft | null;
  selectedModel: string;
  quizLanguage: string;
  highlightedMessageId: string | null;
  creatingRef: React.MutableRefObject<boolean>;
  chatTitle: string | null;
  titleGenerating: boolean;
  setMenuVisible: React.Dispatch<React.SetStateAction<boolean>>;
  regenerateResponse: (messageId: string) => void;
  handleEditMessage: (message: Message) => void;
  handleFeedback: (messageId: string, next: "up" | "down" | null) => void;
  handleQuizAnswer: (messageId: string, letter: "A" | "B" | "C" | "D") => void;
  t: (key: string) => string;
};

export function useChatMessageList({
  messages,
  streaming,
  streamingDraft,
  selectedModel,
  quizLanguage,
  highlightedMessageId,
  creatingRef,
  chatTitle,
  titleGenerating,
  setMenuVisible,
  regenerateResponse,
  handleEditMessage,
  handleFeedback,
  handleQuizAnswer,
  t,
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

  const headerTitleLabel = useMemo(
    () =>
      messages.length > 0
        ? displayChatTitle(chatTitle, { generating: titleGenerating }, t)
        : null,
    [messages.length, chatTitle, titleGenerating, t],
  );

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
      regenerateResponse,
      handleEditMessage,
      handleFeedback,
      handleQuizAnswer,
      creatingRef,
    ],
  );

  return { quizAnswers, lastAssistantId, headerTitleLabel, renderItem };
}
