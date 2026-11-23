/**
 * A draft with ± or ∓ (`2 \pm 3`) holds one calculation for each way its signs can go, and the
 * live answer shows them all (CLAUDE.md, Golden Rule 7):
 *
 * - One sign: both branches, written out with their values, the − branch first, for ± and ∓
 *   alike (`2 - 3 = -1` and `2 + 3 = 5`; `10 \pm 2\times 3` is `10 - 2\times 3 = 4` and
 *   `10 + 2\times 3 = 16`). A branch with no value says undefined (`\frac{1}{1 \pm 1}`).
 * - Two or three signs, all ± or all ∓: each goes either way on its own, and the distinct
 *   values are shown, smallest first (`1 \pm 1 \pm 1` is −1, 1 and 3). More than four of them,
 *   a branch that is undefined, or a fourth sign shows nothing: the line would not hold them.
 * - ± and ∓ together (`a \pm b \mp c`) show nothing: there ∓ means the sign opposite the ±,
 *   two values in all, and a reading that treated each sign as its own would show four.
 *
 * A branch that is not one real number (`\sqrt{1 \pm 2}`) leaves the draft with no answer, as
 * any such draft has.
 */
import { evaluateCalculation, numberOf, type LiveResult, type LiveValue } from "@/lib/math/live/evaluate";
import type { LiveNode, LiveReading } from "@/lib/math/live/read";

type PlusMinus = Extract<LiveNode, { kind: "pm" }>;
type Pick = "-" | "+";

/** One way a ± draft goes: its text with the sign picked, its value, and whether that text is
 * the value's own fraction (`-\frac{1}{3}`), so only its decimal is new. */
export type LiveBranch = { latex: string; result: LiveResult; typed: boolean };

export type LiveSigns =
  | { kind: "one"; result: LiveResult }
  | { kind: "branches"; branches: LiveBranch[] }
  | { kind: "values"; values: LiveValue[] };

const MAX_SIGNS = 3;
const MAX_VALUES = 4;
const SAME = 1e-9;

const childrenOf = (node: LiveNode): LiveNode[] =>
  Object.values(node).filter((value): value is LiveNode => typeof value === "object" && value !== null);

function signsOf(node: LiveNode): PlusMinus[] {
  const own = node.kind === "pm" ? [node] : [];
  return [...own, ...childrenOf(node).flatMap(signsOf)];
}

/** The calculation with each sign picked: `a \pm b` is `a - b` or `a + b`, `\pm b` is `-b` or `b`. */
function picked(node: LiveNode, picks: ReadonlyMap<PlusMinus, Pick>): LiveNode {
  if (node.kind === "pm") {
    const right = picked(node.right, picks);
    const op = picks.get(node) ?? "+";
    if (!node.left) return op === "+" ? right : { kind: "neg", operand: right };
    return { kind: "add", op, left: picked(node.left, picks), right };
  }
  const copy: Record<string, unknown> = { ...node };
  for (const [key, value] of Object.entries(node)) {
    if (typeof value === "object" && value !== null) copy[key] = picked(value as LiveNode, picks);
  }
  return copy as LiveNode;
}

/** The draft as written, its sign replaced (`2\pm 3` → `2- 3`); a typed `*` drawn as ×. */
function written(math: string, sign: PlusMinus, pick: Pick): string {
  const text = `${math.slice(0, sign.at)}${pick}${math.slice(sign.at + sign.width)}`;
  return text.replace(/\*/g, "\\times ");
}

/** Relative to the values themselves: `1.41420e-5` and `1.41421e-5` are two values. */
function same(a: LiveValue, b: LiveValue): boolean {
  if (a.kind === "exact" && b.kind === "exact") return a.r.n === b.r.n && a.r.d === b.r.d;
  const x = numberOf(a);
  const y = numberOf(b);
  return Math.abs(x - y) <= SAME * Math.max(Math.abs(x), Math.abs(y));
}

/** `\frac{3}{4}` (or `-\frac{3}{4}`) typed in lowest terms: only its decimal is new. */
export function isTypedFraction(node: LiveNode, value: LiveResult): boolean {
  if (value.kind !== "exact") return false;
  const negative = node.kind === "neg";
  const frac = negative ? node.operand : node;
  return (
    frac.kind === "frac" &&
    frac.num.kind === "number" &&
    frac.den.kind === "number" &&
    frac.num.text === (negative ? -value.r.n : value.r.n).toString() &&
    frac.den.text === value.r.d.toString()
  );
}

function distinct(values: LiveValue[]): LiveValue[] {
  const sorted = [...values].sort((a, b) => numberOf(a) - numberOf(b));
  return sorted.filter((value, i) => i === 0 || !same(sorted[i - 1]!, value));
}

/** What a reading works out to, each ± branch on its own; `null` when nothing is shown. */
export function workSigns(reading: LiveReading): LiveSigns | null {
  const signs = signsOf(reading.node).sort((a, b) => a.at - b.at);
  if (signs.length === 0) {
    const result = evaluateCalculation(reading.node);
    return result && { kind: "one", result };
  }
  if (signs.length > MAX_SIGNS) return null;
  if (new Set(signs.map((sign) => sign.op)).size > 1) return null;
  const ways: { picks: Map<PlusMinus, Pick>; node: LiveNode; result: LiveResult }[] = [];
  // Bit i is sign i's pick, 0 for −: the − branch comes first.
  for (let mask = 0; mask < 2 ** signs.length; mask += 1) {
    const picks = new Map(signs.map((sign, i): [PlusMinus, Pick] => [sign, (mask >> i) & 1 ? "+" : "-"]));
    const node = picked(reading.node, picks);
    const result = evaluateCalculation(node);
    if (!result) return null;
    ways.push({ picks, node, result });
  }
  const [only] = signs;
  if (signs.length === 1 && only) {
    const branches = ways.map(({ picks, node, result }) => ({
      latex: written(reading.math, only, picks.get(only)!),
      result,
      typed: isTypedFraction(node, result),
    }));
    return { kind: "branches", branches };
  }
  const values: LiveValue[] = [];
  for (const { result } of ways) {
    if (result.kind === "undefined") return null;
    values.push(result);
  }
  const shown = distinct(values);
  return shown.length > MAX_VALUES ? null : { kind: "values", values: shown };
}
