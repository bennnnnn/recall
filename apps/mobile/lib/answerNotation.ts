/**
 * Server-owned answer fences open with header lines, then the value.
 *
 * - `verified: true` — the server checked this value with a solver. It is the only
 *   thing that earns the card's green check; the server strips the line from anything
 *   a model writes, so a reply cannot forge it.
 * - `notation: chemistry` — the body is chemistry text, not LaTeX. Chemistry (and any
 *   later literal subject) keeps formulas, charges, and units as text; treating that
 *   body as algebra rewrites a correct result.
 * - `label: answer` — written here (attachAnswerHeading) to draw "Answer" over the card.
 */

export type AnswerNotation = "math" | "chemistry";

export const CHEMISTRY_ANSWER_NOTATION = "notation: chemistry";
export const ANSWER_LABEL_LINE = "label: answer";
export const VERIFIED_ANSWER_MARKER = "verified: true";

function headerLine(line: string): string | null {
  // The marker must be exactly the server's line: no case, spacing, or invisible
  // characters a forged copy could hide behind.
  if (line === VERIFIED_ANSWER_MARKER) return line;
  const trimmed = line.trim();
  return trimmed === CHEMISTRY_ANSWER_NOTATION || trimmed === ANSWER_LABEL_LINE ? trimmed : null;
}

export function splitAnswerNotation(raw: string): {
  notation: AnswerNotation;
  body: string;
  labeled: boolean;
  verified: boolean;
} {
  const lines = raw.replace(/\r\n/g, "\n").trim().split("\n");
  const headers = new Set<string>();
  // Header lines only at the top, and never the last line: a header with no value
  // after it is the value.
  while (lines.length > 1) {
    const header = headerLine(lines[0]!);
    if (header == null) break;
    headers.add(header);
    lines.shift();
  }
  return {
    notation: headers.has(CHEMISTRY_ANSWER_NOTATION) ? "chemistry" : "math",
    body: lines.join("\n").trim(),
    labeled: headers.has(ANSWER_LABEL_LINE),
    verified: headers.has(VERIFIED_ANSWER_MARKER),
  };
}
