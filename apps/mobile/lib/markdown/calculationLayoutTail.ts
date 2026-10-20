/**
 * Whether a plain line is a chain to lay out, and how a laid-out line ends: its note and
 * its hard break (twin: calculation_layout_tail.py).
 */
import { LETTER } from "@/lib/markdown/unicodeChars";

/**
 * The laid-out rows of a line, then whatever followed the maths.
 *
 * "$h = …, k = …$ — Vertex of a parabola": the note names the first row, not a
 * line of its own. The line's hard break ("…$  ") still ends it, or the next
 * line runs on.
 */
export function finishInline(parts: string[], tail: string): string {
  const note = tail.trim();
  const last = parts.length > 0 ? parts[parts.length - 1] : "";
  if (note.startsWith("— ") && last.includes("\n")) {
    const cut = last.indexOf("\n");
    parts[parts.length - 1] =
      `${last.slice(0, cut).trimEnd()} ${note}  \n${last.slice(cut + 1)}`;
  } else if (note) {
    parts.push(parts.length > 0 ? tail.trimStart() : tail);
  }
  return keepHardBreak(tail, parts.join("\n"));
}

/** `laid` ends with `original`'s hard break, if it had one. */
export function keepHardBreak(original: string, laid: string): string {
  return original.endsWith("  ") ? `${laid.trimEnd()}  ` : laid;
}

// Subscript digits and charges are chemistry notation (C₃H₈, Fe²⁺): typeset as maths,
// its formulas and units went italic ("n(C₃H₈) = 0.227 mol").
const CHEMISTRY_MARKS = /[₀-₉⁺⁻]/;

/** A plain line that stays text: a word of four letters or more, or chemistry notation. */
export function readsAsProse(text: string): boolean {
  let run = 0;
  for (const char of text) {
    if (CHEMISTRY_MARKS.test(char)) return true;
    run = LETTER.test(char) ? run + 1 : 0;
    if (run >= 4) return true;
  }
  return false;
}
