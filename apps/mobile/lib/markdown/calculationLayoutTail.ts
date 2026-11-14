/**
 * Whether a plain line is a chain to lay out, and how a laid-out line ends: its note and
 * its hard break (twin: calculation_layout_tail.py).
 */
import { ALNUM, charAt, LETTER } from "@/lib/markdown/unicodeChars";

// A unit after a value ("km/h", "m/s²", "N.", "kg·m/s"): letter runs of three or fewer, so
// "here" or "only" read as words.
const UNIT_TAIL = /^[A-Za-zµμΩ°]{1,3}(?:[/·^][A-Za-zµμΩ°0-9²³⁻¹]{1,3}|[0-9²³⁻¹]{1,2}){0,3}[.,;:!?]*$/;

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
  } else if (parts.length > 0 && UNIT_TAIL.test(note)) {
    // "$d = 120 + 60 = 180$ km": the unit stays with the last row's value.
    parts[parts.length - 1] = `${last.trimEnd()} ${note}`;
  } else if (note) {
    parts.push(parts.length > 0 ? tail.trimStart() : tail);
  }
  return keepHardBreak(tail, parts.join("\n"));
}

/**
 * Prose follows a maths span on its line: the span is part of a sentence.
 *
 * "has $\Delta = 9 - 8 = 1$, giving …" or "$v = 100/20 = 5$ m/s, so it is slow" split
 * into rows broke the sentence into fragments, a unit or a clause alone on a line. A
 * chain that ends its line ("**Step 1:** $x = 2 + 3 = 5$"), or whose line ends in a unit
 * ("$d = 120 + 60 = 180$ km") or a note ("$h = …$ — Vertex of a parabola"), is a worked
 * step and still splits.
 */
