/**
 * Server-owned answer fences are LaTeX unless the first line says otherwise.
 *
 * Chemistry (and any later literal subject) keeps formulas, charges, and units
 * as text. Treating that body as algebra rewrites a correct result.
 */

export type AnswerNotation = "math" | "chemistry";

export const CHEMISTRY_ANSWER_NOTATION = "notation: chemistry";

export function splitAnswerNotation(raw: string): { notation: AnswerNotation; body: string } {
  const text = raw.replace(/\r\n/g, "\n").trim();
  const newline = text.indexOf("\n");
  if (newline > 0 && text.slice(0, newline).trim() === CHEMISTRY_ANSWER_NOTATION) {
    return { notation: "chemistry", body: text.slice(newline + 1).trim() };
  }
  return { notation: "math", body: text };
}
