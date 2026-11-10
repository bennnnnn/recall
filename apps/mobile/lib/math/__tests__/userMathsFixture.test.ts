/**
 * docs/fixtures/user_maths_cases.json holds maths a user types as plain text, the markdown its
 * sent bubble draws, and the words the server reads it from; the API's test
 * (test_user_maths_fixture.py) holds the drawn maths and the typed words to one SymPy
 * expression. A bracket that groups an argument, a factor or an exponent keeps its meaning:
 * "ln(x^2 + 1)" once drew as "ln x² + 1", and "sin(x^2)cos(x^2)" broke into a display block.
 */
import fixture from "../../../../../docs/fixtures/user_maths_cases.json";
import { preprocessMarkdown } from "@/lib/markdown/preprocess";
import { withTypedLineBreaks } from "@/lib/markdown/typedLineBreaks";
import { displayMathToInline } from "@/lib/math/solutionBars";
import { restoreMathEscapes } from "@/lib/math/text";

type Case = { id: string; text: string; drawn: string; typed: string };

const CASES = (fixture as unknown as { cases: Case[] }).cases;

/** The markdown a sent bubble draws, as `UserBubbleBody` prepares it (the escapes markdown
 * must not read, `_` among them, restored as the maths parser restores them). */
function bubbleMarkdown(text: string): string {
  return restoreMathEscapes(preprocessMarkdown(withTypedLineBreaks(displayMathToInline(text)))).trim();
}

describe("a sent message's maths, as the server reads it", () => {
  it.each(CASES.map((c) => [c.id, c] as const))("%s", (_id, c) => {
    expect(c.text).toContain(c.typed);
    expect(bubbleMarkdown(c.text)).toBe(c.drawn);
  });
});
