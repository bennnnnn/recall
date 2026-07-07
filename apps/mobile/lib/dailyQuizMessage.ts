import type { Message, ProjectDailyQuiz, ProjectQuizQuestion, QuizModality } from "@/lib/api";

export const DAILY_QUIZ_MSG_PREFIX = "daily-quiz-";
export const DAILY_QUIZ_LOADING_ID = "daily-quiz-loading";
export const DAILY_QUIZ_ERROR_ID = "daily-quiz-error";
export const DAILY_QUIZ_EMPTY_ID = "daily-quiz-empty";
export const DAILY_QUIZ_DONE_ID = "daily-quiz-done";

export function isDailyQuizMessageId(id: string): boolean {
  return id.startsWith(DAILY_QUIZ_MSG_PREFIX);
}

export function dailyQuizMessageId(questionId: string): string {
  return `${DAILY_QUIZ_MSG_PREFIX}${questionId}`;
}

export function questionIdFromDailyQuizMessageId(messageId: string): string | null {
  if (!messageId.startsWith(DAILY_QUIZ_MSG_PREFIX)) return null;
  const rest = messageId.slice(DAILY_QUIZ_MSG_PREFIX.length);
  if (!rest || rest === "loading") return null;
  return rest;
}

export function buildDailyQuizMcqContent(
  question: ProjectQuizQuestion,
  progress: { done: number; goal: number },
): string {
  const pos = question.part_of_speech ? ` · _${question.part_of_speech}_` : "";
  const header =
    question.quiz_kind === "trivia"
      ? `**${question.topic}**`
      : `**${question.topic}**${pos}`;
  return [
    `**${progress.done} / ${progress.goal} correct today**`,
    "",
    header,
    "",
    question.question_text,
    "",
    ...question.choices.map((c) => `**${c.letter})** ${c.text}`),
    "",
    "Reply with **A**, **B**, **C**, or **D**.",
  ].join("\n");
}

export function parseDailyQuizLetterReply(text: string): "A" | "B" | "C" | "D" | null {
  const trimmed = text.trim();
  const match = /^([A-Da-d])\)?$/.exec(trimmed);
  if (!match) return null;
  return match[1].toUpperCase() as "A" | "B" | "C" | "D";
}

export function buildDailyQuizMessage(
  question: ProjectQuizQuestion,
  session: ProjectDailyQuiz,
  _modality: QuizModality,
): Message {
  const progress = { done: session.answered_count, goal: session.daily_goal };
  return {
    id: dailyQuizMessageId(question.id),
    role: "assistant",
    content: buildDailyQuizMcqContent(question, progress),
    model: null,
    created_at: new Date().toISOString(),
  };
}

export function buildDailyQuizLoadingMessage(): Message {
  return {
    id: DAILY_QUIZ_LOADING_ID,
    role: "assistant",
    content: "",
    model: null,
    created_at: new Date().toISOString(),
  };
}

function statusMessage(id: string, content: string): Message {
  return {
    id,
    role: "assistant",
    content,
    model: null,
    created_at: new Date().toISOString(),
  };
}

export function buildDailyQuizErrorMessage(text: string): Message {
  return statusMessage(DAILY_QUIZ_ERROR_ID, text);
}

export function buildDailyQuizEmptyMessage(text: string): Message {
  return statusMessage(DAILY_QUIZ_EMPTY_ID, text);
}

export function buildDailyQuizDoneMessage(text: string): Message {
  return statusMessage(DAILY_QUIZ_DONE_ID, text);
}

export function isDailyQuizStatusMessageId(id: string): boolean {
  return (
    id === DAILY_QUIZ_LOADING_ID ||
    id === DAILY_QUIZ_ERROR_ID ||
    id === DAILY_QUIZ_EMPTY_ID ||
    id === DAILY_QUIZ_DONE_ID
  );
}
