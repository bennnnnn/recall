// **Answer**, **Answer:**, ## Answer, Answer: — the heading written above a card.
const ANSWER_HEADING = /^(?:#{1,4}\s+)?(?:\*\*)?answer:?(?:\*\*)?:?$/i;

function isAnswerHeading(line: string): boolean {
  return ANSWER_HEADING.test(line.trim());
}

/**
 * Every answer card draws its own "Answer" heading, checked or not. Drop the
 * **Answer** paragraph written above one so the word shows once.
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
    i = fenceAt - 1;
  }
  return out.join("\n");
}
