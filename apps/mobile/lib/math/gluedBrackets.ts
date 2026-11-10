/**
 * Bracketed formulas in prose, and what a bracket means there.
 *
 * A bracket set off by a space is a writer's maths delimiter ("( x^2 = 6 )"): it goes. A
 * bracket glued to what stands beside it groups: a function's argument ("ln(x^2 + 1)"), a
 * factor ("3(x^2 - 4)", "(x^2 + 1)(x - 3)"), an exponent ("e^(x^2)", "(x^2 + 1)^2"). Such a
 * run is one formula, its brackets kept: unwrapped, a sent "ln(x^2 + 1)" drew as
 * "ln x² + 1", and two glued groups wrapped apart ("sin(x^2)cos(x^2)") met as `$$`, a display
 * block. A script's digit is its base's (`x^2(…)`, `log_2(…)`), never the run's head.
 */

// Names whose bracket holds their argument, drawn upright as LaTeX draws them.
const FUNCTION_NAMES = new Set([
  "sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan", "sinh", "cosh",
  "tanh", "log", "ln", "lg", "exp", "max", "min", "sqrt", "pi",
]);
// What may stand glued before a bracket: a name or a number, its scripts (x_1, log_2, x^2,
// x^{n}) and the caret of a bracketed power. Leftmost first, so a script's digit stays with
// its base.
const HEAD = /(?:[A-Za-z]+|\d+(?:\.\d+)?)(?:[_^](?:[A-Za-z0-9]+|\{[^{}\n]*\}))*\^?$/;
// A power written after a bracket: "^2", "^{n}", "^(…)" (read as a group).
const POWER = /^\^(?:[A-Za-z0-9]+|\{[^{}\n]*\})/;
const NAME = /^[A-Za-z]+/;
const LONGEST_GROUP = 180;

type BracketRun = {
  start: number;
  end: number;
  /** The run as LaTeX: function names upright, a bracketed power braced. */
  latex: string;
  /** A bracket set off on both sides: a delimiter, so `latex` is its inside alone. */
  delimited: boolean;
};

