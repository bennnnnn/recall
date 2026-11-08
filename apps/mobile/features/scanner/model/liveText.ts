import type { ScannerSubject } from "@/lib/scanner/subjects";

const MATH_SIGNAL = /[0-9=+\-*/^<>≤≥√∫π%()]/;
const MATH_WORD = /\b(?:sin|cos|tan|log|ln|sqrt|lim|dx|dy|area|solve|find)\b/i;
/** NaCl, H2O, CO2. A lone capital pair such as OK is not a formula. */
const FORMULA_TOKEN =
  /\b(?:[A-Z][a-z]\d*|[A-Z]\d+)(?:[A-Z][a-z]?\d*)+\b|\b(?:[A-Z][a-z]?\d*)+(?:[A-Z][a-z]\d*|[A-Z]\d+)\b/;
const WORD = /\p{L}{2,}/gu;
/** A question in words ("Explain how enzymes work"): enough for any subject but maths. */
const SENTENCE_WORDS = 3;

export function normalizeLiveText(text: string): string {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

/**
 * Live framing is ready for maths ink or a formula, even when the formula has no digit.
 * Physics, chemistry and biology questions are often words alone, so a sentence counts
 * there; in maths it is more often a heading than the problem.
 */
export function hasUsefulScannerText(text: string, subject: ScannerSubject = "math"): boolean {
  const trimmed = text.trim();
  if (trimmed.length < 2) return false;
  if (MATH_SIGNAL.test(trimmed) || MATH_WORD.test(trimmed) || /\d/.test(trimmed) || FORMULA_TOKEN.test(trimmed)) {
    return true;
  }
  return subject !== "math" && (trimmed.match(WORD)?.length ?? 0) >= SENTENCE_WORDS;
}

/** Pairs of letters, for `sameLiveText`. */
function bigrams(text: string): Map<string, number> {
  const pairs = new Map<string, number>();
  for (let i = 0; i < text.length - 1; i++) {
    const pair = text.slice(i, i + 2);
    pairs.set(pair, (pairs.get(pair) ?? 0) + 1);
  }
  return pairs;
}

/** Two reads share this much of their letter pairs (Dice) when they are the same text. */
const SAME_TEXT = 0.8;

/**
 * Whether two normalized reads are the same text. A held phone reads a line a little
 * differently frame to frame ("2x+3=7" then "2x+3=7." or "2x +3=7"), which an exact match
 * took for new text and never called the frame ready.
 */
export function sameLiveText(a: string, b: string): boolean {
  if (a === b) return true;
  if (a.length < 2 || b.length < 2) return false;
  const left = bigrams(a);
  const right = bigrams(b);
  let shared = 0;
  for (const [pair, count] of left) shared += Math.min(count, right.get(pair) ?? 0);
  return (2 * shared) / (a.length - 1 + b.length - 1) >= SAME_TEXT;
}

/** The live reader's memory: the last useful text and how many reads in a row matched it. */
export type LiveReadState = { text: string; count: number };

export const STABLE_READS = 3;

/** The next state after one frame's read, and what it shows: text found, and held still. */
export function nextLiveRead(
  state: LiveReadState,
  rawText: string,
  subject: ScannerSubject,
): { state: LiveReadState; hasText: boolean; stable: boolean } {
  if (!hasUsefulScannerText(rawText, subject)) {
    return { state: { text: "", count: 0 }, hasText: false, stable: false };
  }
  const text = normalizeLiveText(rawText);
  const count = sameLiveText(text, state.text) ? state.count + 1 : 1;
  return { state: { text, count }, hasText: true, stable: count >= STABLE_READS };
}
