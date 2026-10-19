/**
 * What the composer's math preview draws, decided without React: whether a draft
 * or a sent message shows it, a run's label, and the size a script is drawn at.
 */
import { textLooksLikeMath } from "@/lib/math/composerIntent";
import { SCRIPT_RATIO } from "@/lib/math/layout";
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

/** Drop TeX grouping braces, but keep `\{` and `\}` as the braces the user typed. */
export function composerTextLabel(raw: string): string {
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
export function insideInlineMath(input: string, index: number): boolean {
  let open = false;
  for (let i = 0; i < index; i += 1) {
    if (input[i] === "$" && input[i - 1] !== "\\") open = !open;
  }
  return open;
}
