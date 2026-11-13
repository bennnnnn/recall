/**
 * TeX scripts written in words: a student's "Evaluate ∑_{k=1}^{10} (3k − 1)" and
 * "lim_{x→9}", a part's title "Right-hand limit as x → 5^+". Drawn as text, their braces
 * and carets showed (2026-11-13). Each atom written with its scripts is read as maths, a
 * `$…$` span the renderer draws: a letter, a number, a big operator (∑ ∫ ∏) or an
 * operator's name (lim, max, log) starting a word, then its `^…` and `_…`.
 *
 * A caret is always a power. An underscore is often a word's (file_name, a_b test,
 * snake_case), so it is a script only in braces (`_{k=1}`), with a number after one letter
 * (`x_1`), or under an operator (`∫_0^1`, `lim_x`). What is maths already, inline code,
 * fences, links and a line with a currency dollar are left as written. A script glued
 * after a formula's closing dollar joins the formula (`$\to 5$^+` is `$\to 5^+$`).
 *
 * `plain: false` reads only scripts in braces and an operator's: a sent message's `x^2`
 * and `(x^2 - 4)` are read by the reply's own implicit maths, brackets and all.
 */
import { applyOutsideFences } from "@/lib/fence/scan";
import { readGroup } from "@/lib/math/latexGroups";
import { applyOutsideInlineMath } from "@/lib/math/proseDollars";

const BIG_OPERATOR = /^[∑∏∐∫∬∭∮⋃⋂]/;
// The operators the renderer sets upright that take limits under them.
const OPERATOR_NAMES = new Set(["lim", "liminf", "limsup", "max", "min", "sup", "inf", "log", "ln"]);
const LETTERS = /^[A-Za-zα-ωΑ-Ω]+/;
const NUMBER = /^\d+(?:\.\d+)?/;
const POWER = /^(?:[+\-−]?\d+|[+\-−∗*′]|[A-Za-z](?![A-Za-z]))/;
const INDEX = /^(?:\d+|[A-Za-z](?![A-Za-z]))/;
// The most letters a product of variables written before a power runs to (`abc^2`).
const MAX_PRODUCT = 3;
// A script written straight after a formula's closing dollar is the formula's: a reply's
// "as x $\to 5$^+" showed its caret (2026-11-13).
const GLUED_SCRIPT = /\$([^$\n]+)\$([\^_])(\{[^{}\n]{1,60}\}|[+\-−]?\d+|[+\-−∗*′]|[A-Za-z](?![A-Za-z]))/g;
// A script's braces hold a short formula on one line.
const MAX_GROUP = 60;

/** `word`: a few letters that are no operator, a product of variables (`mc^2`, `ab^2`): a
 * base only for a power, never for an underscore (file_name). A longer word is a word
 * (`Ctrl^C`). */
type Base = { length: number; operator: boolean; letter: boolean; word: boolean };

/** The atom a script may hang on, starting a word at `i`. */
function baseAt(text: string, i: number): Base | null {
  if (i > 0 && /[\p{L}\p{N}_\\^]/u.test(text[i - 1]!)) return null;
  const rest = text.slice(i);
  if (BIG_OPERATOR.test(rest)) return { length: 1, operator: true, letter: false, word: false };
  const letters = LETTERS.exec(rest)?.[0];
  if (letters) {
    const operator = OPERATOR_NAMES.has(letters);
    if (!operator && letters.length > MAX_PRODUCT) return null;
    return { length: letters.length, operator, letter: letters.length === 1, word: letters.length > 1 && !operator };
  }
  const number = NUMBER.exec(rest)?.[0];
  return number ? { length: number.length, operator: false, letter: false, word: false } : null;
}

/**
 * The scripts after a base at `at` as TeX, and where they end; null when they do not make
 * it maths. A bare script of more than one glyph takes braces (`10^-3` is `10^{-3}`).
 */
function scriptsAt(text: string, at: number, base: Base, plain: boolean): { tex: string; end: number } | null {
  if (base.word && text[at] !== "^") return null;
  let j = at;
  let tex = "";
  let maths = base.operator;
  for (let count = 0; count < 2 && (text[j] === "^" || text[j] === "_"); count += 1) {
    const caret = text[j] === "^";
    const group = text[j + 1] === "{" ? readGroup(text, j + 1) : null;
    if (group && group.value.length <= MAX_GROUP && !group.value.includes("\n")) {
      maths = true;
      tex += text.slice(j, group.next);
      j = group.next;
      continue;
    }
    const bare = (caret ? POWER : INDEX).exec(text.slice(j + 1))?.[0];
    if (!bare) break;
    maths ||= plain && (caret || (base.letter && /^\d/.test(bare)));
    tex += `${text[j]}${bare.length > 1 ? `{${bare}}` : bare}`;
    j += 1 + bare.length;
  }
  return maths && j > at ? { tex, end: j } : null;
}

/** The whitespace-separated token around `i` is a link or an address. */
function inLink(text: string, i: number): boolean {
  const start = text.lastIndexOf(" ", i) + 1;
  const end = text.indexOf(" ", i);
  const token = text.slice(start, end < 0 ? text.length : end);
  return /:\/\/|www\.|@/.test(token);
}

function readSegment(text: string, plain: boolean): string {
  let out = "";
  let i = 0;
  while (i < text.length) {
    const base = baseAt(text, i);
    const scripts = base ? scriptsAt(text, i + base.length, base, plain) : null;
    if (base && scripts && !inLink(text, i)) {
      out += `$${text.slice(i, i + base.length)}${scripts.tex}$`;
      i = scripts.end;
      continue;
    }
    // A word is passed whole: "file_{x}" never reads from its "e".
    const skip = base ? base.length : Math.max(1, LETTERS.exec(text.slice(i))?.[0].length ?? 1);
    out += text.slice(i, i + skip);
    i += skip;
  }
  return out;
}

function readLine(line: string, plain: boolean): string {
  if (!/[\^_]/.test(line)) return line;
  // A currency dollar left in the words would pair with a new span's dollar.
  let currency = false;
  applyOutsideInlineMath(line, (prose) => {
    if (prose.includes("$")) currency = true;
    return prose;
  });
  if (currency) return line;
  return applyOutsideInlineMath(line, (prose) => readSegment(prose, plain)).replace(
    GLUED_SCRIPT,
    (_whole, body: string, mark: string, script: string) =>
      `$${body}${mark}${script.length > 1 && !script.startsWith("{") ? `{${script}}` : script}$`,
  );
}

/** `text` with each atom written with TeX scripts in its words read as maths. */
export function typedScriptsAsMath(text: string, { plain = true } = {}): string {
  return applyOutsideFences(text, (prose) => prose.split("\n").map((line) => readLine(line, plain)).join("\n"));
}
