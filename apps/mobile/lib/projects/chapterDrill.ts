import type { ProjectItem } from "@/lib/api";
import type { ParsedVocabQuiz, QuizChoice } from "@/lib/parseVocabQuiz";

import { wholeWordIndex } from "@/lib/projects/wordBoundary";
import { cardMeaning, itemToCard } from "@/lib/projects/chapterLesson";

const LETTERS: QuizChoice["letter"][] = ["A", "B", "C", "D"];

export type DrillStep =
  | { kind: "teach"; itemId: string; card: ReturnType<typeof itemToCard> }
  | {
      kind: "use" | "meaning";
      itemId: string;
      question: string;
      explanation: string;
      contextSentence?: string;
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

/** Only exact whole words/phrases can be replaced with the uninflected answer. */
export function blankTargetWord(sentence: string, word: string): string | null {
  const trimmed = sentence.trim();
  const target = word.trim();
  if (!target || !trimmed) return null;
  const at = wholeWordIndex(trimmed, target);
  return at < 0 ? null : `${trimmed.slice(0, at)}_____${trimmed.slice(at + target.length)}`;
}

function choiceKey(text: string) {
  return text
    .trim()
    .normalize("NFKC")
    .toLowerCase()
    .replace(/\s+/gu, " ")
    .replace(/[.!?…]+$/u, "");
}

export function pickTexts(
  pool: string[],
  correct: string,
  seed: string,
  fallbacks: string[],
): string[] {
  const answer = correct.trim();
  if (!answer) return [];
  const seen = new Set<string>([choiceKey(answer)]);
  const extras: string[] = [];
  for (const text of [...pool, ...fallbacks]) {
    const trimmed = text.trim();
    const key = choiceKey(trimmed);
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
  const correct = choices.find((choice) => choice.text === correctText)?.letter ?? "A";
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
  const meaningPool = pool.map((item) => cardMeaning(itemToCard(item))).filter(Boolean);
  const drills: DrillStep[] = [];
  for (const item of items) {
    const word = item.content.trim();
    if (!word) continue;
    const card = itemToCard(item);
    const meaning = cardMeaning(card);
    const wordPool = pool
      .filter(
        (candidate) =>
          candidate.id === item.id ||
          choiceKey(cardMeaning(itemToCard(candidate))) !== choiceKey(meaning),
      )
      .map((candidate) => candidate.content.trim())
      .filter(Boolean);
    if (!item.definition?.trim() && !item.simple_gloss?.trim()) continue;
    const examples = card.examples ?? [];
    const explanation = `${word} — ${meaning}${examples[0] ? `\n${examples[0]}` : ""}`;
    const gap = examples.map((text) => blankTargetWord(text, word)).find((text) => text != null);
    const useQuestion = gap ? labels.useQuestion(gap) : "";
    const useQuiz = gap
      ? quizFromChoices(word, useQuestion, pickTexts(wordPool, word, `${item.id}:use`, []), word)
      : null;
    // An inflected example remains intact; ask about the taught meaning instead
    // of making a cloze whose answer cannot fit the original sentence.
    const meaningQuestion = labels.meaningQuestion(word);
    const meaningQuiz = quizFromChoices(
      word,
      meaningQuestion,
      pickTexts(meaningPool, meaning, `${item.id}:meaning`, []),
      meaning,
    );
    // Never produce a teaching-only path that could award mastery without a check.
    if (!useQuiz && !meaningQuiz) continue;
    drills.push({ kind: "teach", itemId: item.id, card });
    if (useQuiz)
      drills.push({
        kind: "use",
        itemId: item.id,
        question: useQuestion,
        explanation,
        quiz: useQuiz,
      });
    if (meaningQuiz) {
      drills.push({
        kind: "meaning",
        itemId: item.id,
        question: meaningQuestion,
        contextSentence: examples[0],
        explanation,
        quiz: meaningQuiz,
      });
    }
  }
  return drills;
}
