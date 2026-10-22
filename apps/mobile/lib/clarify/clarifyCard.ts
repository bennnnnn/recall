/**
 * The ```clarify card a reply asks with (docs/clarify.md): read from its JSON, and the
 * user's picks written back as their next message.
 *
 * The server checks the card before it is saved (apps/api/app/modules/chat/clarify_card.py)
 * and reads the picks the next turn (clarify_turn.answers_card): one "Label: pick" line per
 * question, the label exactly as the card has it. This reader is lenient where the server
 * already normalised, and strict where a wrong shape would draw a broken card.
 */
import { parseJsonRecord } from "@/lib/jsonFence";

export type ClarifyQuestion = {
  id: string;
  /** The short name the sent message uses ("Studied it before"). */
  label: string;
  /** What the card shows ("Have you studied integrals before?"). */
  question: string;
  options: string[];
  multi: boolean;
};

export type ClarifyCard = {
  /** "first": no answer yet; "after": under an answer, to tailor it. */
  when: "first" | "after";
  questions: ClarifyQuestion[];
};

/** One question's answer: the choices picked, and the typed "Other…" text (null when not picked). */
export type ClarifyAnswer = { picked: string[]; other: string | null };

export type ClarifyAnswers = Record<string, ClarifyAnswer>;

const MAX_QUESTIONS = 3;
const MIN_OPTIONS = 2;
const MAX_OPTIONS = 4;
const JOIN = ", ";

/** One line of text: trimmed, runs of whitespace (newlines too) as one space. */
function oneLine(value: unknown): string {
  return typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";
}

function readOptions(raw: unknown): string[] | null {
  if (!Array.isArray(raw)) return null;
  const seen = new Set<string>();
  const options: string[] = [];
  for (const item of raw) {
    const text = oneLine(item);
    if (!text || seen.has(text.toLowerCase())) continue;
    seen.add(text.toLowerCase());
    options.push(text);
  }
  return options.length >= MIN_OPTIONS && options.length <= MAX_OPTIONS ? options : null;
}

function readQuestion(raw: unknown, index: number): ClarifyQuestion | null {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return null;
  const record = raw as Record<string, unknown>;
  const question = oneLine(record.question);
  const label = oneLine(record.label) || question;
  const options = readOptions(record.options);
  if (!question || !label || !options) return null;
  return {
    id: oneLine(record.id) || `q${index + 1}`,
    label,
    question,
    options,
    multi: record.multi === true,
  };
}

/** The card in a fence body, or null when it is not one the phone can draw. */
export function parseClarifyCard(content: string): ClarifyCard | null {
  const data = parseJsonRecord(content.trim());
  if (!data || !Array.isArray(data.questions)) return null;
  if (data.questions.length === 0 || data.questions.length > MAX_QUESTIONS) return null;
  const questions: ClarifyQuestion[] = [];
  for (const [index, raw] of data.questions.entries()) {
    const question = readQuestion(raw, index);
    if (!question) return null;
    questions.push(question);
  }
  const ids = new Set(questions.map((question) => question.id));
  if (ids.size !== questions.length) {
    questions.forEach((question, index) => (question.id = `q${index + 1}`));
  }
  return { when: data.when === "after" ? "after" : "first", questions };
}

function answerValues(question: ClarifyQuestion, answer: ClarifyAnswer | undefined): string[] {
  if (!answer) return [];
  const picked = question.options.filter((option) => answer.picked.includes(option));
  const other = answer.other == null ? "" : oneLine(answer.other);
  return other ? [...picked, other] : picked;
}

/** Every question has a pick, or "Other…" text that is not blank. */
export function canSubmitClarify(card: ClarifyCard, answers: ClarifyAnswers): boolean {
  return card.questions.every((question) => answerValues(question, answers[question.id]).length > 0);
}

/**
 * The message Submit sends: one "Label: pick" line per question, in the card's order.
 * Several picks join with ", "; "Other…" text follows the picks, on the same line.
 */
export function clarifyMessage(card: ClarifyCard, answers: ClarifyAnswers): string {
  return card.questions
    .map((question) => `${question.label}: ${answerValues(question, answers[question.id]).join(JOIN)}`)
    .join("\n");
}

/** The options a written answer names, in order, and whatever is left as typed text. */
function splitValue(question: ClarifyQuestion, value: string): ClarifyAnswer {
  if (question.options.includes(value)) return { picked: [value], other: null };
  if (!question.multi) return { picked: [], other: value };
  // Longest first, so "Yes, I'm revising" is read before a shorter "Yes".
  const byLength = [...question.options].sort((a, b) => b.length - a.length);
  const picked: string[] = [];
  let rest = value;
  for (;;) {
    const option = byLength.find(
      (candidate) => rest === candidate || rest.startsWith(candidate + JOIN),
    );
    if (!option) break;
    if (!picked.includes(option)) picked.push(option);
    rest = rest === option ? "" : rest.slice(option.length + JOIN.length);
  }
  return { picked, other: rest ? rest : null };
}

/**
 * The picks a sent message holds, read back onto the card it answered: every line is
 * "Label: value" for one of the card's labels (as the server reads it). Null when the
 * message is anything else (Skip, or something typed instead).
 */
export function answersFromMessage(card: ClarifyCard, message: string): ClarifyAnswers | null {
  const byLabel = new Map(card.questions.map((question) => [question.label.toLowerCase(), question]));
  const lines = message
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) return null;
  const answers: ClarifyAnswers = {};
  for (const line of lines) {
    const colon = line.indexOf(":");
    if (colon < 0) return null;
    const question = byLabel.get(line.slice(0, colon).trim().toLowerCase());
    const value = line.slice(colon + 1).trim();
    if (!question || !value) return null;
    answers[question.id] = splitValue(question, value);
  }
  return answers;
}

/** What Copy and Read aloud make of a card: each question and its choices. */
export function clarifyText(card: ClarifyCard): string {
  return card.questions
    .map((question) => `${question.question} (${question.options.join(" / ")})`)
    .join("\n");
}
