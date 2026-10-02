/**
 * Server-owned answer fences are LaTeX unless the first line says otherwise.
 *
 * Chemistry (and any later literal subject) keeps formulas, charges, and units
 * as text. Treating that body as algebra rewrites a correct result.
 */

export type AnswerNotation = "math" | "chemistry";

export const CHEMISTRY_ANSWER_NOTATION = "notation: chemistry";
export const ANSWER_LABEL_LINE = "label: answer";

export function splitAnswerNotation(raw: string): {
  notation: AnswerNotation;
  body: string;
  labeled: boolean;
} {
  let text = raw.replace(/\r\n/g, "\n").trim();
  let labeled = false;
  const firstBreak = text.indexOf("\n");
  if (firstBreak > 0 && text.slice(0, firstBreak).trim() === ANSWER_LABEL_LINE) {
    labeled = true;
    text = text.slice(firstBreak + 1).trim();
  }
  const newline = text.indexOf("\n");
  if (newline > 0 && text.slice(0, newline).trim() === CHEMISTRY_ANSWER_NOTATION) {
    return { notation: "chemistry", body: text.slice(newline + 1).trim(), labeled };
  }
  return { notation: "math", body: text, labeled };
}