/** The index of the bracket closing the one at `open`, or -1 (nested, one line, bounded). */
function closingBracket(text: string, open: number): number {
  let depth = 0;
  for (let i = open; i < text.length && i - open <= LONGEST_GROUP; i += 1) {
    const ch = text[i];
    if (ch === "\n") return -1;
    if (ch === "(") depth += 1;
    else if (ch === ")") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
}

/** A run's text as LaTeX: `sin(` → `\sin(`, `log_2(` → `\log_2(`, `sqrt(a)` → `\sqrt{a}`,
 * `^(a)` → `^{a}`; everything else as written. */
function bracketRunLatex(text: string): string {
  let out = "";
  for (let i = 0; i < text.length;) {
    const word = NAME.exec(text.slice(i))?.[0];
    if (word && !/[A-Za-z\\]/.test(text[i - 1] ?? "")) {
      const name = word.toLowerCase();
      const base = /^_(?:\d+|\{[^{}]*\})/.exec(text.slice(i + word.length))?.[0] ?? "";
      const open = i + word.length + base.length;
      const close = text[open] === "(" && FUNCTION_NAMES.has(name) ? closingBracket(text, open) : -1;
      if (close > 0) {
        const inside = bracketRunLatex(text.slice(open + 1, close));
        // log_10: a base of two digits is one script, braced.
        const braced = /^_\d{2,}$/.test(base) ? `_{${base.slice(1)}}` : base;
        out += name === "sqrt" ? `\\sqrt{${inside}}` : `\\${name}${braced}(${inside})`;
        i = close + 1;
        continue;
      }
      out += word;
      i += word.length;
      continue;
    }
    const close = text[i] === "(" || (text[i] === "^" && text[i + 1] === "(")
      ? closingBracket(text, text[i] === "^" ? i + 1 : i)
      : -1;
    if (close > 0) {
      const power = text[i] === "^";
      const inside = bracketRunLatex(text.slice(i + (power ? 2 : 1), close));
      out += power ? `^{${inside}}` : `(${inside})`;
      i = close + 1;
      continue;
    }
    out += text[i];
    i += 1;
  }
  return out;
}

/** Where the run ending with the group closed at `close` ends: past every group, power and
 * function glued after it. */
function runEnd(seg: string, close: number): number {
  let end = close + 1;
  for (;;) {
    let next = -1;
    if (seg[end] === "(") next = closingBracket(seg, end);
    else if (seg[end] === "^" && seg[end + 1] === "(") next = closingBracket(seg, end + 1);
    else if (seg[end] === "^") {
      const power = POWER.exec(seg.slice(end));
      next = power ? end + power[0].length - 1 : -1;
    } else {
      const word = NAME.exec(seg.slice(end))?.[0];
      const open = word ? end + word.length : -1;
      if (word && FUNCTION_NAMES.has(word.toLowerCase()) && seg[open] === "(") {
        next = closingBracket(seg, open);
      }
    }
    if (next < 0) return end;
    end = next + 1;
  }
}

/** Every group's inside in a run, to ask whether any of them is maths. */
function groupInsides(run: string): string[] {
  const insides: string[] = [];
  for (let i = run.indexOf("("); i >= 0; i = run.indexOf("(", i + 1)) {
    const close = closingBracket(run, i);
    if (close > 0) insides.push(run.slice(i + 1, close));
  }
  return insides;
}

/** Where a run's head starts, for the bracket at `open`; `open` itself when nothing glued
 * stands before it, and null when what does is not maths's (a command, a price). */
function headStart(seg: string, open: number, floor: number): number | null {
  const head = HEAD.exec(seg.slice(floor, open));
  if (head === null) return open;
  const start = floor + head.index;
  const before = seg[start - 1] ?? "";
  // `\sqrt(`: a command's name, read by wrapInlineLatexCommands. "$5(": a price.
  if (before === "\\" || before === "$") return null;
  // The tail of something longer ("x2(", "2a(") is no head: the bracket alone is the run.
  if (/[A-Za-z0-9^_]/.test(before)) return open;
  const word = /^[A-Za-z]{2,}/.exec(head[0])?.[0];
  if (word && !FUNCTION_NAMES.has(word.toLowerCase())) {
    // A word ("the area(r^2)") stays prose; the bracket beside it still groups.
    return head[0] === word ? open : null;
  }
  // "-3(x^2 + 1)": a leading minus is the term's sign.
  return before === "-" && /^[\s(=]?$/.test(seg[start - 2] ?? "") ? start - 1 : start;
}

/** Each bracketed formula in a prose segment, its glued head and tail included. */
export function bracketRuns(seg: string, mathLike: (inside: string) => boolean): BracketRun[] {
  const runs: BracketRun[] = [];
  let floor = 0;
  for (let open = seg.indexOf("(", floor); open >= 0; open = seg.indexOf("(", floor)) {
    const close = closingBracket(seg, open);
    if (close < 0) {
      floor = open + 1;
      continue;
    }
    const end = runEnd(seg, close);
    const start = headStart(seg, open, floor);
    const run = seg.slice(start ?? open, end);
    // A price before it ("costs $5 (x^2 …)") would pair its dollar with the formula's.
    const price = /\$\s?\d/.test(seg.slice(0, start ?? open));
    if (start === null || price || !(mathLike(run) || groupInsides(run).some(mathLike))) {
      floor = end;
      continue;
    }
    const glued = start < open || end > close + 1 || /[\])}^_A-Za-z0-9]/.test(seg[open - 1] ?? "");
    runs.push({
      start,
      end,
      latex: bracketRunLatex(glued ? run : seg.slice(open + 1, close).trim()),
      delimited: !glued,
    });
    floor = end;
  }
  return runs;
}

/** A bracketed power braced (`2^(x+1)` → `2^{x+1}`): its brackets only group the exponent,
 * and a script took the bracket alone ("2^(" raised, "x+1)" on the line). */
export function bracePowers(text: string): string {
  let out = "";
  let last = 0;
  for (let at = text.indexOf("^("); at >= 0; at = text.indexOf("^(", last)) {
    const close = closingBracket(text, at + 1);
    if (close < 0) break;
    out += `${text.slice(last, at)}^{${bracePowers(text.slice(at + 2, close))}}`;
    last = close + 1;
  }
  return out + text.slice(last);
}
