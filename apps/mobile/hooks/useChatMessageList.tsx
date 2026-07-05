import { useCallback, useEffect, useMemo } from "react";

import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import { DailyQuizLoadingRow } from "@/components/chat/DailyQuizLoadingRow";
import { DailyQuizTextRow } from "@/components/chat/DailyQuizTextRow";
import { StreamingChatMessageRow } from "@/components/chat/StreamingChatMessageRow";
import type { Message, ProjectQuizQuestion, QuizModality } from "@/lib/api";
import { findLastAssistantId, priorUserTextFor } from "@/lib/chatMessageLogic";
import {
  DAILY_QUIZ_LOADING_ID,
  hasDailyQuizTextFence,
  parseDailyQuizText,
  questionIdFromDailyQuizMessageId,
} from "@/lib/dailyQuizMessage";
import { inferQuizAnswersFromMessages } from "@/lib/parseVocabQuiz";

type DailyQuizRowProps = {
  active: boolean;
  submitting: boolean;
  allowRetry: boolean;
  currentQuestion: ProjectQuizQuestion | null;
  onModalityChange: (modality: QuizModality) => void;
  onTextAnswer: (question: ProjectQuizQuestion, text: string, modality: "definition" | "sentence") => void;
  onSkip: (question: ProjectQuizQuestion) => void;
};

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
  dailyQuizRow?: DailyQuizRowProps;
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
  dailyQuizRow,
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

  const headerTitleLabel = null;

  const quizDisabled =
    streaming || finalizing || creatingRef.current || Boolean(dailyQuizRow?.submitting);

  const sharedRowProps = useMemo(
    () => ({
      streaming,
      finalizing,
      lastAssistantId,
      selectedModel,
      quizLanguage,
      quizVariant,
      quizAnswers,
      highlightedMessageId,
      sendingMessageId,
      quizDisabled,
      onRegenerate: regenerateResponse,
      onEdit: handleEditMessage,
      onFeedback: handleFeedback,
      onQuizAnswer: handleQuizAnswer,
    }),
    [
      streaming,
      finalizing,
      lastAssistantId,
      selectedModel,
      quizLanguage,
      quizVariant,
      quizAnswers,
      highlightedMessageId,
      sendingMessageId,
      quizDisabled,
      regenerateResponse,
      handleEditMessage,
      handleFeedback,
      handleQuizAnswer,
    ],
  );

  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) => {
      if (item.id === DAILY_QUIZ_LOADING_ID) {
        return <DailyQuizLoadingRow quizVariant={quizVariant} />;
      }

      if (hasDailyQuizTextFence(item.content)) {
        const parsed = parseDailyQuizText(item.content);
        if (parsed) {
          const question =
            dailyQuizRow?.currentQuestion?.id === parsed.questionId
              ? dailyQuizRow.currentQuestion
              : ({
                  id: parsed.questionId,
                  sequence: 0,
                  quiz_kind: "vocab",
                  topic: parsed.topic,
                  part_of_speech: null,
                  question_text: "",
                  choices: [],
                  status: "answered",
                  allowed_modalities: ["definition", "sentence"],
                } satisfies ProjectQuizQuestion);
          return (
            <DailyQuizTextRow
              parsed={parsed}
              question={question}
              submitting={dailyQuizRow?.submitting ?? false}
              allowRetry={dailyQuizRow?.allowRetry ?? false}
              active={
                Boolean(dailyQuizRow?.active) &&
                item.id === lastAssistantId &&
                dailyQuizRow?.currentQuestion?.id === parsed.questionId
              }
              onModalityChange={dailyQuizRow?.onModalityChange ?? (() => {})}
              onTextAnswer={(text, modality) =>
                dailyQuizRow?.onTextAnswer(question, text, modality)
              }
              onSkip={() => dailyQuizRow?.onSkip(question)}
            />
          );
        }
      }

      const priorUserText = priorUserTextFor(messages, index);

      return item.id === "streaming" ? (
        <StreamingChatMessageRow item={item} priorUserText={priorUserText} {...sharedRowProps} />
      ) : (
        <ChatMessageRow item={item} priorUserText={priorUserText} {...sharedRowProps} />
      );
    },
    [sharedRowProps, dailyQuizRow, lastAssistantId, quizVariant, messages],
  );

  return { quizAnswers, lastAssistantId, headerTitleLabel, renderItem };
}
