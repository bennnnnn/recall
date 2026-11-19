/**
 * A diagram's labels as the card draws them (the user, 2026-11-18: "stop it showing random
 * stuff in this flow chart"). The model decorates labels with emoji (🖐️ Small piston,
 * 📦 Load), and a label with a line break draws its `>` and `<` as "&gt;" and "&lt;": Mermaid
 * escapes such a label's text and SVG text shows the escape (Mermaid's own entity codes fix
 * it in a node label, not in an edge label, and never for `<`). So, in each label of a
 * node or an edge, whatever its shape (`[…]`, `(…)`, `{…}`, `|…|`, `>…]`, `[/…/]`, `[\…\]`
 * and their doubled forms): a quoted one runs from its quote to the closing quote before
 * the shape's closing bracket, across lines too; an unquoted one is the text on its line
 * between the brackets:
 *
 * - no emoji: a pictograph shown as an emoji (its own presentation, or asked for by U+FE0F),
 *   with the joiners, skin tones and keycap marks that build one. Plain symbols such as ©,
 *   ™ or ≥ stay. A label that is nothing but emoji keeps them: an empty label is no diagram.
 * - in a label with a line break, its own `>` and `<` as the small-form signs ﹥ and ﹤,
 *   which draw like them with no escape.
 *
 * Nothing outside a label changes: arrows, names and identifiers are syntax. Display only:
 * the source view and Copy keep the diagram as the model wrote it.
 */

const EMOJI =
  /(?:[0-9#*]️?⃣|(?:\p{Emoji_Presentation}|\p{Extended_Pictographic}️)(?:️|‍(?:\p{Extended_Pictographic}️?)?|\p{Emoji_Modifier})*)/gu;
/** A quoted label: its opening brackets (`>` opens the flag shape), its text (any lines), and the closing bracket after it. */
const QUOTED_LABEL = /([[({|]+[/\\]?|>)"([\s\S]*?)"(?=[/\\]?[\])}|])/g;
/** An unquoted label: its opening brackets (a name's `>` opens the flag shape), its text on one line (no quote, no bracket), and the closing bracket after it. */
const BARE_LABEL = /([[({|]+[/\\]?|\w>)([^"[\](){}|\n]+?)(?=[/\\]?[\])}|])/g;
const LINE_BREAK = /<br\s*\/?>/i;

/** A label's text without emoji and the space they leave; as written when nothing is left. */
function withoutEmoji(text: string): string {
  const bare = text.replace(EMOJI, "");
  if (bare === text) return text;
  const tidy = bare
    .split(/(<br\s*\/?>)/i)
    .map((part) => (LINE_BREAK.test(part) ? part : part.replace(/[ \t]{2,}/g, " ").trim()))
    .join("");
  return tidy.replace(/<br\s*\/?>/gi, "").trim() ? tidy : text;
}

/** A label's own > and < as small forms, when a line break would have them escaped. */
function withSigns(text: string): string {
  if (!LINE_BREAK.test(text)) return text;
  return text
    .split(/(<br\s*\/?>)/i)
    .map((part) => (LINE_BREAK.test(part) ? part : part.replace(/>/g, "﹥").replace(/</g, "﹤")))
    .join("");
}

/** A label's text as drawn: no emoji, and its signs drawn as written. */
function displayText(text: string): string {
  return withSigns(withoutEmoji(text));
}

export function mermaidDisplaySource(source: string): string {
  return source
    .replace(QUOTED_LABEL, (_whole, open: string, text: string) => `${open}"${displayText(text)}"`)
    .replace(BARE_LABEL, (_whole, open: string, text: string) => `${open}${displayText(text)}`);
}
