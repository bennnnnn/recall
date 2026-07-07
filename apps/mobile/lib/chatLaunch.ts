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
    quizMode: quizMode ?? "chat",
  };
  return true;
}

/** @deprecated Use queueChatLaunch with a prompt — daily quiz runs in chat now. */
export function queueDailyQuizLaunch(
  projectId: string,
  quizVariant: "vocab" | "trivia",
  quizLanguage?: string,
  prompt?: string,
): boolean {
  if (!projectId) return false;
  const fallback =
    quizVariant === "trivia"
      ? "Continue my daily general-knowledge session in chat. Ask the next question — you pick the format."
      : "Continue my daily vocabulary session in chat. Teach or quiz the next word — you pick the format.";
  return queueChatLaunch(
    prompt?.trim() || fallback,
    projectId,
    quizLanguage,
    quizVariant,
    "chat",
  );
}

export function takeQueuedChatLaunch(): QueuedChatLaunch | null {
  if (!queued) return null;
  const next = queued;
  queued = null;
  return next;
}
