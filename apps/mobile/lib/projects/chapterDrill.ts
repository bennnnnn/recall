import type { ProjectItem } from "@/lib/api";
import type { ParsedVocabQuiz, QuizChoice } from "@/lib/parseVocabQuiz";

import { itemToCard } from "@/lib/projects/chapterLesson";

const LETTERS: QuizChoice["letter"][] = ["A", "B", "C", "D"];

const FALLBACK_WORDS = ["hello", "thanks", "please", "water"];
const FALLBACK_MEANINGS = ["a greeting", "a polite request", "a drink", "a number"];

export type DrillStep =
  | { kind: "teach"; itemId: string; card: ReturnType<typeof itemToCard> }
  | {
      kind: "use" | "meaning";
      itemId: string;
      question: string;
      quiz: ParsedVocabQuiz;
    };

export type DrillLabels = {
  useQuestion: (meaning: string) => string;
  meaningQuestion: (word: string) => string;
};

function hashSeed(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function seededShuffle<T>(items: T[], seed: string): T[] {
  const next = [...items];
  let state = hashSeed(seed) || 1;
  for (let index = next.length - 1; index > 0; index -= 1) {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    const swap = state % (index + 1);
    const current = next[index];
    const other = next[swap];
    if (current === undefined || other === undefined) continue;
    next[index] = other;
    next[swap] = current;
  }
  return next;
}

function definitionOf(item: ProjectItem): string {
  return item.definition?.trim() || item.content;
}

function pickTexts(
  pool: string[],
  correct: string,
  seed: string,
  fallbacks: string[],
): string[] {
  const seen = new Set<string>([correct.toLowerCase()]);
  const extras: string[] = [];
  for (const text of [...pool, ...fallbacks]) {
    const key = text.toLowerCase();
    if (!text.trim() || seen.has(key)) continue;
    seen.add(key);
    extras.push(text);
    if (extras.length === 3) break;
  }
  while (extras.length < 3) {
    extras.push(`${correct} ${extras.length + 1}`);
  }
  return seededShuffle([correct, ...extras.slice(0, 3)], seed);
}

function quizFromChoices(
  word: string,
  question: string,
  texts: string[],
  correctText: string,
): ParsedVocabQuiz {
  const choices = LETTERS.map((letter, index) => ({
    letter,
    text: texts[index] ?? correctText,
  }));
  const correct =
    choices.find((choice) => choice.text === correctText)?.letter ?? "A";
  return { word, question, correct, choices, quizType: "vocab" };
}

export function lessonWordProgress(
  drills: Pick<DrillStep, "itemId">[],
  index: number,
): { current: number; total: number; fill: number } {
  const ids: string[] = [];
  for (const step of drills) {
    if (!ids.includes(step.itemId)) ids.push(step.itemId);
  }
  const total = ids.length;
  if (total === 0) return { current: 0, total: 0, fill: 0 };
  if (index >= drills.length) return { current: total, total, fill: 1 };
  const step = drills[index];
  const current = (step ? ids.indexOf(step.itemId) : ids.length - 1) + 1;
  const first = drills.findIndex((entry) => entry.itemId === step?.itemId);
  const wordSteps = drills.filter((entry) => entry.itemId === step?.itemId).length;
  const within = wordSteps > 0 ? (index - first + 1) / wordSteps : 1;
  return { current, total, fill: (current - 1 + within) / total };
}

export function buildChapterDrills(
  items: ProjectItem[],
  pool: ProjectItem[],
  labels: DrillLabels,
): DrillStep[] {
  const wordPool = pool.map((item) => item.content.trim()).filter(Boolean);
  const meaningPool = pool.map(definitionOf).filter(Boolean);
  const drills: DrillStep[] = [];
  for (const item of items) {
    const word = item.content.trim();
    const meaning = definitionOf(item);
    if (!word) continue;
    drills.push({ kind: "teach", itemId: item.id, card: itemToCard(item) });
    drills.push({
      kind: "use",
      itemId: item.id,
      question: labels.useQuestion(meaning),
      quiz: quizFromChoices(
        word,
        labels.useQuestion(meaning),
        pickTexts(wordPool, word, `${item.id}:use`, FALLBACK_WORDS),
        word,
      ),
    });
    drills.push({
      kind: "meaning",
      itemId: item.id,
      question: labels.meaningQuestion(word),
      quiz: quizFromChoices(
        word,
        labels.meaningQuestion(word),
        pickTexts(meaningPool, meaning, `${item.id}:meaning`, FALLBACK_MEANINGS),
        meaning,
      ),
    });
  }
  return drills;
}
