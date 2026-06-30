import React, { memo } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import type { Message } from "@/lib/api";
import type { StreamingDraft } from "@/hooks/useChat";
import type { QuizChoice } from "@/lib/parseVocabQuiz";

type Props = {
  item: Message;
  index: number;
  messages: Message[];
  streaming: boolean;
  streamingDraft: StreamingDraft | null;
  lastAssistantId: string | null;
  selectedModel: string;
  quizLanguage: string;
  quizAnswers: Partial<Record<string, QuizChoice["letter"]>>;
  highlightedMessageId: string | null;
  quizDisabled: boolean;
  onRegenerate: (model: string) => void;
  onEdit: (message: Message) => void;
  onFeedback: (messageId: string, next: "up" | "down" | null) => void;
  onQuizAnswer: (messageId: string, letter: "A" | "B" | "C" | "D") => void;
};

export const ChatMessageRow = memo(function ChatMessageRow({
  item,
  index,
  messages,
  streaming,
  streamingDraft,
  lastAssistantId,
  selectedModel,
  quizLanguage,
  quizAnswers,
  highlightedMessageId,
  quizDisabled,
  onRegenerate,
  onEdit,
  onFeedback,
  onQuizAnswer,
}: Props) {
  const priorUserText =
    item.role === "assistant" && index > 0 && messages[index - 1]?.role === "user"
      ? messages[index - 1].content
      : null;
  const isStreamingItem = item.id === "streaming";
  const isLastAssistant = item.role === "assistant" && item.id === lastAssistantId;

  return (
    <MessageBubble
      message={item}
      priorUserText={priorUserText}
      isGenerating={streaming && isStreamingItem}
      liveContent={isStreamingItem ? streamingDraft?.content : undefined}
      liveSearchSources={isStreamingItem ? streamingDraft?.search_sources : undefined}
      isLastAssistant={isLastAssistant}
      onRegenerate={
        isLastAssistant && !streaming ? () => onRegenerate(selectedModel) : undefined
      }
      onEdit={onEdit}
      canEdit={item.role === "user" && !streaming && !item.id.startsWith("local-")}
      onFeedback={onFeedback}
      onQuizAnswer={
        isLastAssistant && !streaming ? onQuizAnswer : undefined
      }
      quizDisabled={quizDisabled}
      quizLanguage={quizLanguage}
      quizSelectedLetter={quizAnswers[item.id] ?? null}
      highlighted={item.id === highlightedMessageId}
    />
  );
});
