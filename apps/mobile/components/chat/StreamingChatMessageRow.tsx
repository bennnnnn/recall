import React, { memo } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import { useStreamingDraft } from "@/contexts/StreamingDraftContext";
import type { Message } from "@/lib/api";
import type { QuizChoice } from "@/lib/parseVocabQuiz";

type Props = {
  item: Message;
  index: number;
  messages: Message[];
  streaming: boolean;
  finalizing: boolean;
  lastAssistantId: string | null;
  selectedModel: string;
  quizLanguage: string;
  quizVariant: "vocab" | "trivia";
  quizAnswers: Partial<Record<string, QuizChoice["letter"]>>;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  quizDisabled: boolean;
  onRegenerate: (model: string) => void;
  onEdit: (message: Message) => void;
  onFeedback: (messageId: string, next: "up" | "down" | null) => void;
  onQuizAnswer: (
    messageId: string,
    letter: "A" | "B" | "C" | "D",
    meta?: import("@/lib/parseVocabQuiz").QuizAnswerMeta,
  ) => void;
};

export const StreamingChatMessageRow = memo(function StreamingChatMessageRow({
  item,
  index,
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
  quizDisabled,
  onRegenerate,
  onEdit,
  onFeedback,
  onQuizAnswer,
}: Props) {
  const streamingDraft = useStreamingDraft();
  const priorUserText =
    item.role === "assistant" && index > 0 && messages[index - 1]?.role === "user"
      ? messages[index - 1].content
      : null;
  const isLastAssistant = item.role === "assistant" && item.id === lastAssistantId;
  const streamVisualActive = streaming || finalizing;

  return (
    <MessageBubble
      message={item}
      priorUserText={priorUserText}
      isGenerating={streamVisualActive}
      liveContent={streamingDraft?.content}
      liveSearchSources={streamingDraft?.search_sources}
      liveReasoning={streamingDraft?.reasoning}
      streamStatus={streamingDraft?.status}
      isLastAssistant={isLastAssistant}
      onRegenerate={
        isLastAssistant && !streamVisualActive ? () => onRegenerate(selectedModel) : undefined
      }
      onEdit={onEdit}
      canEdit={item.role === "user" && !streamVisualActive && !item.id.startsWith("local-")}
      onFeedback={onFeedback}
      onQuizAnswer={
        isLastAssistant && !streamVisualActive ? onQuizAnswer : undefined
      }
      quizDisabled={quizDisabled}
      quizLanguage={quizLanguage}
      quizVariant={quizVariant}
      quizSelectedLetter={quizAnswers[item.id] ?? null}
      highlighted={item.id === highlightedMessageId}
      isSending={item.id === sendingMessageId}
    />
  );
});
