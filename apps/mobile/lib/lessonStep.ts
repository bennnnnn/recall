import type { Message } from "@/lib/api";
import { findActiveQuizMessageId } from "@/lib/chatMessageLogic";
import { stripLearningLaunchBlock } from "@/lib/parseLearningLaunch";
import {
  parseVocabCard,
  stripVocabCardBlock,
  type ParsedVocabCard,
} from "@/lib/parseVocabCard";
import {
  isRenderableVocabQuiz,
  parseVocabQuiz,
  stripVocabQuizBlock,
  type ParsedVocabQuiz,
} from "@/lib/parseVocabQuiz";

export type LessonStep =
  | { kind: "loading" }
  | { kind: "quiz"; quiz: ParsedVocabQuiz; question: string; messageId: string }
  | { kind: "vocab_card"; card: ParsedVocabCard; prompt: string }
  | { kind: "open_ended"; prompt: string }
  | { kind: "idle"; prompt: string };

export function looksLikeOpenEndedPrompt(content: string): boolean {
  return /write (?:your own |a |an )?sentence|use .+ in (?:a |your own )?sentence|what does (?:it|.+) mean|in your own words/i.test(
    content,
  );
}

export function lessonProseFromAssistant(content: string): string {
  return stripLearningLaunchBlock(stripVocabCardBlock(stripVocabQuizBlock(content))).trim();
}

function quizStepFromMessage(message: Message): Extract<LessonStep, { kind: "quiz" }> | null {
  const quiz = parseVocabQuiz(message.content);
  if (!isRenderableVocabQuiz(quiz)) return null;
  return {
    kind: "quiz",
    quiz,
    question:
      quiz.question?.trim() ||
      lessonProseFromAssistant(message.content) ||
      quiz.word,
    messageId: message.id,
  };
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
      const step = quizStepFromMessage(streaming);
      if (step) return step;
      const card = parseVocabCard(streaming.content);
      if (card) {
        return {
          kind: "vocab_card",
          card,
          prompt: lessonProseFromAssistant(streaming.content),
        };
      }
    }
    return { kind: "loading" };
  }

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "assistant" || message.id === "streaming") continue;
    const card = parseVocabCard(message.content);
    if (card) {
      return {
        kind: "vocab_card",
        card,
        prompt: lessonProseFromAssistant(message.content),
      };
    }
    const prose = lessonProseFromAssistant(message.content);
    if (looksLikeOpenEndedPrompt(message.content) && prose) {
      return { kind: "open_ended", prompt: prose };
    }
    if (prose) return { kind: "idle", prompt: prose };
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