export function continuesSentence(after: string): boolean {
  const rest = after.replace(/^[.,;:!?]+/, "").trim();
  return rest.length > 0 && !rest.startsWith("— ") && !UNIT_TAIL.test(rest);
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

// How a value's unit is written: \mathrm{km/h}, \text{ m}, \Omega, 30^\circ.
const UNIT_MARKS = ["\\mathrm{", "\\text{", "\\Omega", "^\\circ", "°"];
const hasUnit = (segment: string) => UNIT_MARKS.some((mark) => segment.includes(mark));

/**
 * `v = 100 km/h × 1000/3600 = 27.8 m/s`: a symbol's value in two units, one row.
 *
 * Every value after the symbol carries its unit. A chain that works a value out
 * (`a = (27.8 − 0)/8 = 3.47 m/s²`) has bare numbers until its end, and splits;
 * so does one through another symbol (`F = ma = …`), or from a value rather than a
 * symbol (`1 km = 1000 m = 100000 cm`).
 */
export function convertsUnits(segments: string[]): boolean {
  return (
    segments.length > 2 && !/^\d/.test((segments[0] ?? "").trim()) && segments.slice(1).every(hasUnit)
  );
}

export const CHAIN_STOP_WORDS = new Set(["or", "and"]);
// A gap that names a new relationship is one step, not another value of the first side.
export const CHAIN_STOP_COMMANDS = new Set([
  "rightarrow",
  "leftarrow",
  "Rightarrow",
  "Leftarrow",
  "Longrightarrow",
  "longrightarrow",
  "to",
  "implies",
  "iff",
  "Leftrightarrow",
  "mapsto",
  "quad",
  "qquad",
  "therefore",
  "because",
  "\\",
]);
// The same written as marks: "x = 2 ⇒ y = 4", "∴ y = 4".
const STOP_MARKS = new Set([..."⇒⟹→⟶⇔↔∴∵"]);
// Commands whose braces hold words ("\\text{ so }"): read as the sentence they are.
const TEXT_COMMANDS = new Set(["text", "textrm", "textit", "textbf", "mathrm", "mbox"]);
// Names a formula writes as a word before its argument ("ln x", "lim x"): no prose between two
// statements.
const FUNCTION_WORDS = new Set([
  "sin",
  "cos",
  "tan",
  "sec",
  "csc",
  "cot",
  "sinh",
  "cosh",
  "tanh",
  "arcsin",
  "arccos",
  "arctan",
  "ln",
  "log",
  "exp",
  "lim",
  "max",
  "min",
  "det",
  "gcd",
  "lcm",
  "mod",
  "arg",
  "sqrt",
  "abs",
]);

/**
 * True when a word joins two statements before the last side: "so A = 54", "0.5 donc T",
 * "πr² where r = 3", in any language. Copied into each row, the word and the symbol after it
 * became the row's left side ("so A = 54"). A unit after the last value ("6 kg m/s") is no join.
 */
export function joinedByWords(segments: string[]): boolean {
  return segments.slice(0, -1).some(wordThenTerm);
}

/**
 * Two letters or more, a capital only first ("So"). Letters without case are words (ስለዚህ,
 * 所以); a modifier letter (the ᵢ of xᵢ, the ⁿ of xⁿ) marks a symbol, never a word.
 */
function isWord(word: string): boolean {
  const chars = Array.from(word);
  return (
    chars.length >= 2 &&
    !chars.slice(1).some((char) => char !== char.toLowerCase()) &&
    !chars.some((char) => /\p{Lm}/u.test(char))
  );
}

/**
 * A word outside brackets, standing alone and followed by a space and another term (a letter,
 * a digit or a command): "so A", "so 2a", "donc T". A product of symbols ("ma", "at") is
 * followed by an operator or nothing; a function's name ("ln x") is no word. A stated arrow or
 * "therefore" mark, or a ";" written in text, ends a statement too.
 */
function wordThenTerm(raw: string): boolean {
  const segment = inlineText(raw);
  let depth = 0;
  let index = 0;
  while (index < segment.length) {
    const char = charAt(segment, index);
    if (char === "\\") {
      // A command's name ("\\Delta x") is no word; skip it whole, or the one mark after.
      index += 1;
      if (/[A-Za-z]/.test(segment[index] ?? "")) {
        while (/[A-Za-z]/.test(segment[index] ?? "")) index += 1;
      } else index += 1;
      continue;
    }
    if ("([{".includes(char)) depth += 1;
    else if (")]}".includes(char)) depth = Math.max(0, depth - 1);
    else if (depth === 0 && (STOP_MARKS.has(char) || char === ";")) return true;
    if (!LETTER.test(char)) {
      index += char.length;
      continue;
    }
    const start = index;
    while (LETTER.test(charAt(segment, index))) index += charAt(segment, index).length;
    const word = segment.slice(start, index);
    if (depth > 0 || (start > 0 && !/\s/.test(segment[start - 1]))) continue;
    if (CHAIN_STOP_WORDS.has(word.toLowerCase())) return true;
    if (!isWord(word) || FUNCTION_WORDS.has(word.toLowerCase())) continue;
    if (startsTerm(segment, index)) return true;
  }
  return false;
}

// What may follow a word and keep it maths: an operator ("2 kg \\cdot 9.8") or TeX spacing.
const OPERATOR_COMMANDS = new Set([
  "cdot",
  "cdotp",
  "times",
  "div",
  "pm",
  "mp",
  "ast",
  "star",
  "circ",
  "bullet",
  "approx",
  "neq",
  "ne",
  "leq",
  "le",
  "geq",
  "ge",
  "equiv",
  "sim",
  "simeq",
  "propto",
]);
const SPACE_COMMANDS = new Set(["quad", "qquad", "thinspace", "enspace"]);

/**
 * Whether another term follows a word ending at `index`, past spaces and TeX spacing: a letter,
 * a digit or a command that is no operator ("so A", "so 2a", "so \\frac12"; not the unit of
 * "2 kg \\cdot 9.8").
 */
function startsTerm(segment: string, from: number): boolean {
  let index = from;
  while (index < segment.length) {
    if (segment[index] === " ") {
      index += 1;
      continue;
    }
    if (segment[index] !== "\\") break;
    if (index + 1 < segment.length && ",;:! ".includes(segment[index + 1])) {
      index += 2;
      continue;
    }
    let end = index + 1;
    while (end < segment.length && LETTER.test(segment[end])) end += 1;
    const name = segment.slice(index + 1, end);
    if (SPACE_COMMANDS.has(name)) {
      index = end;
      continue;
    }
    return index > from && !OPERATOR_COMMANDS.has(name);
  }
  return index > from && index < segment.length && ALNUM.test(charAt(segment, index));
}

/**
 * The segment with each text command's braces written out, so the words inside it
 * ("\\text{ so } A") read as the sentence they are.
 */
function inlineText(segment: string): string {
  let out = "";
  let index = 0;
  while (index < segment.length) {
    if (segment[index] !== "\\") {
      out += segment[index];
      index += 1;
      continue;
    }
    let end = index + 1;
    while (end < segment.length && LETTER.test(segment[end])) end += 1;
    const close = segment.startsWith("{", end) ? segment.indexOf("}", end) : -1;
    if (TEXT_COMMANDS.has(segment.slice(index + 1, end)) && close > 0) {
      out += ` ${segment.slice(end + 1, close)} `;
      index = close + 1;
      continue;
    }
    end = Math.max(end, index + 2);
    out += segment.slice(index, end);
    index = end;
  }
  return out;
}

export function joinRows(rows: string[], delim: string, punct = ""): string {
  const lines = rows.map((row) => `${delim}${row}${delim}`);
  if (punct) lines[lines.length - 1] += punct;
  if (lines.length === 1) return lines[0];
  return lines.map((line, index) => (index < lines.length - 1 ? `${line}  ` : line)).join("\n");
}

export function listPrefix(line: string): { prefix: string; body: string } {
  let index = 0;
  while (index < line.length && line[index] === " ") index += 1;
  const rest = line.slice(index);
  for (const marker of ["- ", "* ", "+ "]) {
    if (rest.startsWith(marker)) {
      return { prefix: line.slice(0, index + 2), body: rest.slice(2) };
    }
  }
  let digits = 0;
  while (digits < rest.length && /\d/.test(rest[digits])) digits += 1;
  if (digits > 0 && digits <= 3 && rest.slice(digits, digits + 2) === ". ") {
    return { prefix: line.slice(0, index + digits + 2), body: rest.slice(digits + 2) };
  }
  return { prefix: "", body: line };
}
