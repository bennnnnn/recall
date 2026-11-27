import { displayMathLines } from "@/lib/markdown/markdownRegions";

describe("displayMathLines", () => {
  it.each([
    ["a $$ block across lines", ["$$", "x = 1", "$$", "after"], [true, true, true, false]],
    ["a \\[ block across lines", ["\\[", "a", "\\]", "after"], [true, true, true, false]],
    ["an escaped $$ opens nothing", ["\\$$ not maths", "next"], [false, false]],
    ["an escaped dollar closes nothing", ["$$x \\$$", "y", "$$"], [true, true, true]],
    ["an escaped backslash leaves $$ a closer", ["$$x \\\\$$", "next"], [false, false]],
    ["$$ in a code span opens nothing", ["`$$` code", "next"], [false, false]],
    ["a price tier mid-line opens nothing", ["Nopa – $$.", "Zuni – $$$.", "Bar – $$."], [false, false, false]],
    ["a list item ends a formula left open", ["- $$ = moderate", "- $$$ = pricey", "after"], [true, false, false]],
  ])("%s", (_name, lines, expected) => {
    expect(displayMathLines(lines)).toEqual(expected);
  });

  // Each character once counted the backslashes before it: a line of 16,000 of them took
  // 250-730 ms (jest), now under 1 ms.
  it("reads a long run of backslashes once", () => {
    const line = `$$a${"\\".repeat(16_001)}$$`;
    const start = performance.now();
    expect(displayMathLines([line, "x"])).toEqual([true, true]);
    expect(performance.now() - start).toBeLessThan(40);
  });
});
