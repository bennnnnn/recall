/**
 * A formula as one line of its symbols, where a screen shows maths as text (a search
 * hit's line): "(v_f - v_i)/t", "x^(n+1)", "√2̅". A drawing groups by position, a fraction
 * bar or a raised exponent; on one line the grouping is written with parentheses wherever
 * the line would otherwise read another way ("v_f - v_i/t" is v_f - (v_i/t)).
 *
 * One walker per job over the parser's tree: this one draws symbols, a screen reader
 * hears `spokenFormula`'s words, and Copy writes `markdownToCopyText`'s form.
 */
import { DEGREE_RING, parseSimpleLatex } from "@/lib/math/latexParse";
import type { MathAccentKind, MathSegment } from "@/lib/math/textTypes";

// Copy and read-aloud still spell an accent as a combining mark. The screen
// draws a measured rule from the accent segment; these marks are not painted.
const ACCENT_MARK: Record<MathAccentKind, string> = {
  overline: "̅",
  underline: "̲",
  hat: "̂",
  tilde: "̃",
  vec: "⃗",
  vecLeft: "⃖",
  bar: "̄",
  ddot: "̈",
  dot: "̇",
};

/** Combining mark applied per-character so copy spells the whole accented
 * run. The screen draws one measured rule; these marks are not painted. */
function markEachChar(text: string, mark: string): string {
  return Array.from(text)
    .map((ch) => (ch === " " ? ch : `${ch}${mark}`))
    .join("");
}

// One number or one letter reads as itself beside a fraction bar; "2a" or "Δ v" does not
// ("1/2a" reads as (1/2)a). A script may also be a name (t_flight, x_max).
const SIDE_ATOM = /^[+\-−]?(?:\d+(?:[.,]\d+)?|\p{L})$/u;
const SCRIPT_ATOM = /^(?:[+\-−]?(?:\d+(?:[.,]\d+)?|\p{L}+)|[°′″'*∗†‡])$/u;
const NAME = /^\p{L}+$/u;

/** One number, letter or upright name, and scripts that are atoms themselves. */
function isAtom(segments: MathSegment[], atom: RegExp): boolean {
  const [head, ...scripts] = segments;
  if (!head) return true;
  // A struck-through or accented term is still one term (the 3 in 3x/3̸, a v⃗).
  if ((head.type === "cancel" || head.type === "accent") && !scripts.length) return isAtom(head.body, atom);
  const value = head.type === "text" || head.type === "upright" ? head.value.trim() : null;
  if (value === null || !(atom.test(value) || (head.type === "upright" && NAME.test(value)))) return false;
  return scripts.every((script) => (script.type === "sup" || script.type === "sub") && scriptIsAtom(script));
}

/** A script of one term, itself unscripted: "x^y^2" on a line hides which power is whose. */
function scriptIsAtom(script: Extract<MathSegment, { type: "sup" | "sub" }>): boolean {
  if (!script.body) return SCRIPT_ATOM.test(script.value.trim());
  return script.body.length === 1 && isAtom(script.body, SCRIPT_ATOM);
}

/** The next piece is written straight after, as a factor (½mv², (a/b)²), not after a space or an operator. */
export function joinsDirectly(next: MathSegment | undefined): boolean {
  if (!next) return false;
  if (next.type !== "text" && next.type !== "upright") return true;
  return /^[\p{L}\p{N}(√]/u.test(next.value);
}

function scriptToPlain(seg: Extract<MathSegment, { type: "sup" | "sub" }>): string {
  if (seg.type === "sup" && !seg.body && seg.value === DEGREE_RING) return "°";
  const inner = (seg.body ? segmentsToPlain(seg.body) : seg.value).trim();
  return `${seg.type === "sup" ? "^" : "_"}${scriptIsAtom(seg) ? inner : `(${inner})`}`;
}

function fractionToPlain(seg: Extract<MathSegment, { type: "frac" }>, next: MathSegment | undefined): string {
  const side = (part: MathSegment[]) => {
    const text = segmentsToPlain(part).trim();
    return isAtom(part, SIDE_ATOM) ? text : `(${text})`;
  };
  const fraction = `${side(seg.num)}/${side(seg.den)}`;
  return joinsDirectly(next) ? `(${fraction})` : fraction;
}

function segmentToPlain(seg: MathSegment, next: MathSegment | undefined): string {
  if (seg.type === "text" || seg.type === "upright") return seg.value;
  if (seg.type === "sup" || seg.type === "sub") return scriptToPlain(seg);
  if (seg.type === "cancel") return segmentsToPlain(seg.body);
  if (seg.type === "accent") {
    return markEachChar(segmentsToPlain(seg.body), ACCENT_MARK[seg.kind]);
  }
  if (seg.type === "sqrt") {
    // Radicand under a combining overline ("4̅"), not "(4)" in parens — the
    // bar itself delimits what's under the root, closer to how it's drawn
    // on paper. Nested content (a fraction, superscript, …) is flattened
    // to plain text first since there's no way to draw it under a bar too.
    const body = markEachChar(segmentsToPlain(seg.body), "̅");
    const indexText = seg.index ? segmentsToPlain(seg.index) : seg.degree;
    return indexText ? `√[${indexText}]${body}` : `√${body}`;
  }
  return fractionToPlain(seg, next);
}

export function segmentsToPlain(segments: MathSegment[]): string {
  return segments.map((segment, index) => segmentToPlain(segment, segments[index + 1])).join("");
}

/** The formula as one line of symbols, never a leftover `\\command`. */
export function formulaText(latex: string): string {
  const plain = segmentsToPlain(parseSimpleLatex(latex));
  return plain.replace(/\\[a-zA-Z]+/g, (cmd) => cmd.slice(1));
}
