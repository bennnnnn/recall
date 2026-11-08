/**
 * What the composer's math preview draws, decided without React: whether a draft
 * or a sent message shows it, a run's label, and the size a script is drawn at.
 */
import { textLooksLikeMath } from "@/lib/math/composerIntent";
import type { DraftNode } from "@/lib/math/draftNodes";
import { SCRIPT_RATIO } from "@/lib/math/layout";
import { latexNameKind } from "@/lib/math/latexNames";
import { spokenFormula } from "@/lib/math/spokenFormula";
import { isMostlyProsePaste } from "@/lib/math/pasteNormalize";
import {
  NATIVE_LITERAL_LEFT_BRACE_MARKER,
  NATIVE_LITERAL_RIGHT_BRACE_MARKER,
} from "@/lib/math/textMarkers";

/**
 * True when the composer draft should show the live math preview.
 * Shows when the input contains `$` (explicit math delimiters) OR when it
 * looks like math content (LaTeX commands, math symbols, bare equations)
 * even without `$` — so typing `√9` or `x^2 = 4` shows the preview without
 * requiring the user to manually wrap in `$...$`.
 *
 * Note: `UserMessageContent` uses its own check (only `$`) for sent messages;
 * this broader check is for the live composer draft only.
 */
export function draftShowsMathPreview(input: string): boolean {
  const s = input.trim();
  if (s.length === 0) return false;
  // Commands between `$`s (`\partial`, `\nabla`) are math, not words: a row of
  // calculus keys read as prose, and the preview (and a sent bubble) went blank.
  if (s.includes("$") && !/[A-Za-z]{2,}/.test(proseOutsideMath(s))) return true;
  if (isMostlyProsePaste(s)) return false;
  if (input.includes("$")) return true;
  return textLooksLikeMath(input);
}

/**
 * True when a *sent* user message should render via `MathDraftPreview`.
 * Unlike the composer, sent messages only use the preview when the user
 * explicitly wrapped math in `$...$` — bare equations in sent messages
 * render through the normal markdown path (which handles implicit math).
 *
 * Multi-line / display-math pastes (`\[...\]`, `$$...$$`) must not use the
 * composer preview: wrapping them in one `$` row left a tall empty bubble.
 * A sentence that only contains an equation stays markdown, so the words
 * are not dropped and the bubble is not left as a dot.
 */
/** Words outside `$...$`. A question around an equation is a sentence. */
function proseOutsideMath(input: string): string {
  let out = "";
  let i = 0;
  while (i < input.length) {
    if (input[i] === "$") {
      const close = input.indexOf("$", i + 1);
      if (close > i) {
        i = close + 1;
        continue;
      }
    }
    out += input[i];
    i += 1;
  }
  return out;
}

export function sentMessageShowsMathPreview(input: string): boolean {
  const s = input.trim();
  if (!s.includes("$") || s.length === 0) return false;
  if (s.includes("\n")) return false;
  if (s.includes("\\[") || s.includes("\\]") || s.includes("$$")) return false;
  if (s.length > 160) return false;
  // The composer preview drops the words and the bubble collapses to a dot.
  if (/[A-Za-z]{2,}/.test(proseOutsideMath(s))) return false;
  return true;
}

// A command's argument (`\mathbb{N}`, `\mathrm{i}`) is read by MathText, braces and all.
const COMMAND_ARGUMENT = /\\[A-Za-z]+\{[^{}]*\}/g;

/** Drop TeX grouping braces, but keep `\{` and `\}` as the braces the user typed. */
function composerTextLabel(raw: string): string {
  let label = "";
  let last = 0;
  for (const found of raw.matchAll(COMMAND_ARGUMENT)) {
    label += dropGroupingBraces(raw.slice(last, found.index)) + found[0].replace(/\$/g, "");
    last = found.index + found[0].length;
  }
  return label + dropGroupingBraces(raw.slice(last));
}

function dropGroupingBraces(raw: string): string {
  return raw
    .replace(/\$/g, "")
    .replace(/\\\{/g, NATIVE_LITERAL_LEFT_BRACE_MARKER)
    .replace(/\\\}/g, NATIVE_LITERAL_RIGHT_BRACE_MARKER)
    .replace(/[{}]/g, "")
    .split(NATIVE_LITERAL_LEFT_BRACE_MARKER)
    .join("{")
    .split(NATIVE_LITERAL_RIGHT_BRACE_MARKER)
    .join("}");
}

/** The formula's text size. A script draws smaller, as MathText draws one in a reply. */
export const DRAFT_TEXT_SIZE = 16;
const MIN_SCRIPT_SIZE = 9;

export function scriptSize(size: number): number {
  return Math.max(MIN_SCRIPT_SIZE, Math.round(size * SCRIPT_RATIO));
}

/** Text between `$`s is math: a lone `x` is the italic variable, not prose. */
function insideInlineMath(input: string, index: number): boolean {
  let open = false;
  for (let i = 0; i < index; i += 1) {
    if (input[i] === "$" && input[i - 1] !== "\\") open = !open;
  }
  return open;
}

