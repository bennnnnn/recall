// **Answer**, **Answer:**, ## Answer, Answer: — the heading written above a card.
const ANSWER_HEADING = /^(?:#{1,4}\s+)?(?:\*\*)?answer:?(?:\*\*)?:?$/i;

function isAnswerHeading(line: string): boolean {
  return ANSWER_HEADING.test(line.trim());
}

// A line that only restates the value the card will show: maths, an "x = ...", or
// a "(or -2.5)" aside. Prose is working or an explanation and stays.
const RESTATED_VALUE = /^(?:\$[^$]+\$|\\\(.+\\\)|[A-Za-z]\s*[=≈<>≤≥].{0,40})(?:\s*\((?:or|about|≈)[^)]{0,30}\))?[.\s]*$/i;
// How far above its card a heading may sit, past restated values and other headings.
const MAX_LOOKAHEAD = 6;

/**
 * Every answer card draws its own "Answer" heading, checked or not. Drop the
 * **Answer** heading written above one, so the word shows once, and the lines
 * between them that only restate the card's value ("$x = -5/2$ (or -2.5)"):
 * kept, they read as a second Answer section. With no card below, a written-out
 * Answer section is the answer and stays as it is.
 */
export function attachAnswerHeadingToFence(markdown: string): string {
  const lines = markdown.split("\n");
  const out: string[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] ?? "";
    if (!isAnswerHeading(line)) {
      out.push(line);
      continue;
    }
    let fenceAt = -1;
    for (let j = i + 1; j < lines.length && j <= i + MAX_LOOKAHEAD; j += 1) {
      const next = (lines[j] ?? "").trim();
      if (next.startsWith("```answer")) {
        fenceAt = j;
        break;
      }
      if (next === "" || isAnswerHeading(next) || RESTATED_VALUE.test(next)) continue;
      break;
    }
    if (fenceAt === -1) {
      out.push(line);
      continue;
    }
    i = fenceAt - 1;
  }
  return out.join("\n");
}
