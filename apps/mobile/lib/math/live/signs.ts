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
import { childrenOf, mapChildren, type LiveNode, type LiveReading } from "@/lib/math/live/read";

type PlusMinus = Extract<LiveNode, { kind: "pm" }>;
type Pick = "-" | "+";

/** One way a ± draft goes: its text with the sign picked (`null` where it cannot be written
 * truly, in a draft with a mod), its value, and whether that text is the value's own fraction
 * (`-\frac{1}{3}`), so only its decimal is new. */
export type LiveBranch = { latex: string | null; result: LiveResult; typed: boolean };

export type LiveSigns =
  | { kind: "one"; result: LiveResult }
  | { kind: "branches"; branches: LiveBranch[] }
  | { kind: "values"; values: LiveValue[] };

const MAX_SIGNS = 3;
/** Below the 10 digits shown: values this close are one value. */
const SAME = 1e-12;

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
  return mapChildren(node, (child) => picked(child, picks));
}

/** A run of signs and one more as one sign: `-` then `-` is `+`, `--` then `+` is `+`. */
const merged = (run: string, pick: Pick): Pick =>
  [...run.replace(/[^+\-−]/g, "")].reduce<Pick>((sign, next) => ((next === "+") === (sign === "+") ? "+" : "-"), pick);

/** Signs and the spaces the reader skips between them (`\,`, `\quad`). */
const RUN = String.raw`(?:[+\-−]|\s|\\[,;:! ]|\\q?quad\b)*`;
const RUN_BEFORE = new RegExp(String.raw`[+\-−]${RUN}$`);
const RUN_AFTER = new RegExp(String.raw`^(?:\s|\\[,;:! ]|\\q?quad\b)*[+\-−]${RUN}`);

/**
 * The draft as written, its sign replaced (`2\pm 3` → `2-3`); a typed `*` drawn as ×. The
 * space the key typed after `\pm` goes with it. A run of + and − typed right before or after
 * the sign merges with it (`2-\pm 3`, `2--\pm 3` and `2\pm -3` → `2+3` and `2-3`), never `2--3`.
 * Not in a draft with a mod, where it may not be true (`(-2) mod 3` is not `-(2 mod 3)`): there
 * `null`, and the draft shows its values alone.
 */
function written(math: string, sign: PlusMinus, pick: Pick): string | null {
  let before = math.slice(0, sign.at);
  let after = math.slice(sign.at + sign.width).replace(/^\s+/, "");
  let shown = pick;
  const operators = RUN_BEFORE.exec(before);
  if (!sign.left && operators) {
    shown = merged(operators[0], shown);
    before = before.slice(0, operators.index);
  }
  const next = RUN_AFTER.exec(after);
  if (next) {
    shown = merged(next[0], shown);
    after = after.slice(next[0].length);
  }
  const merging = Boolean((!sign.left && operators) || next);
  if (merging && math.includes("\\bmod")) return null;
  // The keyboard's own glyphs as the commands the draft above draws (`2×-3` → `2 \times -3`).
  return `${before}${shown}${after}`
    .replace(/[*×]/g, "\\times ")
    .replace(/÷/g, "\\div ")
    .replace(/·/g, "\\cdot ");
}

/** Relative to the values themselves: `1.41420e-5` and `1.41421e-5` are two values. */
function same(a: LiveValue, b: LiveValue): boolean {
  if (a.kind === "exact" && b.kind === "exact") return a.r.n === b.r.n && a.r.d === b.r.d;
  const x = numberOf(a);
  const y = numberOf(b);
  return Math.abs(x - y) <= SAME * Math.max(Math.abs(x), Math.abs(y));
}

/** A node under its minus signs, and whether they come to a minus (`--3` is 3). */
function unsigned(node: LiveNode): { node: LiveNode; negative: boolean } {
  let negative = false;
  let inner = node;
  while (inner.kind === "neg") {
    negative = !negative;
    inner = inner.operand;
  }
  return { node: inner, negative };
}

/** `\frac{3}{4}`, `-\frac{3}{4}`, `\frac{-3}{4}` or `\frac{3}{-4}` typed in lowest terms: only its decimal is new. */
export function isTypedFraction(node: LiveNode, value: LiveResult): boolean {
  if (value.kind !== "exact") return false;
  const outside = unsigned(node);
  const frac = outside.node;
  if (frac.kind !== "frac") return false;
  const top = unsigned(frac.num);
  const bottom = unsigned(frac.den);
  if (top.node.kind !== "number" || bottom.node.kind !== "number") return false;
  // The signs outside, on top and below together: `\frac{1}{-3}` is −1/3.
  const negative = [outside, top, bottom].filter((part) => part.negative).length % 2 === 1;
  return top.node.text === (negative ? -value.r.n : value.r.n).toString() && bottom.node.text === value.r.d.toString();
}

/** Smallest first, each compared with the last one kept, so close values never merge in a chain. */
function distinct(values: LiveValue[]): LiveValue[] {
  const kept: LiveValue[] = [];
  for (const value of [...values].sort((a, b) => numberOf(a) - numberOf(b))) {
    const last = kept.at(-1);
    if (!last || !same(last, value)) kept.push(value);
  }
  return kept;
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
  if (only && signs.length === 1) {
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
  return { kind: "values", values: distinct(values) };
}
