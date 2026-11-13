/**
 * TeX scripts written in words: a student's "Evaluate ∑_{k=1}^{10} (3k − 1)" and
 * "lim_{x→9}", a part's title "Right-hand limit as x → 5^+". Drawn as text, their braces
 * and carets showed (2026-11-13). A word of maths written with a script is read as maths,
 * one `$…$` span the renderer draws: the whole run between spaces (`x^{2}y^{3}`,
 * `e^{2x}sin(x)`), never a piece of it.
 *
 * A script hangs on a letter, a number, a closing bracket, a big operator (∑ ∫ ∏) or an
 * operator's name (lim, max, log). A caret is a power after up to three letters (`mc^2`,
 * never `Ctrl^C`). An underscore is often a word's (file_name, a_b test, snake_case), so it
 * is a script only in braces after one letter or an operator (`a_{n}`, `lim_{x→0}`), with a
 * number after one letter (`x_1`), or under an operator (`∫_0^1`). A script glued after a
 * formula's closing dollar joins the formula (`$\to 5$^+` is `$\to 5^+$`).
 *
 * Only plain words are read. A line with TeX of its own (`\(`, `\[`, `$$`, a `\command`
 * outside its maths), code, a link or an image, bold or emphasis markers, or a currency
 * dollar is left exactly as written, for the markdown's own reading.
 *
 * `plain: false` reads only scripts in braces and an operator's (a sent message's `x^2` is
 * the markdown's implicit maths); `sentScriptsAsMath` reads a sent message only where that
 * implicit maths leaves a script as text.
 */
import { applyOutsideFences } from "@/lib/fence/scan";
import { readGroup } from "@/lib/math/latexGroups";
import { normalizeImplicitMath } from "@/lib/math/normalizeImplicit";
import { applyOutsideInlineMath } from "@/lib/math/proseDollars";

