export type QuizChoice = { letter: "A" | "B" | "C" | "D"; text: string };

export type QuizAnswerMeta = {
  topic: string;
  question: string;
  isCorrect: boolean | null;
};

export type ParsedVocabQuiz = {
  word: string;
  partOfSpeech?: string;
  question?: string;
  correct?: QuizChoice["letter"];
  choices: QuizChoice[];
  quizType?: "vocab" | "trivia";
  dailyProgress?: { done: number; goal: number };
};

export function isRenderableVocabQuiz(quiz: ParsedVocabQuiz | null): quiz is ParsedVocabQuiz {
  if (quiz == null || quiz.choices.length !== 4) return false;
  if (quiz.quizType === "trivia") {
    return Boolean(quiz.question?.trim() || quiz.word.trim());
  }
  return Boolean(quiz.word.trim());
}

export function isCompleteVocabQuiz(quiz: ParsedVocabQuiz | null): quiz is ParsedVocabQuiz {
  return (
    isRenderableVocabQuiz(quiz) &&
    quiz.correct != null &&
    /^[A-D]$/.test(quiz.correct)
  );
}

/** Single-letter reply sent when the user taps a quiz choice. */
export function isVocabQuizAnswer(content: string): boolean {
  return /^[A-D]\.?$/i.test(content.trim());
}

export function parseQuizAnswerLetter(
  content: string,
): QuizChoice["letter"] | null {
  const match = content.trim().match(/^([A-D])\.?$/i);
  return match ? (match[1].toUpperCase() as QuizChoice["letter"]) : null;
}

/** Map assistant quiz message ids → the user's chosen letter (from chat history). */
export function inferQuizAnswersFromMessages(
  messages: Array<{ id: string; role: string; content: string }>,
): Partial<Record<string, QuizChoice["letter"]>> {
  const answers: Partial<Record<string, QuizChoice["letter"]>> = {};
  for (let i = 0; i < messages.length - 1; i++) {
    const msg = messages[i];
    if (msg.role !== "assistant" || !isRenderableVocabQuiz(parseVocabQuiz(msg.content))) {
      continue;
    }
    const next = messages[i + 1];
    if (next.role !== "user") continue;
    const letter = parseQuizAnswerLetter(next.content);
    if (letter) answers[msg.id] = letter;
  }
  return answers;
}

const CHOICE_LINE = /^([A-D])[\).:]\s*(.+)$/i;
const VOCAB_QUIZ_FENCE_RE = /```vocab_quiz\s*\n([\s\S]*?)```/i;
const VOCAB_QUIZ_FENCE_PARTIAL_RE = /```vocab_quiz[\s\S]*$/i;
const VOCAB_SESSION_JSON_FENCE_RE = /```json\s*\n([\s\S]*?)```/gi;
const VOCAB_SESSION_JSON_PARTIAL_RE = /```json[\s\S]*$/i;
const SESSION_METADATA_KEYS = new Set([
  "session_complete",
  "sessionComplete",
  "words_learned",
  "wordsLearned",
  "daily_goal_met",
  "dailyGoalMet",
]);
const QUESTION_LINE =
  /^(?:What does it mean\??|Choose the best meaning:?|Which definition is correct:?)\s*$/i;
const QUIZ_ANSWER_PROMPT_LINE =
  /^\(?\s*Answer\s+[A-D](?:\s*,\s*(?:or\s+)?[A-D])*\s*[!?).]/i;

/** Strip markdown bold markers the model sometimes leaves on quiz words. */
export function cleanQuizWord(raw: string): string {
  return raw
    .replace(/\*\*/g, "")
    .replace(/^\*+|\*+$/g, "")
    .trim();
}

type ChoiceBlock = {
  choices: QuizChoice[];
  startLine: number;
  endLine: number;
};

function parseVocabQuizFence(content: string): ParsedVocabQuiz | null {
  if (!hasVocabQuizFence(content)) return null;
  const match = VOCAB_QUIZ_FENCE_RE.exec(content);
  if (!match) return null;
  try {
    const data = JSON.parse(match[1].trim()) as {
      word?: string;
      part_of_speech?: string;
      question?: string;
      correct?: string;
      quiz_type?: string;
      quizType?: string;
      daily_progress?: { done?: number; goal?: number };
      choices?: Array<{ letter?: string; text?: string }>;
    };
    const quizTypeRaw = String(data.quiz_type ?? data.quizType ?? "").toLowerCase();
    const quizType =
      quizTypeRaw === "trivia" ? "trivia" : quizTypeRaw === "vocab" ? "vocab" : undefined;
    const word = cleanQuizWord(String(data.word ?? ""));
    const question = data.question?.trim() || undefined;
    if (quizType === "trivia") {
      if (!question && !word) return null;
    } else if (!word) {
      return null;
    }
    if (!Array.isArray(data.choices)) return null;
    const choices: QuizChoice[] = [];
    for (const item of data.choices) {
      const letter = String(item.letter ?? "").toUpperCase();
      const text = String(item.text ?? "").trim();
      if (!/^[A-D]$/.test(letter) || !text) continue;
      choices.push({ letter: letter as QuizChoice["letter"], text });
    }
    if (choices.length < 4) return null;
    const correctRaw = String(data.correct ?? "").toUpperCase();
    const correct = /^[A-D]$/.test(correctRaw)
      ? (correctRaw as QuizChoice["letter"])
      : undefined;
    const progressRaw = data.daily_progress;
    const dailyProgress =
      progressRaw && typeof progressRaw.done === "number" && typeof progressRaw.goal === "number"
        ? { done: progressRaw.done, goal: progressRaw.goal }
        : undefined;
    return {
      word: word || question?.slice(0, 40) || "Trivia",
      partOfSpeech: quizType === "trivia" ? undefined : data.part_of_speech?.trim() || undefined,
      question,
      correct,
      choices,
      quizType,
      dailyProgress,
    };
  } catch {
    return null;
  }
}

