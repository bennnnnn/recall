/**
 * Lesson cards the model writes as JSON fences.
 *
 * ```quiz {"question": "...", "options": ["...", "..."], "answer": 1, "explanation": "..."}
 * ```array {"name": "nums", "values": [2, 7, 11, 15], "highlight": [0, 1]}
 *
 * Both parse to null when the fence is not usable, so the card can say so.
 */

export type QuizFence = {
  question: string;
  options: string[];
  /** 0-based index into `options`. */
  answer: number;
  explanation: string;
};

export type ArrayValue = string | number | boolean | null;

export type ArrayFence = {
  name: string | null;
  values: ArrayValue[];
  highlight: number[];
};

const MAX_OPTIONS = 6;
const MAX_CELLS = 24;
const LETTERS = "ABCDEF";

function parseObject(content: string): Record<string, unknown> | null {
  let raw: unknown;
  try {
    raw = JSON.parse(content);
  } catch {
    return null;
  }
  return raw && typeof raw === "object" && !Array.isArray(raw)
    ? (raw as Record<string, unknown>)
    : null;
}

function trimmed(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** The answer as an index: 1, "1", "B", "B)" or the option's own text. */
function answerIndex(answer: unknown, options: string[]): number {
  if (typeof answer === "number" && Number.isInteger(answer)) return answer;
  const text = trimmed(answer);
  if (/^\d+$/.test(text)) return Number(text);
  const letter = text.match(/^([A-F])[).:]?$/i);
  if (letter) return LETTERS.indexOf(letter[1]!.toUpperCase());
  return options.findIndex((option) => option === text);
}

export function parseQuizFence(content: string): QuizFence | null {
  const data = parseObject(content);
  if (!data) return null;
  const question = trimmed(data.question);
  const options = Array.isArray(data.options)
    ? data.options.map((option) => (typeof option === "number" ? String(option) : trimmed(option)))
    : [];
  if (!question || options.length < 2 || options.length > MAX_OPTIONS) return null;
  if (options.some((option) => !option)) return null;
  const answer = answerIndex(data.answer, options);
  if (answer < 0 || answer >= options.length) return null;
  return { question, options, answer, explanation: trimmed(data.explanation) };
}

function isCell(value: unknown): value is ArrayValue {
  return (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean" ||
    (typeof value === "number" && Number.isFinite(value))
  );
}

export function parseArrayFence(content: string): ArrayFence | null {
  const data = parseObject(content);
  if (!data || !Array.isArray(data.values)) return null;
  const values = data.values;
  if (values.length === 0 || values.length > MAX_CELLS || !values.every(isCell)) return null;
  const highlight = Array.isArray(data.highlight)
    ? data.highlight.filter(
        (index): index is number =>
          Number.isInteger(index) && (index as number) >= 0 && (index as number) < values.length,
      )
    : [];
  return { name: trimmed(data.name) || null, values, highlight };
}

/** How a cell reads: strings quoted, the rest as written. */
export function formatCell(value: ArrayValue): string {
  return typeof value === "string" ? JSON.stringify(value) : String(value);
}

/** "nums = [2, 7, 11, 15]" for copy and speech. */
export function arrayText(fence: ArrayFence): string {
  const list = `[${fence.values.map(formatCell).join(", ")}]`;
  return fence.name ? `${fence.name} = ${list}` : list;
}

/** The question and lettered options as plain text, for copy and speech. */
export function quizText(fence: QuizFence): string {
  const options = fence.options.map((option, i) => `${LETTERS[i]}) ${option}`);
  return [fence.question, ...options].join("\n");
}
