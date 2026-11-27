/**
 * Each pass that reads `$$` asks the shared reader (displayDollars.ts), so a price tier
 * reaches the screen, the copy and the voice as written. Reverting any one pass to its own
 * `$$` pairing fails its row here. The cases are docs/fixtures/display_math_cases.json's
 * one-line price tiers; the server's twin is
 * apps/api/app/tests/modules/chat/test_display_dollars.py.
 */
import { layoutCalculations } from "@/lib/markdown/calculationLayout";
import { repairInlineTokenBoundaries } from "@/lib/markdown/inlineBoundaries";
import { codeNotation } from "@/lib/markdown/notationSpans";
import { markdownToCopyText, markdownToSpeechText } from "@/lib/markdown/plain";
import { presentStreamTail } from "@/lib/markdown/presentation";
import { normalizeImplicitMath } from "@/lib/math/normalizeImplicit";
import { displayMathToInline } from "@/lib/math/solutionBars";
import { prepareStreamingMathText } from "@/lib/math/streaming";

import fixture from "../../../../docs/fixtures/display_math_cases.json";

type Case = { id: string; text: string; display: string[] };

/** One-line texts with dollar runs and no formula: prices. */
const PRICES = (fixture.cases as Case[])
  .filter((c) => c.display.length === 0 && !c.text.includes("\n") && !c.text.includes("`") && !c.text.includes("\\"))
  .map((c): [string, string] => [c.id, c.text]);

/** The dollar runs of `text`, in order: a pass that kept the prices keeps these. */
const runs = (text: string) => text.match(/\$+/g) ?? [];

describe("every $$ reader leaves a price tier as written", () => {
  it("has price cases to read", () => {
    expect(PRICES.length).toBeGreaterThan(5);
  });

  it.each(PRICES)("%s: inline token boundaries", (_id, text) => {
    expect(repairInlineTokenBoundaries(text)).toBe(text);
  });

  it.each(PRICES)("%s: calculation layout", (_id, text) => {
    expect(layoutCalculations(text)).toBe(text);
  });

  it("calculation layout splits no chain a price tier closes", () => {
    // Paired with the first two dollars of "$$$", this chain was laid out in rows.
    expect(layoutCalculations("$$x = 1 + 1 = 2$$$")).toBe("$$x = 1 + 1 = 2$$$");
    expect(layoutCalculations("Then $$x = 1 + 1 = 2$$.")).toBe("Then\n$$x = 1 + 1$$  \n$$x = 2$$.");
  });

  it.each(PRICES)("%s: copied and spoken text keep the dollars", (_id, text) => {
    expect(runs(markdownToCopyText(text))).toEqual(runs(text));
    expect(runs(markdownToSpeechText(text))).toEqual(runs(text));
  });

  it.each(PRICES)("%s: the live line shows it at once", (_id, text) => {
    expect(prepareStreamingMathText(text)).toEqual({ text, pending: false });
  });

  it.each(PRICES.filter(([, text]) => !text.startsWith("|")))(
    "%s: the stream tail presents the prose after a tier",
    (_id, text) => {
      // Read as an open formula, the tier held the rest of the tail raw: the glued bold after
      // it kept no space (openMathStart, review #2606).
      expect(presentStreamTail(`${text} Try **brunch**now.`)).toContain("**brunch** now.");
    },
  );

  it.each(PRICES)("%s: the user bubble's compact maths", (_id, text) => {
    expect(displayMathToInline(text)).toBe(text);
  });

  it("a SMILES string between two tiers paragraphs apart is still code (review #2606)", () => {
    const text = "Zuni – $$.\n\nIts smell is CC(=O)O.\n\nTartine – $$.";
    expect(codeNotation(text)).toContain("`CC(=O)O`");
    // Between two tiers the prose is read for maths, as it is with no tier around it.
    const between = (outer: string) => normalizeImplicitMath(`${outer}\n\nThen x^2 = 4\n\n${outer}`).split("\n\n")[1];
    expect(between("Zuni – $$.")).toBe(between("Zuni."));
  });
});

describe("a formula still reads as one", () => {
  it("keeps a tight $$x$$ whole through the inline readers", () => {
    expect(repairInlineTokenBoundaries("So $$|x| = 3$$ has two answers.")).toBe("So $$|x| = 3$$ has two answers.");
    expect(displayMathToInline("So $$|x| = 3$$ here")).toBe("So $|x| = 3$ here");
  });

  it("holds the live line while a line-final $$ waits for its formula", () => {
    expect(prepareStreamingMathText("Therefore: $$").pending).toBe(true);
    expect(prepareStreamingMathText("Cafe – $$. Great brunch").pending).toBe(false);
  });
});

describe("a line of many pairs is read once (review #2606 round 2)", () => {
  it.each([
    ["tight pairs", "$$x$$ ".repeat(5_000)],
    ["price tiers", "Nopa – $$. ".repeat(5_000)],
    ["padded pairs", "$$ x = 1 $$ and ".repeat(3_000)],
  ])("%s", (_name, line) => {
    const started = performance.now();
    repairInlineTokenBoundaries(line);
    layoutCalculations(line);
    displayMathToInline(line);
    markdownToCopyText(line);
    // Each reader asked about every `$$`, and each question read the line from its start.
    expect(performance.now() - started).toBeLessThan(2_000);
  });
});
