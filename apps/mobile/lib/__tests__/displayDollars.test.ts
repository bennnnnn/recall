/**
 * `$$` display maths, read the same by every reader on the phone and by the server's twin:
 * docs/fixtures/display_math_cases.json holds the cases both run (the server's test is
 * apps/api/app/tests/modules/chat/test_display_dollars.py).
 */
import { displayDollarsAfter, findDisplayDollars, type DisplayCloser } from "@/lib/markdown/displayDollars";
import { readInlineMathSpan } from "@/lib/markdown/inlineMath";
import { convertBlockMath } from "@/lib/markdown/preprocessMathBlocks";
import { findStableMarkdownPrefixLen } from "@/lib/markdown/preprocessStream";

import fixture from "../../../../docs/fixtures/display_math_cases.json";

type Case = { id: string; text: string; display: string[] };
const CASES = (fixture.cases as Case[]).map((c): [string, Case] => [c.id, c]);

const bodies = (text: string) =>
  findDisplayDollars(text).map(({ start, end }) => text.slice(start + 2, end - 2).trim());

describe("display dollars (docs/fixtures/display_math_cases.json)", () => {
  it.each(CASES)("%s: the reader finds its formulas", (_id, c) => {
    expect(bodies(c.text)).toEqual(c.display);
  });

  it.each(CASES)("%s: convertBlockMath makes a maths card of each, and only those", (_id, c) => {
    const out = convertBlockMath(c.text);
    const cards = [...out.matchAll(/```math\n([\s\S]*?)\n```/g)].map((m) => m[1]);
    expect(cards).toEqual(c.display);
  });

  it.each(CASES)("%s: the inline reader pairs the same dollars", (_id, c) => {
    const found: string[] = [];
    for (let i = 0; i < c.text.length; i += 1) {
      if (!c.text.startsWith("$$", i)) continue;
      const span = readInlineMathSpan(c.text, i, true);
      if (!span) continue;
      found.push(span.value);
      i = span.end - 1;
    }
    expect(found).toEqual(c.display);
  });

  it.each(CASES)("%s: the stream holds the text back only while a formula is open", (_id, c) => {
    const lines = c.text.split("\n");
    let open: DisplayCloser = null;
    for (const line of lines) open = displayDollarsAfter(line, open);
    const text = `${c.text}\n`;
    const stable = findStableMarkdownPrefixLen(text);
    // A table row holds the stream back of its own (it may still grow).
    if (!/\|\s*$/.test(c.text)) expect(stable === text.length).toBe(open == null);
  });
});

describe("the price tiers B3 reported", () => {
  it("leaves a price range as text", () => {
    expect(convertBlockMath("Californian, $$–$$$, open late.")).toBe("Californian, $$–$$$, open late.");
  });

  it("keeps a numbered restaurant list a list", () => {
    const list = "1. **Nopa** – $$$.\n2. **Zuni** – $$.\n3. **Tartine** – $$.\n\nAll three take bookings.";
    expect(convertBlockMath(list)).toBe(list);
  });
});
