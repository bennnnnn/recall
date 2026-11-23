/**
 * The composer's live answer: while the math keyboard is open, a draft that is a calculation
 * (`$3+1\times 2$`) shows its value under it (`= 5`) as each key lands. It is a typing
 * preview, worked on the phone; Send still asks the server, whose checked answer is the one
 * the chat keeps (CLAUDE.md, Golden Rule 7). A draft that is not a calculation shows nothing.
 * One with no number at all says undefined (`1 ÷ 0`, `tan 90°`, `log 0`), and one with ± shows
 * each branch (`signs.ts`).
 *
 * `docs/fixtures/live_answer_cases.json` holds drafts and their values; the server's test
 * (`test_live_answer_fixture.py`) checks each against SymPy and the turn's own reading, and
 * the phone's test checks this module against the same file.
 */
import type { LiveResult } from "@/lib/math/live/evaluate";
import { formatBranches, formatLiveResult, formatValues, type LiveAnswer } from "@/lib/math/live/format";
import { readCalculation, type LiveNode } from "@/lib/math/live/read";
import { isTypedFraction, workSigns, type LiveSigns } from "@/lib/math/live/signs";

export type { LiveAnswer };

const isSignOnly = (node: LiveNode): boolean => node.kind === "pm" && !node.left;

/** `5`, `-2.5`, `(3)`, `\pm 3` or `-\pm 3` has nothing to work out. */
function isPlainNumber(node: LiveNode): boolean {
  if (node.kind === "pm" && !node.left) return isPlainNumber(node.right);
  if (node.kind === "neg" && isSignOnly(node.operand)) return isPlainNumber(node.operand);
  return node.kind === "number" || (node.kind === "neg" && node.operand.kind === "number");
}


/** Spaces the keyboard may leave after the = (`\,`, `\quad`, …). */
const LATEX_SPACE = String.raw`(?:\s|\\[,;:! ]|\\q?quad\b)*`;
const CLOSING_EQUALS_IN_MATH = new RegExp(String.raw`=${LATEX_SPACE}\$\s*$`);
const CLOSING_EQUALS_PLAIN = new RegExp(String.raw`=${LATEX_SPACE}$`);

/**
 * `3+4=` asks for its value, as a calculator's = key does: one = at the very end of the maths
 * is dropped before the draft is read. `2+2=4` keeps its = and stays an equation, and an =
 * after the closing `$` is text outside the maths, no calculation.
 */
function withoutClosingEquals(draft: string): string {
  return draft.includes("$")
    ? draft.replace(CLOSING_EQUALS_IN_MATH, "$")
    : draft.replace(CLOSING_EQUALS_PLAIN, "");
}

function read(draft: string): { node: LiveNode; signs: LiveSigns } | null {
  const reading = readCalculation(withoutClosingEquals(draft));
  if (!reading || isPlainNumber(reading.node)) return null;
  const signs = workSigns(reading);
  return signs ? { node: reading.node, signs } : null;
}

/** The draft's values (one, or a ± draft's each), or `null` when it shows no answer. */
export function liveValuesForTest(draft: string): LiveResult[] | null {
  const signs = read(draft)?.signs;
  if (!signs) return null;
  if (signs.kind === "one") return [signs.result];
  return signs.kind === "branches" ? signs.branches.map((branch) => branch.result) : signs.values;
}

/**
 * What the composer shows under the draft, or `null` for no answer. `undefinedWord` is
 * "undefined" in the app's language (`chat.math_live_undefined`).
 */
export function liveAnswer(draft: string, undefinedWord: string): LiveAnswer | null {
  const found = read(draft);
  if (!found) return null;
  const { node, signs } = found;
  const preferFraction = /\\[dt]?frac\{/.test(draft);
  if (signs.kind === "branches") return formatBranches(signs.branches, { preferFraction, typedFraction: false }, undefinedWord);
  if (signs.kind === "values") return formatValues(signs.values, { preferFraction, typedFraction: false });
  return formatLiveResult(signs.result, { preferFraction, typedFraction: isTypedFraction(node, signs.result) }, undefinedWord);
}
