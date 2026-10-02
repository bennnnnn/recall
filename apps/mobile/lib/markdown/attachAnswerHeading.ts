const ANSWER_HEADINGS = new Set(["**Answer**", "**Answer:**"]);
const ANSWER_LABEL_LINE = "label: answer";

function isAnswerHeading(line: string): boolean {
  return ANSWER_HEADINGS.has(line.trim());
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
    if (opener === undefined || !opener.startsWith("```answer")) {
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
