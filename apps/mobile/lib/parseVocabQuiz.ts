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
};

export function isCompleteVocabQuiz(quiz: ParsedVocabQuiz | null): quiz is ParsedVocabQuiz {
  return quiz != null && quiz.choices.length === 4;
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
    if (msg.role !== "assistant" || !isCompleteVocabQuiz(parseVocabQuiz(msg.content))) {
      continue;
    }
    const next = messages[i + 1];
    if (next.role !== "user") continue;
    const letter = parseQuizAnswerLetter(next.content);
    if (letter) answers[msg.id] = letter;
  }
  return answers;
}

const CHOICE_LINE = /^([A-D])\)\s*(.+)$/i;
const VOCAB_QUIZ_FENCE_RE = /```vocab_quiz\s*\n([\s\S]*?)```/i;
const QUESTION_LINE =
  /^(?:What does it mean\??|Choose the best meaning:?|Which definition is correct:?)\s*$/i;

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
  if (!content.includes("```vocab_quiz")) return null;
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
    if (choices.length < 2) return null;
    const correctRaw = String(data.correct ?? "").toUpperCase();
    const correct = /^[A-D]$/.test(correctRaw)
      ? (correctRaw as QuizChoice["letter"])
      : undefined;
    return {
      word: word || question?.slice(0, 40) || "Trivia",
      partOfSpeech: quizType === "trivia" ? undefined : data.part_of_speech?.trim() || undefined,
      question,
      correct,
      choices,
      quizType,
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
  if (!wordInfo) return null;

  return {
    word: wordInfo.word,
    partOfSpeech: wordInfo.partOfSpeech,
    question: extractQuestion(lines, wordInfo.headerLine, block.startLine),
    choices: block.choices,
  };
}

export function parseVocabQuiz(content: string): ParsedVocabQuiz | null {
  return parseVocabQuizFence(content) ?? parseVocabQuizMarkdown(content);
}

/** Intro/feedback text without the interactive quiz block. */
export function stripVocabQuizBlock(content: string): string {
  let stripped = content.replace(VOCAB_QUIZ_FENCE_RE, "").trim();

  const lines = stripped.split("\n");
  const blocks = findChoiceBlocks(lines);
  if (blocks.length === 0) return stripped.trim();

  const block = blocks[blocks.length - 1];
  const wordInfo = extractWordAbove(lines, block.startLine);
  const stripFrom = wordInfo?.headerLine ?? block.startLine;

  const kept = lines.slice(0, stripFrom);
  return kept.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}