function findChoiceBlocks(lines: string[]): ChoiceBlock[] {
  const blocks: ChoiceBlock[] = [];
  let current: QuizChoice[] = [];
  let blockStart = -1;

  const flush = (endLine: number) => {
    if (current.length >= 2) {
      blocks.push({ choices: current, startLine: blockStart, endLine });
    }
    current = [];
    blockStart = -1;
  };

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].trim().match(CHOICE_LINE);
    if (match) {
      if (current.length === 0) blockStart = i;
      current.push({
        letter: match[1].toUpperCase() as QuizChoice["letter"],
        text: match[2].trim(),
      });
      continue;
    }
    if (current.length > 0) flush(i - 1);
  }
  if (current.length > 0) flush(lines.length - 1);
  return blocks;
}

function extractWordAbove(lines: string[], choiceStartLine: number): {
  word: string;
  partOfSpeech?: string;
  headerLine: number;
} | null {
  for (let i = choiceStartLine - 1; i >= Math.max(0, choiceStartLine - 10); i--) {
    const line = lines[i].trim();
    if (!line) continue;

    const wordMatch = line.match(
      /(?:\*\*Word:\*\*|Word:)\s*([^[\n]+?)(?:\s*\[([^\]]+)\])?\s*$/i,
    );
    if (wordMatch) {
      const word = cleanQuizWord(wordMatch[1]);
      if (!word) continue;
      return {
        word,
        partOfSpeech: wordMatch[2]?.trim(),
        headerLine: i,
      };
    }

    const boldWord = line.match(/^\*\*([^*\n]+)\*\*$/);
    if (boldWord) {
      const candidate = cleanQuizWord(boldWord[1]);
      if (candidate && candidate.split(/\s+/).length <= 2) {
        return { word: candidate, headerLine: i };
      }
    }
  }
  return null;
}

function extractQuestion(lines: string[], headerLine: number, choiceStartLine: number): string | undefined {
  for (let i = headerLine + 1; i < choiceStartLine; i++) {
    const line = lines[i].trim();
    if (QUESTION_LINE.test(line)) return line;
  }
  return undefined;
}

function parseVocabQuizMarkdown(content: string): ParsedVocabQuiz | null {
  const lines = content.split("\n");
  const blocks = findChoiceBlocks(lines);
  if (blocks.length === 0) return null;

  const block = blocks[blocks.length - 1];
  const wordInfo = extractWordAbove(lines, block.startLine);
  if (wordInfo) {
    return {
      word: wordInfo.word,
      partOfSpeech: wordInfo.partOfSpeech,
      question: extractQuestion(lines, wordInfo.headerLine, block.startLine),
      choices: block.choices,
    };
  }

  const trivia = extractTriviaAboveChoices(lines, block.startLine);
  if (!trivia) return null;

  return {
    word: trivia.topic,
    question: trivia.question,
    choices: block.choices,
    quizType: "trivia",
  };
}

