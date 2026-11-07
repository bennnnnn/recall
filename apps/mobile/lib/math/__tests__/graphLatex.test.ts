import { graphRelationLatex } from "@/lib/math/graphLatex";
import { parseSimpleLatex, readableLatexFallback } from "@/lib/math/text";

describe("a graph legend in the maths face", () => {
  it.each([
    ["y = x^2 - 4x + 3", "y = x^{2} - 4x + 3"],
    ["x^2 - 4*x + 3", "y = x^{2} - 4x + 3"],
    ["y = 2*sin(x)", "y = 2\\sin(x)"],
    ["y = -x^2 + 6", "y = -x^{2} + 6"],
    ["y = (x - 8)^2", "y = (x - 8)^{2}"],
    ["y = 1/(x - 2) + 3", "y = \\frac{1}{x - 2} + 3"],
    ["y = sqrt(x) - abs(x)", "y = \\sqrt{x} - |x|"],
    ["y = e^x", "y = e^{x}"],
    ["y = 2*pi*x", "y = 2πx"],
    ["y = x*2", "y = x \\cdot 2"],
    ["y = x - (x + 1)", "y = x - (x + 1)"],
    ["y <= 2x + 1", "y \\le 2x + 1"],
    ["y = log(x) + ln(x)", "y = \\log(x) + \\ln(x)"],
  ])("draws %s as %s", (expr, latex) => {
    expect(graphRelationLatex(expr)).toBe(latex);
  });

  it("reads back as the expression it came from", () => {
    expect(readableLatexFallback(graphRelationLatex("y = x^2 - 4x + 3")!)).toBe("y = x^2 - 4x + 3");
    expect(parseSimpleLatex(graphRelationLatex("y = x^2 - 4x + 3")!).some((seg) => seg.type === "sup")).toBe(true);
  });

  it.each(["x^2 + y^2 = 25", "(8, 3)", "banana", ""])("leaves %p, which the plot grammar cannot read, as text", (expr) => {
    expect(graphRelationLatex(expr)).toBeNull();
  });
});