/** A run of draft text and whether it is math (between `$`s) or prose; `$` dropped. */
export function textRuns(input: string, start: number, end: number): { math: boolean; text: string }[] {
  const runs: { math: boolean; text: string }[] = [];
  let math = insideInlineMath(input, start);
  let from = start;
  for (let i = start; i <= end; i += 1) {
    if (i < end && !(input[i] === "$" && input[i - 1] !== "\\")) continue;
    const text = composerTextLabel(input.slice(from, i));
    if (text) runs.push({ math: math && text.trim().length > 0, text });
    math = !math;
    from = i + 1;
  }
  return runs;
}

/** What a screen reader says for a sent math message: its prose, and its maths as words. */
export function spokenDraft(input: string): string {
  return textRuns(input, 0, input.length)
    .map((run) => (run.math ? spokenFormula(run.text) : run.text))
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}

type TextNode = Extract<DraftNode, { kind: "text" }>;

/**
 * A run ending in ∫, ∑, ∏ or lim, split at that operator: the text before it is
 * drawn as text, so `$\\int $ $\\int_{a}^{b}$` keeps its first ∫. The operator starts at
 * the run's last backslash (the caller has matched it at the end).
 */
export function splitBeforeOperator(input: string, run: TextNode): { lead: TextNode | null; operator: TextNode } {
  const at = run.start + input.slice(run.start, run.end).lastIndexOf("\\");
  const lead = input.slice(run.start, at).replace(/[$\s]/g, "") ? { ...run, end: at } : null;
  return { lead, operator: { ...run, start: at } };
}

/** Operations and relations a reply spaces on both sides when they sit between two terms. */
const SPACED_OPERATOR_NAMES = new Set([
  "times", "div", "pm", "mp", "cdot", "leq", "geq", "le", "ge", "neq", "ne", "approx", "equiv",
  "sim", "cong", "to", "in", "notin", "subset", "subseteq", "cup", "cap",
]);
const SPACED_OPERATOR_CHARS = new Set(["+", "-", "=", "<", ">"]);
/** After one of these a `-` or `+` is a sign (`(-3`, `x^-1`, `a, -b`), not an operation. */
const OPENS_TERM = new Set(["(", "[", "{", "\\{", ",", "^", "_"]);
const DRAFT_TOKEN = /\\[A-Za-z]+|\\.|\s+|./gsu;
/** A space the renderer keeps at either end of a run, where it trims a plain one (`\,`). */
const EDGE_SPACE = "\\,";

type DraftToken = {
  text: string;
  /** An operation or relation (`+`, `\times`), spaced when a term comes before it. */
  operator: boolean;
  /** A command drawn as one symbol (`\pi`, `\times`): a space after it only ends its name. */
  symbol: boolean;
};

function draftToken(text: string): DraftToken {
  const name = /^\\([A-Za-z]+)$/.exec(text)?.[1];
  const operator = SPACED_OPERATOR_CHARS.has(text) || (name != null && SPACED_OPERATOR_NAMES.has(name));
  const symbol = name != null && (SPACED_OPERATOR_NAMES.has(name) || latexNameKind(name) === "symbol");
  return { text, operator, symbol };
}

/**
 * A draft's maths as the preview draws it, spaced the way a reply's is. The keys type
 * `\times ` and `\pi ` with a space that only ends the command and `+` with none, and the
 * preview draws every space it is given, so `3+1\times 2` read "3+1× 2". An operation
 * between two terms gets one space each side, while a sign (`-3`, `(-x`) and, with
 * `tight`, a script's maths stay close; a space that only ended a symbol's name is dropped
 * (`{}` ends it before a letter: `2\pi{}r` draws "2πr"). `termBefore`: a term (a fraction,
 * a root) sits just before this run. The draft itself is never changed.
 */
export function spacedDraftMath(latex: string, { termBefore = false, tight = false } = {}): string {
  let out = "";
  let afterTerm = termBefore;
  let last: (DraftToken & { spaced: boolean }) | null = null;
  let space = false;
  // Each open brace, and whether it holds a script (`x^{n+1}`), which stays close.
  const groups: boolean[] = [];
  for (const [text] of latex.matchAll(DRAFT_TOKEN)) {
    if (!text.trim()) {
      space = true;
      continue;
    }
    const token = draftToken(text);
    if (text === "{") groups.push(last?.text === "^" || last?.text === "_");
    if (text === "}") groups.pop();
    if (token.operator && afterTerm && !tight && !groups.includes(true)) {
      out = `${out.trimEnd() || EDGE_SPACE}${out.trim() ? " " : ""}${text} `;
      last = { ...token, spaced: true };
      afterTerm = false;
      space = false;
      continue;
    }
    if (space && !last?.spaced) out += last?.symbol ? (/^[A-Za-z]/.test(text) ? "{}" : "") : " ";
    out += text;
    last = { ...token, spaced: false };
    afterTerm = !token.operator && !OPENS_TERM.has(text);
    space = false;
  }
  if (last?.spaced) return `${out.trimEnd()}${EDGE_SPACE}`;
  return space && last && !last.symbol ? `${out} ` : out;
}

/** Whether a term (a fraction, a root, a script) ends just before `at` in the draft. */
export function draftTermBefore(input: string, at: number): boolean {
  return /[^\s${([]$/.test(input.slice(0, at).trimEnd());
}