export function hasVocabQuizFence(content: string): boolean {
  return /```vocab_quiz/i.test(content);
}

function extractTriviaAboveChoices(
  lines: string[],
  choiceStartLine: number,
): { topic: string; question: string; stripFromLine: number } | null {
  let topic = "Trivia";
  let question: string | null = null;
  let stripFromLine = choiceStartLine;
  let hasNextLine = false;

  for (let i = choiceStartLine - 1; i >= Math.max(0, choiceStartLine - 15); i--) {
    const line = lines[i].trim();
    if (!line) continue;

    const nextMatch = line.match(/^Next:\s*\*\*([^*]+)\*\*/i);
    if (nextMatch) {
      topic = cleanQuizWord(nextMatch[1]);
      stripFromLine = Math.min(stripFromLine, i);
      hasNextLine = true;
      continue;
    }

    if (QUIZ_ANSWER_PROMPT_LINE.test(line)) {
      stripFromLine = Math.min(stripFromLine, i);
      continue;
    }

    const boldLine = line.match(/^\*\*([^*\n]+)\*\*$/);
    if (boldLine) {
      const text = cleanQuizWord(boldLine[1]);
      if (/[?？]$/.test(text) || /^(which|what|who|where|when|how|name)\b/i.test(text)) {
        question = text;
        stripFromLine = Math.min(stripFromLine, i);
        continue;
      }
    }

    const plain = cleanQuizWord(line.replace(/\*\*/g, ""));
    if (/[?？]$/.test(plain) && plain.length >= 12) {
      question = plain;
      stripFromLine = Math.min(stripFromLine, i);
      continue;
    }
  }

  if (!question || !hasNextLine) return null;
  return { topic, question, stripFromLine };
}

export function parseVocabQuiz(content: string): ParsedVocabQuiz | null {
  return parseVocabQuizFence(content) ?? parseVocabQuizMarkdown(content);
}

function normalizeQuizText(text: string): string {
  return text
    .replace(/\*\*/g, "")
    .replace(/[_*`~]/g, "")
    .replace(/[\u2018\u2019\u201A\u201B'""`]/g, "")
    .replace(/\s+/g, " ")
    .replace(/[?!.,:;…]+$/g, "")
    .trim()
    .toLowerCase();
}

function lineMatchesQuizQuestion(line: string, questionNorm: string): boolean {
  const lineNorm = normalizeQuizText(line);
  if (!lineNorm || !questionNorm) return false;
  if (lineNorm === questionNorm) return true;
  if (questionNorm.length >= 12) {
    return lineNorm.includes(questionNorm) || questionNorm.includes(lineNorm);
  }
  return false;
}

function isQuizIntroLine(line: string, quiz: ParsedVocabQuiz): boolean {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (CHOICE_LINE.test(trimmed)) return true;
  if (QUIZ_ANSWER_PROMPT_LINE.test(trimmed)) return true;
  const questionNorm = quiz.question ? normalizeQuizText(quiz.question) : null;
  if (questionNorm && lineMatchesQuizQuestion(trimmed, questionNorm)) return true;
  if (quiz.quizType !== "trivia") {
    const wordMatch = trimmed.match(
      /(?:\*\*Word:\*\*|Word:)\s*([^[\n]+?)(?:\s*\[([^\]]+)\])?\s*$/i,
    );
    if (wordMatch && cleanQuizWord(wordMatch[1]) === cleanQuizWord(quiz.word)) {
      return true;
    }
    if (QUESTION_LINE.test(trimmed)) return true;
  }
  return false;
}

function stripQuizIntroLines(lines: string[], quiz: ParsedVocabQuiz): string[] {
  return lines.filter((line) => !isQuizIntroLine(line, quiz));
}

/** Remove quiz question/choices/prompts already shown in the quiz card. */
export function stripQuizMarkdownDuplicates(
  content: string,
  quiz: ParsedVocabQuiz,
): string {
  const lines = content.split("\n");
  return stripQuizIntroLines(lines, quiz).join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function isVocabSessionMetadata(data: unknown): boolean {
  if (!data || typeof data !== "object" || Array.isArray(data)) return false;
  return Object.keys(data as Record<string, unknown>).some((key) =>
    SESSION_METADATA_KEYS.has(key),
  );
}

/** Hide ```json session summary blocks the model sometimes emits after daily vocab sessions. */
export function stripVocabSessionMetadata(content: string): string {
  let stripped = content.replace(VOCAB_SESSION_JSON_FENCE_RE, (block, jsonBody: string) => {
    try {
      const data = JSON.parse(jsonBody.trim()) as unknown;
      return isVocabSessionMetadata(data) ? "" : block;
    } catch {
      return block;
    }
  });

  const partial = VOCAB_SESSION_JSON_PARTIAL_RE.exec(stripped);
  if (
    partial &&
    /session_complete|sessionComplete|words_learned|wordsLearned|daily_goal_met|dailyGoalMet/i.test(
      partial[0],
    )
  ) {
    stripped = stripped.slice(0, partial.index).trimEnd();
  }

  return stripped.replace(/\n{3,}/g, "\n\n").trim();
}

/** Intro/feedback text without the interactive quiz block (incl. partial fences while streaming). */
export function stripVocabQuizBlock(content: string): string {
  let stripped = stripVocabSessionMetadata(content);
  const fromFence = hasVocabQuizFence(stripped);
  const parsed = parseVocabQuiz(stripped);

  stripped = stripped.replace(VOCAB_QUIZ_FENCE_RE, "");
  stripped = stripped.replace(VOCAB_QUIZ_FENCE_PARTIAL_RE, "").trimEnd();

  const lines = stripped.split("\n");

  if (fromFence && parsed && isCompleteVocabQuiz(parsed)) {
    const kept = stripQuizIntroLines(lines, parsed);
    return kept.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  }

  const blocks = findChoiceBlocks(lines);
  if (blocks.length === 0) return stripped.trim();

  const block = blocks[blocks.length - 1];
  if (parsed && isCompleteVocabQuiz(parsed) && parsed.quizType === "trivia") {
    const trivia = extractTriviaAboveChoices(lines, block.startLine);
    const stripFrom = trivia?.stripFromLine ?? block.startLine;
    const kept = lines.slice(0, stripFrom);
    return kept.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  }

  const wordInfo = extractWordAbove(lines, block.startLine);
  const stripFrom = wordInfo?.headerLine ?? block.startLine;

  const kept = lines.slice(0, stripFrom);
  return kept.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}
