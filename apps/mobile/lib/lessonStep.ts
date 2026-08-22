import type { Message } from "@/lib/api";
import { findActiveQuizMessageId } from "@/lib/chatMessageLogic";
import { stripLearningLaunchBlock } from "@/lib/parseLearningLaunch";
import { parseVocabCard, stripVocabCardBlock, type ParsedVocabCard } from "@/lib/parseVocabCard";
import {
  isRenderableVocabQuiz,
  parseVocabQuiz,
  stripVocabQuizBlock,
  type ParsedVocabQuiz,
} from "@/lib/parseVocabQuiz";

export type LessonStep =
  | { kind: "loading" }
  | { kind: "quiz"; quiz: ParsedVocabQuiz; question: string; messageId: string }
  | { kind: "vocab_card"; card: ParsedVocabCard };

export function lessonProseFromAssistant(content: string): string {
  return stripLearningLaunchBlock(stripVocabCardBlock(stripVocabQuizBlock(content))).trim();
}

function quizStepFromMessage(message: Message): Extract<LessonStep, { kind: "quiz" }> | null {
  const quiz = parseVocabQuiz(message.content);
  if (!isRenderableVocabQuiz(quiz)) return null;
  return {
    kind: "quiz",
    quiz,
    question: quiz.question?.trim() || quiz.word,
    messageId: message.id,
  };
}

function cardStepFromContent(content: string): Extract<LessonStep, { kind: "vocab_card" }> | null {
  const card = parseVocabCard(content);
  if (!card) return null;
  return { kind: "vocab_card", card };
}

export function deriveLessonStep(
  messages: Message[],
  options?: { streaming?: boolean },
): LessonStep {
  const activeId = findActiveQuizMessageId(messages);
  if (activeId) {
    const active = messages.find((message) => message.id === activeId);
    if (active) {
      const step = quizStepFromMessage(active);
      if (step) return step;
    }
  }

  if (options?.streaming) {
    const streaming = messages.find((message) => message.id === "streaming");
    if (streaming) {
      const quiz = quizStepFromMessage(streaming);
      if (quiz) return quiz;
      const card = cardStepFromContent(streaming.content);
      if (card) return card;
    }
    return { kind: "loading" };
  }

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "assistant" || message.id === "streaming") continue;
    const quiz = quizStepFromMessage(message);
    if (quiz) return quiz;
    const card = cardStepFromContent(message.content);
    if (card) return card;
  }

  return { kind: "loading" };
}

export function latestAssistantProse(messages: Message[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "assistant" || message.id === "streaming") continue;
    return lessonProseFromAssistant(message.content);
  }
  return "";
}
