/**
 * The composer's live answer: while the math keyboard is open, a draft that is a calculation
 * (`$3+1\times 2$`) shows its value under it (`= 5`) as each key lands. It is a typing
 * preview, worked on the phone; Send still asks the server, whose checked answer is the one
 * the chat keeps (CLAUDE.md, Golden Rule 7). A draft that is not a calculation shows nothing.
 *
 * `docs/fixtures/live_answer_cases.json` holds drafts and their values; the server's test
 * (`test_live_answer_fixture.py`) checks each against SymPy and the turn's own reading, and
 * the phone's test checks this module against the same file.
 */
import { evaluateCalculation, type LiveValue } from "@/lib/math/live/evaluate";
import { formatLiveValue, type LiveAnswer } from "@/lib/math/live/format";
import { readCalculation, type LiveNode } from "@/lib/math/live/read";

export type { LiveAnswer, LiveValue };

/** `5`, `-2.5` or `(3)` has nothing to work out. */
function isPlainNumber(node: LiveNode): boolean {
  return node.kind === "number" || (node.kind === "neg" && node.operand.kind === "number");
}

/** `\frac{3}{4}` typed in lowest terms: only its decimal is new. */
function isTypedFraction(node: LiveNode, value: LiveValue): boolean {
  return (
    node.kind === "frac" &&
    value.kind === "exact" &&
    node.num.kind === "number" &&
    node.den.kind === "number" &&
    node.num.text === value.r.n.toString() &&
    node.den.text === value.r.d.toString()
  );
}

function read(draft: string): { node: LiveNode; value: LiveValue } | null {
  const node = readCalculation(draft);
  if (!node || isPlainNumber(node)) return null;
  const value = evaluateCalculation(node);
  return value ? { node, value } : null;
}

/** The draft's value, or `null` when it is not a calculation. */
export function liveValue(draft: string): LiveValue | null {
  return read(draft)?.value ?? null;
}

/** What the composer shows under the draft, or `null` for no answer. */
export function liveAnswer(draft: string): LiveAnswer | null {
  const found = read(draft);
  if (!found) return null;
  return formatLiveValue(found.value, {
    preferFraction: /\\[dt]?frac\{/.test(draft),
    typedFraction: isTypedFraction(found.node, found.value),
  });
}
