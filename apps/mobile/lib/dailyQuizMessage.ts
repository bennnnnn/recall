import type { Message, ProjectDailyQuiz, ProjectQuizQuestion, QuizModality } from "@/lib/api";

export const DAILY_QUIZ_MSG_PREFIX = "daily-quiz-";
export const DAILY_QUIZ_LOADING_ID = "daily-quiz-loading";

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
  return [
    "```vocab_quiz",
    JSON.stringify({
      word: question.topic,
      part_of_speech: question.part_of_speech ?? undefined,
      question: question.question_text,
      quiz_type: question.quiz_kind === "trivia" ? "trivia" : "vocab",
      choices: question.choices.map((c) => ({ letter: c.letter, text: c.text })),
      daily_progress: progress,
    }),
    "```",
  ].join("\n");
}

const DAILY_QUIZ_TEXT_FENCE_RE = /```daily_quiz_text\s*\n([\s\S]*?)```/i;

export type ParsedDailyQuizText = {
  questionId: string;
  topic: string;
  modality: "definition" | "sentence";
  progress: { done: number; goal: number };
};

export function buildDailyQuizTextContent(
  question: ProjectQuizQuestion,
  modality: "definition" | "sentence",
  progress: { done: number; goal: number },
): string {
  return [
    "```daily_quiz_text",
    JSON.stringify({
      question_id: question.id,
      topic: question.topic,
      modality,
      progress,
    }),
    "```",
  ].join("\n");
}

export function parseDailyQuizText(content: string): ParsedDailyQuizText | null {
  const match = DAILY_QUIZ_TEXT_FENCE_RE.exec(content);
  if (!match) return null;
  try {
    const data = JSON.parse(match[1].trim()) as {
      question_id?: string;
      topic?: string;
      modality?: string;
      progress?: { done?: number; goal?: number };
    };
    const questionId = String(data.question_id ?? "");
    const topic = String(data.topic ?? "").trim();
    const modality = data.modality === "sentence" ? "sentence" : "definition";
    if (!questionId || !topic) return null;
    const done = Number(data.progress?.done ?? 0);
    const goal = Number(data.progress?.goal ?? 0);
    return {
      questionId,
      topic,
      modality,
      progress: { done, goal },
    };
  } catch {
    return null;
  }
}

export function hasDailyQuizTextFence(content: string): boolean {
  return /```daily_quiz_text/i.test(content);
}

export function buildDailyQuizMessage(
  question: ProjectQuizQuestion,
  session: ProjectDailyQuiz,
  modality: QuizModality,
): Message {
  const progress = { done: session.answered_count, goal: session.daily_goal };
  const content =
    modality === "mcq"
      ? buildDailyQuizMcqContent(question, progress)
      : buildDailyQuizTextContent(question, modality, progress);

  return {
    id: dailyQuizMessageId(question.id),
    role: "assistant",
    content,
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
