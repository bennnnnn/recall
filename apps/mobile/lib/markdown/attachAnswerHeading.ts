import { ANSWER_LABEL_LINE, isVerifiedAnswer } from "@/lib/answerNotation";

const ANSWER_HEADINGS = new Set(["**Answer**", "**Answer:**"]);

function isAnswerHeading(line: string): boolean {
  return ANSWER_HEADINGS.has(line.trim());
}

/** The fence opened at ``fenceAt`` is the server's card: its header has the marker. */
function opensVerified(lines: string[], fenceAt: number): boolean {
  const body: string[] = [];
  for (let j = fenceAt + 1; j < lines.length && !(lines[j] ?? "").startsWith("```"); j += 1) {
    body.push(lines[j] ?? "");
  }
  return isVerifiedAnswer(body.join("\n"));
}

/**
 * A lesson writes **Answer** as the paragraph above the answer fence, so the
 * word lands on its own line and the equation sits below it. Move that word
 * into the fence; the chip draws it on the equation's row.
 */
export function attachAnswerHeadingToFence(markdown: string): string {
  const lines = markdown.split("\n");
  const out: string[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    if (!isAnswerHeading(lines[i] ?? "")) {
      out.push(lines[i] ?? "");
      continue;
    }
    let fenceAt = i + 1;
    while (fenceAt < lines.length && (lines[fenceAt] ?? "").trim() === "") fenceAt += 1;
    const opener = lines[fenceAt];
    // Only the server's checked card draws "Answer" beside it. An unmarked fence
    // renders as ordinary math, which has no label, so the heading stays a heading.
    if (opener === undefined || !opener.startsWith("```answer") || !opensVerified(lines, fenceAt)) {
      out.push(lines[i] ?? "");
      continue;
    }
    out.push(opener);
    if ((lines[fenceAt + 1] ?? "").trim() !== ANSWER_LABEL_LINE) {
      out.push(ANSWER_LABEL_LINE);
    }
    i = fenceAt;
  }
  return out.join("\n");
}
