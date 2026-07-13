import { parseSimpleLatex, segmentsToPlain, splitMathLines } from "@/lib/mathText";

describe("parseSimpleLatex", () => {
  it("parses superscripts", () => {
    const segs = parseSimpleLatex("x^2 + 2 = 6");
    expect(segmentsToPlain(segs)).toBe("x^2 + 2 = 6");
    expect(segs.some((s) => s.type === "sup" && s.value === "2")).toBe(true);
  });

  it("handles pm and sqrt", () => {
    const segs = parseSimpleLatex(String.raw`x = \pm \sqrt{4}`);
    expect(segmentsToPlain(segs)).toContain("±");
    expect(segmentsToPlain(segs)).toContain("√(4)");
  });

  it("parses fractions", () => {
    const segs = parseSimpleLatex(String.raw`\frac{a}{b}`);
    expect(segs).toEqual([{ type: "frac", num: "a", den: "b" }]);
  });

  it("BUG FIX regression: renders known function names without the leading backslash", () => {
    // \log_2(2) used to render literally as "\log_2(2)" in the no-WebView
    // (Expo Go) plain-text fallback since \log wasn't in CMD_REPLACEMENTS.
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\log_2(2)`))).toBe("log_2(2)");
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\sin(x) + \cos(x)`))).toBe(
      "sin(x) + cos(x)",
    );
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\lim_{x \to 0}`))).toBe("lim_x \\to 0");
  });

  it("still shows the backslash for a genuinely unknown command", () => {
    expect(segmentsToPlain(parseSimpleLatex(String.raw`\widehat{x}`))).toContain("\\widehat");
  });
});

describe("splitMathLines", () => {
  it("splits a multi-equation fence body into separate lines", () => {
    expect(splitMathLines("x^2 = 5 - 1\nx^2 = 4")).toEqual(["x^2 = 5 - 1", "x^2 = 4"]);
  });

  it("returns a single-element array for a one-line body", () => {
    expect(splitMathLines("x^2 = 4")).toEqual(["x^2 = 4"]);
  });

  it("drops blank lines", () => {
    expect(splitMathLines("x = 2\n\nx = -2\n")).toEqual(["x = 2", "x = -2"]);
  });
});
