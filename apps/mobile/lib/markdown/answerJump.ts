/**
 * The answer a reply shows at its top when its ```answer card sits under its working.
 *
 * A worked reply lays out Given, Required, each formula and its substitution, and only then
 * the card: on a phone that is screens of scrolling before the answer (2026-11-06). A reply
 * with working above its first card opens with the values of its cards in one line, which
 * a tap takes to the first card. Read from the reply's text, so the line is the same for
 * every subject and does not wait on layout.
 */
import { splitAnswerNotation } from "@/lib/answerNotation";
import { fenceIdForLang } from "@/lib/fenceRegistry";
import { isHeavyInlineMath } from "@/lib/math/fenceRetag";
import { answerReadsAsProse, normalizeAnswerContent } from "@/lib/math/answerLayout";
import { scanFences } from "@/lib/mdFenceScan";

/** Lines above the first card that make it worth a line at the top: a short reply needs none. */
const WORKING_LINES = 8;
/** A diagram or another card above the answer stands for this many lines of text. */
const FENCE_LINES = 6;
/** More values than this, or a longer one, and the line names the answer without them. */
const MAX_VALUES = 3;
const MAX_VALUE_LENGTH = 32;

type AnswerValue = { text: string; notation: "math" | "chemistry" };

/** The values to show, or `[]` for a line that only names the answer and leads to it. */
export type AnswerJump = { values: AnswerValue[] };

function isAnswerFence(info: string): boolean {
  return fenceIdForLang(info.trim().split(/\s+/)[0] ?? "") === "answer";
}

/** Text lines and fences above `end`, a fence counted as the room it takes. */
function workingAbove(content: string, end: number): number {
  const before = content.slice(0, end);
  const fences = scanFences(before, true);
  let lines = fences.length * FENCE_LINES;
  let cursor = 0;
  for (const fence of [...fences, { start: before.length, end: before.length }]) {
    lines += before.slice(cursor, fence.start).split("\n").filter((line) => line.trim()).length;
    cursor = fence.end;
  }
  return lines;
}

/** A value short enough for one line of the chip: no environment, sentence or long chain. */
function shortValue(value: AnswerValue): boolean {
  if (!value.text || value.text.length > MAX_VALUE_LENGTH) return false;
  return value.notation === "chemistry" || (!isHeavyInlineMath(value.text) && !answerReadsAsProse(value.text));
}

/** The line a settled reply opens with, or null when its answer is already in view. */
export function answerJumpFor(content: string): AnswerJump | null {
  const cards = scanFences(content, true).filter((fence) => fence.closed && isAnswerFence(fence.info));
  const first = cards[0];
  if (!first || workingAbove(content, first.start) < WORKING_LINES) return null;
  const values = cards.map((card): AnswerValue => {
    const parsed = splitAnswerNotation(card.body);
    const text = parsed.notation === "chemistry" ? parsed.body : normalizeAnswerContent(parsed.body);
    return { text, notation: parsed.notation };
  });
  const shown = values.length <= MAX_VALUES && values.every(shortValue);
  return { values: shown ? values : [] };
}
