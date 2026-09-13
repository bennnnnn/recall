import katex from "katex";
import { preprocessMarkdown } from "@/lib/markdown/markdownPreprocess";
import { prepareStreamingMathText } from "@/lib/math/streamingMath";
import { splitInlineMath } from "@/lib/markdown/inlineMath";
import { markdownItInstance } from "@/lib/markdownIt";
import { parseSimpleLatex, readableLatexFallback, restoreMathEscapes, segmentsToPlain } from "@/lib/mathText";
import { renderKatexHtml } from "@/lib/katexRender";

function formulae(text: string): string[] {
  return markdownItInstance.parse(text, {}).flatMap((token) => token.type === "inline"
    ? (token.children ?? []).flatMap((child) => child.type === "text"
      ? splitInlineMath(child.content).filter((part) => part.type === "math").map((part) => part.value) : []) : []);
}
const plain = (source: string) => segmentsToPlain(parseSimpleLatex(source));

describe("derivative primes survive Markdown typography", () => {
  it.each([
    ["$f'(x)=e^x$", "f'(x)=e^x", "f′(x)"],
    ["$f''(x)=e^x$", "f''(x)=e^x", "f″(x)"],
    [String.raw`\( f''(x) = e^x \)`, "f''(x) = e^x", "f″(x)"],
  ])("preserves original LaTeX through real Markdown tokenization: %s", (source, original, derivative) => {
    for (const prepared of [preprocessMarkdown(source), prepareStreamingMathText(source).text]) {
      const math = formulae(prepared);
      expect(math).toHaveLength(1);
      expect(restoreMathEscapes(math[0])).toBe(original);
      expect(plain(math[0])).toContain(derivative);
      expect(plain(math[0])).not.toMatch(/[‘’\uE000-\uE005]/);
    }
  });

  it("keeps C14's first and second derivatives distinct inside the actual list form", () => {
    const source = [
      String.raw`**Terms calculated:**`,
      String.raw`1. \( f(1) = e^1 = e \)`,
      String.raw`2. \( f'(x) = e^x \) → \( f'(1) = e \)`,
      String.raw`3. \( f''(x) = e^x \) → \( f''(1) = e \)`,
    ].join("\x20\x20\n");
    const values = formulae(preprocessMarkdown(source)).map(plain);
    expect(values).toEqual(["f(1) = e^1 = e", "f′(x) = e^x", "f′(1) = e", "f″(x) = e^x", "f″(1) = e"]);
  });

  it("keeps every partial derivative span pending until its closing delimiter", () => {
    for (const source of ["$f''(x)=e^x$", String.raw`\(f''(x)=e^x\)`]) {
      const opener = source[0] === "$" ? 1 : 2;
      for (let end = opener + 1; end < source.length; end += 1) {
        const result = prepareStreamingMathText(source.slice(0, end));
        expect(result.pending).toBe(true);
        expect(formulae(result.text)).toEqual([]);
        expect(result.text).not.toContain("'");
      }
      expect(formulae(prepareStreamingMathText(source).text).map(plain)).toEqual(["f″(x)=e^x"]);
    }
  });

  it("passes the original apostrophes to KaTeX rather than native prime substitutions", () => {
    const math = formulae(preprocessMarkdown("$f''(x)=e^x$"))[0];
    const render = jest.spyOn(katex, "renderToString");
    try {
      renderKatexHtml(math);
      expect(render).toHaveBeenCalledWith("f''(x)=e^x", expect.any(Object));
    } finally { render.mockRestore(); }
  });

  it("keeps ordinary prose smartquotes and explicit escaped quotes", () => {
    const source = String.raw`It's "clear"; don\'t change prose. Use $f'(x)$ instead.`;
    const parsed = markdownItInstance.render(preprocessMarkdown(source));
    expect(parsed).toContain("It’s “clear”");
    expect(parsed).toContain("don't change prose");
    expect(formulae(preprocessMarkdown(source)).map(plain)).toEqual(["f′(x)"]);
  });

  it("preserves code fences and literal inline code", () => {
    const code = "```python\nvalue = \"f''(x)\"\n```\n\n`console.log(\"f'(x)\")`.";
    const tokens = markdownItInstance.parse(preprocessMarkdown(code), {});
    expect(tokens.find((token) => token.type === "fence")?.content).toBe("value = \"f''(x)\"\n");
    expect(tokens.flatMap((token) => token.children ?? []).find((token) => token.type === "code_inline")?.content).toBe("console.log(\"f'(x)\")");
  });

  it.each([
    ["f'''(x)", "f‴(x)"],
    ["y' = x", "y′ = x"],
    [String.raw`\theta'(x)`, "θ′(x)"],
    [String.raw`f^{\prime}(x)`, "f^′(x)"],
    [String.raw`f\'(x)`, "f'(x)"],
    [String.raw`\text{don't change f'(x)}`, "don't change f'(x)"],
    [String.raw`\frac{\text{f'(x)}}{2}`, "f'(x)/2"],
    [String.raw`\frac{f\'(x)}{2}`, "f'(x)/2"],
    ["James' theorem", "James' theorem"],
  ])("keeps prime versus literal apostrophe semantics: %s", (source, expected) => {
    expect(plain(source)).toBe(expected);
  });
});

describe("SymPy function argument grouping", () => {
  it("renders exact C18 without invisible grouping braces", () => {
    const source = String.raw`y{\left(x \right)} = C_{1} + x^{2}`;
    expect(plain(source)).toBe("y(x) = C_1 + x^2");
    expect(readableLatexFallback(source)).toBe("y(x) = C_1 + x^2");
  });
  it.each([
    [String.raw`y\{(x)\}`, "y{(x)}"],
    [String.raw`\{1,2\}`, "{1,2}"],
    [String.raw`\frac{y{\left(x\right)}}{\sqrt{x^{2}}}`, "y(x)/√x̅^̅2̅"],
    [String.raw`y{(x)+(z)}`, "y{(x)+(z)}"],
    [String.raw`y{(x}`, "y{(x}"],
  ])("preserves sets and non-function groups: %s", (source, expected) => {
    expect(plain(source)).toBe(expected);
  });
});
