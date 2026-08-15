import {
  caretAfterExpression,
  caretBeforeExpression,
  findDraftNodes,
  hasTappableDraftSlot,
  spliceMathBackspace,
  stepMathCaret,
} from "@/lib/mathDraftSlots";

describe("findDraftNodes", () => {
  it("finds fractions, roots, scripts, abs, and groups", () => {
    const nodes = findDraftNodes("$\\frac{8}{8}\\sqrt{x}x^{2}|y|\\sin()$");
    expect(nodes.filter((n) => n.kind !== "text").map((n) => n.kind)).toEqual([
      "frac",
      "sqrt",
      "script",
      "abs",
      "group",
    ]);
    expect(hasTappableDraftSlot(nodes)).toBe(true);
  });

  it("keeps the continue caret inside the closing dollar", () => {
    expect(caretAfterExpression("$\\frac{8}{8}$")).toBe("$\\frac{8}{8}$".length - 1);
  });

  it("steps the caret from the front of a fraction to the numerator", () => {
    const text = "$\\frac{8}{8}$";
    const front = caretBeforeExpression(text);
    const next = stepMathCaret(text, front, 1);
    expect(next).toBeGreaterThan(front);
    const back = stepMathCaret(text, next, -1);
    expect(back).toBe(front);
  });
});

describe("spliceMathBackspace", () => {
  it("deletes a denominator digit without exposing raw \\frac braces", () => {
    const text = "$\\frac{8}{8}$";
    const den = text.lastIndexOf("8") + 1;
    const once = spliceMathBackspace(text, { start: den, end: den });
    expect(once.text).toBe("$\\frac{8}{}$");
    const twice = spliceMathBackspace(once.text, once.selection);
    expect(twice.text).toBe("$\\frac{}{}$");
    const gone = spliceMathBackspace(twice.text, twice.selection);
    expect(gone.text).toBe("");
  });

  it("deletes \\times after a fraction instead of the closing brace", () => {
    const text = "$\\frac{8}{8}\\times $";
    const caret = text.length - 1;
    const result = spliceMathBackspace(text, { start: caret, end: caret });
    expect(result.text).toBe("$\\frac{8}{8}$");
  });

  it("deletes the first numerator digit when the caret is at the front", () => {
    const text = "$\\frac{8}{8}$";
    const result = spliceMathBackspace(text, { start: 1, end: 1 });
    expect(result.text).toBe("$\\frac{}{8}$");
  });

  it("deletes a finished fraction from the trailing dollar without leaking latex", () => {
    const text = "$\\frac{8}{8}$";
    const result = spliceMathBackspace(text, { start: text.length - 1, end: text.length - 1 });
    expect(result.text).toBe("$\\frac{8}{}$");
  });
});
