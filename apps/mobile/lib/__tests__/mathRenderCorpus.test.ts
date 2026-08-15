/**
 * Reproduction corpus: assistant-shaped strings through preprocess → inline
 * split → native parse. A leftover `\\command` after this pipeline is what
 * painted as raw LaTeX in chat.
 */
import { markdownItInstance } from "@/lib/markdownIt";
import { preprocessMarkdown, splitInlineMath } from "@/lib/markdownPreprocess";
import { readableLatexFallback, segmentsToPlain, parseSimpleLatex } from "@/lib/mathText";
import { findStableMarkdownPrefixLen, preprocessMarkdownForStream } from "@/lib/markdownPreprocessStream";

const BACKSLASH_CMD = /\\[a-zA-Z]+/;

function mathSpansAfterPreprocess(raw: string): string[] {
  const prepared = preprocessMarkdown(raw);
  const tokens = markdownItInstance.parse(prepared, {});
  const texts: string[] = [];
  const walk = (ts: Array<{ type: string; content?: string; children?: unknown[] | null }>) => {
    for (const t of ts) {
      if (t.type === "text" && t.content) texts.push(t.content);
      if (t.children) walk(t.children as typeof ts);
    }
  };
  walk(tokens);
  return texts.flatMap((c) => splitInlineMath(c).filter((p) => p.type === "math").map((p) => p.value));
}

describe("math render corpus (preprocess → typeset, never raw \\cmd)", () => {
  it("inline $x^2$", () => {
    const spans = mathSpansAfterPreprocess("Let $x^2$ be the square.");
    expect(spans).toEqual(["x^2"]);
    expect(readableLatexFallback(spans[0])).toBe("x^2");
    expect(readableLatexFallback(spans[0])).not.toMatch(BACKSLASH_CMD);
  });

  it("converts $$ display math into a ```math fence", () => {
    const out = preprocessMarkdown("The area is $$\\pi r^2$$ for a circle.");
    expect(out).toContain("```math");
    expect(out).toContain("\\pi r^2");
    expect(out).not.toContain("$$");
  });

  it("converts \\(...\\) to $...$ so markdown-it cannot strip delimiters", () => {
    const out = preprocessMarkdown("Cancel \\(\\frac{m}{m}\\) since \\(m \\neq 0\\).");
    expect(out).toContain("$\\frac{m}{m}$");
    expect(out).not.toContain("\\(");
    const spans = mathSpansAfterPreprocess("Cancel \\(\\frac{m}{m}\\) since \\(m \\neq 0\\).");
    expect(spans.some((s) => s.includes("\\frac{m}{m}"))).toBe(true);
    expect(readableLatexFallback("\\frac{m}{m}")).toBe("m/m");
  });

  it("converts \\[...\\] display math into a ```math fence", () => {
    const out = preprocessMarkdown("Solve:\n\n\\[ x = \\pm \\sqrt{4} \\]\n");
    expect(out).toContain("```math");
    expect(out).toContain("x = \\pm \\sqrt{4}");
    expect(out).not.toContain("\\[");
  });

  it("keeps a ```math fence as a fence (not inline $)", () => {
    const out = preprocessMarkdown("```math\n\\frac{1}{2}\n```");
    expect(out).toContain("```math");
    expect(readableLatexFallback("\\frac{1}{2}")).toBe("1/2");
  });

  it("numbered steps with inline math still produce math spans", () => {
    const input = "1. Divide by $m$: $1 = 2m$.\n2. So $m = \\frac{1}{2}$.";
    const spans = mathSpansAfterPreprocess(input);
    expect(spans.length).toBeGreaterThanOrEqual(3);
    expect(spans).toContain("m = \\frac{1}{2}");
  });

  it("list items with inline math still produce math spans", () => {
    const spans = mathSpansAfterPreprocess("- Let $x^2 + 1$ be positive.");
    expect(spans).toContain("x^2 + 1");
  });

  it("table cells with inline math still produce math spans", () => {
    const input = "| Qty | Formula |\n| --- | --- |\n| area | $\\pi r^2$ |";
    const spans = mathSpansAfterPreprocess(input);
    expect(spans.some((s) => s.includes("\\pi r^2") || s.includes("pi r^2"))).toBe(true);
  });

  it("aligned / matrix / cases degrade without leftover backslash commands", () => {
    const aligned = String.raw`\begin{aligned} a &= b \\ c &= d \end{aligned}`;
    const matrix = String.raw`\begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}`;
    const cases = String.raw`\begin{cases} x & x \ge 0 \\ -x & x < 0 \end{cases}`;
    for (const src of [aligned, matrix, cases]) {
      const plain = segmentsToPlain(parseSimpleLatex(src));
      expect(plain).not.toMatch(BACKSLASH_CMD);
      expect(plain).not.toContain("\\begin");
    }
  });

  it("mixed prose + math on one line", () => {
    const spans = mathSpansAfterPreprocess("If $a > 0$ then $b = a^2$ holds.");
    expect(spans).toEqual(["a > 0", "b = a^2"]);
  });

  it("math adjacent to a code fence is not swallowed by the fence", () => {
    const input = "See $x^2$ then\n```\ncode\n```\nand $y^2$.";
    const spans = mathSpansAfterPreprocess(input);
    expect(spans).toContain("x^2");
    expect(spans).toContain("y^2");
  });

  it("an unclosed $$ mid-stream stays out of the stable prefix", () => {
    const raw = "Before.\n\n$$\n\\frac{1}{2}\n";
    expect(findStableMarkdownPrefixLen(raw)).toBeLessThan(raw.length);
    const { prepared } = preprocessMarkdownForStream(raw, null);
    // Unstable tail is still raw; it must not be turned into a half fence.
    expect(prepared).toContain("$$");
  });
});
