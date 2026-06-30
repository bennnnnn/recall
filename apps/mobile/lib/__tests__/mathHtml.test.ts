import { isHeavyMath, pickMathEngine } from "@/lib/mathHtml";
import { splitInlineMath } from "@/lib/markdownPreprocess";

describe("mathHtml", () => {
  it("routes matrices and integrals to MathJax", () => {
    expect(pickMathEngine(String.raw`\begin{pmatrix} a & b \\ c & d \end{pmatrix}`)).toBe(
      "mathjax",
    );
    expect(pickMathEngine(String.raw`\int_0^1 x^2 dx`)).toBe("mathjax");
  });

  it("keeps short inline expressions on KaTeX", () => {
    expect(pickMathEngine("x^2 + y^2 = r^2")).toBe("katex");
    expect(isHeavyMath("E = mc^2")).toBe(false);
  });
});

describe("splitInlineMath", () => {
  it("parses dollar and parenthesis delimiters", () => {
    const parts = splitInlineMath("Let \\(a^2\\) and $b^2$ be sides.");
    expect(parts).toEqual([
      { type: "text", value: "Let " },
      { type: "math", value: "a^2" },
      { type: "text", value: " and " },
      { type: "math", value: "b^2" },
      { type: "text", value: " be sides." },
    ]);
  });
});
