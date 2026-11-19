/**
 * A diagram's labels as the card draws them (the user, 2026-11-18: "stop it showing random
 * stuff in this flow chart"). The model decorates labels with emoji (🖐️ Small piston,
 * 📦 Load), and a label with a line break draws its `>` and `<` as "&gt;" and "&lt;": Mermaid
 * escapes the label's text and SVG text shows the escape. So the card draws:
 *
 * - no emoji: a pictograph shown as an emoji (its own presentation, or asked for by U+FE0F),
 *   with the joiners and keycap marks that build one. Plain symbols such as © or ™ stay.
 * - the small-form signs ﹥ and ﹤ for a label's own > and <, which draw like them with no
 *   escape, in node and edge labels alike. Only text inside a label's double quotes is
 *   touched: arrows (-->, ->>, <|--) are syntax, and <br/> is a line break.
 *
 * Display only: Copy keeps the diagram as the model wrote it.
 */

const EMOJI =
  /(?:[0-9#*]\uFE0F?\u20E3|(?:\p{Emoji_Presentation}|\p{Extended_Pictographic}\uFE0F)(?:\uFE0F|\u200D(?:\p{Extended_Pictographic}\uFE0F?)?|\p{Emoji_Modifier})*)/gu;
const QUOTED = /"[^"\n]*"/g;
const LINE_BREAK = /<br\s*\/?>/gi;

/** A label's line breaks, each kept as written, between the parts it splits. */
function eachLine(label: string, edit: (line: string) => string): string {
  const breaks = label.match(LINE_BREAK) ?? [];
  return label
    .split(LINE_BREAK)
    .map((line, index) => edit(line) + (breaks[index] ?? ""))
    .join("");
}

/** One line of a label: no emoji or the space they leave, and its own > and < as small forms. */
function drawnLine(line: string): string {
  const bare = line.replace(EMOJI, "");
  const tidy = bare === line ? line : bare.replace(/[ \t]{2,}/g, " ").trim();
  return tidy.replace(/>/g, "﹥").replace(/</g, "﹤");
}

/** Each quoted label as the card draws it, and any emoji left outside the quotes dropped. */
export function mermaidDisplaySource(source: string): string {
  const labelled = source.replace(QUOTED, (quoted) => `"${eachLine(quoted.slice(1, -1), drawnLine)}"`);
  return labelled.replace(EMOJI, "");
}
