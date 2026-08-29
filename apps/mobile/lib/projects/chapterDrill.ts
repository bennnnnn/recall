import type { ProjectItem } from "@/lib/api";
import type { ParsedVocabQuiz, QuizChoice } from "@/lib/parseVocabQuiz";

import { cardMeaning, itemToCard } from "@/lib/projects/chapterLesson";

const LETTERS: QuizChoice["letter"][] = ["A", "B", "C", "D"];

export type DrillStep =
  | { kind: "teach"; itemId: string; card: ReturnType<typeof itemToCard> }
  | {
      kind: "use" | "meaning";
      itemId: string;
      question: string;
      quiz: ParsedVocabQuiz;
    };

export type DrillLabels = {
  useQuestion: (sentence: string) => string;
  meaningQuestion: (sentence: string) => string;
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

/** First case-insensitive occurrence of `word` → `_____`. Linear scan, no regex. */
export function blankTargetWord(sentence: string, word: string): string {
  const trimmed = sentence.trim() || word;
  const target = word.trim();
  if (!target) return `${trimmed} (_____)`;
  const at = trimmed.toLowerCase().indexOf(target.toLowerCase());
  if (at === -1) return `${trimmed} (_____)`;
  return `${trimmed.slice(0, at)}_____${trimmed.slice(at + target.length)}`;
}

export function pickTexts(
  pool: string[],
  correct: string,
  seed: string,
  fallbacks: string[],
): string[] {
  const answer = correct.trim();
  if (!answer) return [];
  const seen = new Set<string>([answer.toLowerCase()]);
  const extras: string[] = [];
  for (const text of [...pool, ...fallbacks]) {
    const trimmed = text.trim();
    const key = trimmed.toLowerCase();
    if (!trimmed || seen.has(key)) continue;
    seen.add(key);
    extras.push(trimmed);
  }
  const sampled = seededShuffle(extras, `${seed}:extras`).slice(0, 3);
  return seededShuffle([answer, ...sampled], seed);
}

function quizFromChoices(
  word: string,
  question: string,
  texts: string[],
  correctText: string,
): ParsedVocabQuiz | null {
  if (texts.length < 2) return null;
  const choices = texts.slice(0, 4).map((text, index) => ({
    letter: LETTERS[index] ?? "A",
    text,
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

export function isLastStepForWord(drills: Pick<DrillStep, "itemId">[], index: number): boolean {
  const current = drills[index];
  const next = drills[index + 1];
  return Boolean(current) && (!next || next.itemId !== current.itemId);
}

export function buildChapterDrills(
  items: ProjectItem[],
  pool: ProjectItem[],
  labels: DrillLabels,
): DrillStep[] {
  const wordPool = pool.map((item) => item.content.trim()).filter(Boolean);
  const meaningPool = pool.map((item) => cardMeaning(itemToCard(item))).filter(Boolean);
  const drills: DrillStep[] = [];
  for (const item of items) {
    const word = item.content.trim();
    if (!word) continue;
    const card = itemToCard(item);
    const meaning = cardMeaning(card);
    const example = item.example_sentence?.trim() || item.note?.trim() || word;
    const gap = blankTargetWord(example, word);
    drills.push({ kind: "teach", itemId: item.id, card });
    const useQuestion = labels.useQuestion(gap);
    const useQuiz = quizFromChoices(
      word,
      useQuestion,
      pickTexts(wordPool, word, `${item.id}:use`, []),
      word,
    );
    if (useQuiz) {
      drills.push({ kind: "use", itemId: item.id, question: useQuestion, quiz: useQuiz });
    }
    const meaningQuestion = labels.meaningQuestion(gap);
    const meaningQuiz = quizFromChoices(
      word,
      meaningQuestion,
      pickTexts(meaningPool, meaning, `${item.id}:meaning`, []),
      meaning,
    );
    if (meaningQuiz) {
      drills.push({
        kind: "meaning",
        itemId: item.id,
        question: meaningQuestion,
        quiz: meaningQuiz,
      });
    }
  }
  return drills;
}