// Markup a span would cut through, and TeX written another way: the line is left as it is.
const LEAVE_LINE = /\\[([]|\$\$|`|\]\(|\*\*|__|(?:^|\s)[*_]\S/;
const COMMAND = /\\[A-Za-z]/;
const BIG_OPERATOR = /[∑∏∐∫∬∭∮⋃⋂]/;
// Operators the renderer sets upright, which take scripts as limits or powers.
const OPERATOR_NAMES = new Set([
  "lim", "liminf", "limsup", "max", "min", "sup", "inf", "log", "ln", "sin", "cos", "tan",
]);
// What a word of maths is made of. A word in another alphabet, a quote or a colon is not one.
const MATHS_WORD = /^[A-Za-zα-ωΑ-Ω0-9+\-−×·*/=<>≤≥≠≈()[\]{}^_.,′″|!→←↑↓∞√∈∉∅½¼¾⁰-⁹⁺⁻₀-₉∑∏∐∫∬∭∮⋃⋂]+$/;
// An address: a domain, a path, a mail.
const ADDRESS = /:\/\/|www\.|@|[A-Za-z]\.[A-Za-z]{2,}/;
const POWER = /^(?:[+\-−]?\d+|[+\-−∗*′]|[A-Za-z](?![A-Za-z]))/;
const INDEX = /^\d+/;
// The most letters a product of variables written before a power runs to (`abc^2`).
const MAX_PRODUCT = 3;
// A script's braces hold a short formula on one line.
const MAX_GROUP = 60;
// A script written straight after a formula's closing dollar is the formula's: a reply's
// "as x $\to 5$^+" showed its caret (2026-11-13). Never one a next formula opens on.
const GLUED_SCRIPT = /\$([^$\n]+)\$([\^_])(\{[^{}\n]{1,60}\}|[+\-−]?\d+|[+\-−∗*′]|[A-Za-z](?![A-Za-z]))(?!\$)/g;

/** What the script at `at` hangs on: an operator, one letter, a few letters, or another atom. */
function baseBefore(word: string, at: number): "operator" | "letter" | "letters" | "atom" | null {
  const before = word.slice(0, at);
  if (BIG_OPERATOR.test(before.at(-1) ?? "")) return "operator";
  const letters = /[A-Za-zα-ωΑ-Ω]+$/.exec(before)?.[0];
  if (letters) {
    if (OPERATOR_NAMES.has(letters)) return "operator";
    if (letters.length === 1) return "letter";
    return letters.length <= MAX_PRODUCT ? "letters" : null;
  }
  return /[0-9)\]}′]$/.test(before) ? "atom" : null;
}

/** Whether `word` holds a script that makes it maths. */
function holdsScript(word: string, plain: boolean): boolean {
  for (let at = 1; at < word.length; at += 1) {
    const mark = word[at];
    if (mark !== "^" && mark !== "_") continue;
    const base = baseBefore(word, at);
    if (!base) continue;
    const group = word[at + 1] === "{" ? readGroup(word, at + 1) : null;
    if (group && group.value.length <= MAX_GROUP) {
      if (mark === "^" || base === "operator" || base === "letter") return true;
      continue;
    }
    const bare = (mark === "^" ? POWER : INDEX).exec(word.slice(at + 1));
    if (base === "operator" && /^[A-Za-z0-9]/.test(word[at + 1] ?? "")) return true;
    if (bare && plain && (mark === "^" || base === "letter")) return true;
  }
  return false;
}

/** How many more brackets `text` opens than it closes. */
function openBrackets(text: string): number {
  return (text.match(/\(/g) ?? []).length - (text.match(/\)/g) ?? []).length;
}

/** Each bracket closes one opened before it, and every one is closed: `4)/(x^{2}` is no word. */
function nested(text: string): boolean {
  let depth = 0;
  for (const ch of text) {
    depth += ch === "(" || ch === "[" ? 1 : ch === ")" || ch === "]" ? -1 : 0;
    if (depth < 0) return false;
  }
  return depth === 0;
}

/**
 * One word between spaces, read as maths when it is one: brackets and stops around it stay.
 * Null for a word with a script that is no word of maths (`4)/(x^{2}`, `Ctrl^C`, an address):
 * its line is left whole, never read in part.
 */
function readWord(word: string, plain: boolean): string | null {
  let start = /^[("“‘[]*/.exec(word)?.[0] ?? "";
  let end = /[)"”’\].,;:!?]*$/.exec(word.slice(start.length))?.[0] ?? "";
  let core = word.slice(start.length, word.length - end.length);
  // A bracket the word opens or closes is its own: `(x^{2}+1)^{3}`, `f^{-1}(x)`.
  while (end.startsWith(")") && openBrackets(core) > 0) {
    core += ")";
    end = end.slice(1);
  }
  while (start.endsWith("(") && openBrackets(core) < 0) {
    core = `(${core}`;
    start = start.slice(0, -1);
  }
  // A longer word in it is a word (`Ctrl^C`, `sqrt(x^{2})`), not a product of variables.
  const words = (core.match(/[A-Za-z]{4,}/g) ?? []).filter((run) => !OPERATOR_NAMES.has(run));
  if (!core || !holdsScript(core, plain)) return word;
  if (words.length || !MATHS_WORD.test(core.replace(/\s/g, "")) || !nested(core) || ADDRESS.test(word)) return null;
  return `${start}$${core}$${end}`;
}

/** The segment's words of maths read, or null when one of its scripts cannot be. */
function readSegment(text: string, plain: boolean): string | null {
  let out = "";
  let i = 0;
  while (i < text.length) {
    if (/\s/.test(text[i]!)) {
      out += text[i];
      i += 1;
      continue;
    }
    // A word runs to the next space, a script's braces whole (`∑_{k = 1}^{n}`).
    let j = i;
    while (j < text.length && !/\s/.test(text[j]!)) {
      const group = text[j] === "{" ? readGroup(text, j) : null;
      j = group && !group.value.includes("\n") ? group.next : j + 1;
    }
    const read = readWord(text.slice(i, j), plain);
    if (read === null) return null;
    out += read;
    i = j;
  }
  return out;
}

function readLine(line: string, plain: boolean): string {
  if (!/[\^_]/.test(line) || LEAVE_LINE.test(line)) return line;
  // A currency dollar left in the words would pair with a new span's dollar, and TeX of
  // its own outside the maths is the markdown's to read.
  let leave = false;
  applyOutsideInlineMath(line, (prose) => {
    if (prose.includes("$") || COMMAND.test(prose)) leave = true;
    return prose;
  });
  if (leave) return line;
  let refused = false;
  const read = applyOutsideInlineMath(line, (prose) => {
    const words = readSegment(prose, plain);
    refused ||= words === null;
    return words ?? prose;
  });
  return refused ? line : read.replace(
    GLUED_SCRIPT,
    (_whole, body: string, mark: string, script: string) =>
      `$${body}${mark}${script.length > 1 && !script.startsWith("{") ? `{${script}}` : script}$`,
  );
}

/** `text` with each word of maths written with TeX scripts read as maths. */
export function typedScriptsAsMath(text: string, { plain = true } = {}): string {
  return applyOutsideFences(text, (prose) => prose.split("\n").map((line) => readLine(line, plain)).join("\n"));
}

/**
 * A sent message, read only where the markdown's implicit maths leaves a script as text
 * ("Evaluate lim_{x→9} …"); every other line stays exactly as written, for that reading.
 */
export function sentScriptsAsMath(text: string): string {
  return applyOutsideFences(text, (prose) =>
    prose
      .split("\n")
      .map((line) => {
        const implicit = normalizeImplicitMath(line);
        const read = readLine(implicit, false);
        return read === implicit ? line : read;
      })
      .join("\n"),
  );
}
