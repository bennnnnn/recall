/** First line of a server answer fence. Absent means the body is LaTeX. */

export const CHEMISTRY_ANSWER_NOTATION = "notation: chemistry";

export function visibleAnswerBody(raw: string): string {
  const text = raw.replace(/\r\n/g, "\n").trim();
  const newline = text.indexOf("\n");
  if (newline > 0 && text.slice(0, newline).trim() === CHEMISTRY_ANSWER_NOTATION) {
    return text.slice(newline + 1).trim();
  }
  return text;
}
