/** Queued chat opener — avoids fragile long strings in expo-router params. */
import type { QuizMode } from "@/lib/quizMode";

export type QueuedChatLaunch = {
  prompt?: string;
  dailyQuiz?: boolean;
  projectId?: string;
  quizLanguage?: string;
  quizVariant?: "vocab" | "trivia";
  quizMode?: QuizMode;
};

let queued: QueuedChatLaunch | null = null;

export function queueChatLaunch(
  prompt: string,
  projectId?: string,
  quizLanguage?: string,
  quizVariant?: "vocab" | "trivia",
  quizMode?: QuizMode,
): boolean {
  const trimmed = prompt.trim();
  if (!trimmed) return false;
  queued = {
    prompt: trimmed,
    ...(projectId ? { projectId } : {}),
    ...(quizLanguage ? { quizLanguage } : {}),
    ...(quizVariant ? { quizVariant } : {}),
    ...(quizMode ? { quizMode } : {}),
  };
  return true;
}

/** Open exam mode using pre-generated daily quiz questions (no LLM prompt). */
export function queueDailyQuizLaunch(
  projectId: string,
  quizVariant: "vocab" | "trivia",
  quizLanguage?: string,
): boolean {
  if (!projectId) return false;
  queued = {
    dailyQuiz: true,
    projectId,
    quizVariant,
    quizMode: "exam",
    ...(quizLanguage ? { quizLanguage } : {}),
  };
  return true;
}

export function takeQueuedChatLaunch(): QueuedChatLaunch | null {
  if (!queued) return null;
  const next = queued;
  queued = null;
  return next;
}
