import { normalizeBoldInlineMath, normalizeMarkdownTables, isPipeTable, preprocessMarkdown, splitInlineMath } from "@/lib/markdownPreprocess";
import { repairBrokenMarkdownLinks } from "@/lib/placesList";

const RESTAURANT_LIST = `Here are some top-rated restaurants in San Francisco that might tickle your taste buds 🍽️:

### **Fine Dining**
1. **Benu** – 3-Michelin stars, modern Asian fusion ($$$)
2. **Atelier Crenn** – Poetic, French-inspired ($$$)

### **Casual & Trendy**
3. **State Bird Provisions** – Creative dim-sum ($$)
4. **Tartine Manufactory** – Bakery meets Californian fare ($$)`;

describe("preprocessMarkdown", () => {
  it("does not split restaurant price tiers ($$$) into math fences", () => {
    const out = preprocessMarkdown(RESTAURANT_LIST);

    expect(out).not.toContain("```math");
    expect(out).not.toContain("```\n$$");
    expect(out).toContain("**Benu**");
    expect(out).toContain("($$$)");
    expect(out).toContain("**Atelier Crenn**");
    expect(out).toContain("### **Casual & Trendy**");
  });

  it("does not split ($$) price tiers across list items", () => {
    const input = `1. **Benu** – fusion ($$)
2. **Atelier Crenn** – Poetic ($$)`;

    const out = preprocessMarkdown(input);

    expect(out).not.toContain("```math");
    expect(out).toContain("($$)");
    expect(out).toContain("**Atelier Crenn**");
  });

  it("still converts real display math delimiters", () => {
    const input = "The area is $$\\pi r^2$$ for a circle.";
    const out = preprocessMarkdown(input);
    expect(out).toContain("```math");
    expect(out).toContain("\\pi r^2");
  });

  it("repairs already-corrupted restaurant markdown from bad ($$) splits", () => {
    const corrupted = `Here are restaurants:

### **Fine Dining**
1. **Benu** – 3-Michelin stars, modern Asian fusion (
\`\`\`math
$)
2. **Atelier Crenn** – Poetic, French-inspired ($$$
\`\`\`
3. **State Bird Provisions** – Creative dim-sum ($$)`;

    const out = preprocessMarkdown(corrupted);

    expect(out).not.toContain("```math");
    expect(out).not.toContain("```\n$$");
    expect(out).toContain("**Benu**");
    expect(out).toContain("**Atelier Crenn**");
    expect(out).toContain("**State Bird Provisions**");
  });

  it("repairs broken salon markdown links with dollar delimiters", () => {
    const broken = `1. [CODE Salon]$https://www.yelp.com/biz/code$ — 4.7 stars
2. [Nepenji]$https://maps.google.com/?q=nepenji$ — Japanese care`;

    const out = preprocessMarkdown(broken);

    expect(out).toContain("[CODE Salon](https://www.yelp.com/biz/code)");
    expect(out).not.toContain("]$https://");
  });

  it("repairBrokenMarkdownLinks helper", () => {
    expect(
      repairBrokenMarkdownLinks("[A]$https://x.com$"),
    ).toBe("[A](https://x.com)");
  });

  it("unwraps inline math from inside bold markers", () => {
    expect(normalizeBoldInlineMath("**Answer: $x = 2$**")).toBe("**Answer:** $x = 2$");
    expect(normalizeBoldInlineMath("**$x^2$**")).toBe("$x^2$");
    expect(normalizeBoldInlineMath("**Final Answer:** $x = 2 or x = -2$")).toBe(
      "**Final Answer:** $x = 2 or x = -2$",
    );
  });

  it("splitInlineMath handles final answer line", () => {
    const parts = splitInlineMath("Final Answer: $x = 2 or x = -2$");
    expect(parts).toEqual([
      { type: "text", value: "Final Answer: " },
      { type: "math", value: "x = 2 or x = -2" },
    ]);
  });

  it("preprocess keeps math adjacent to bold labels", () => {
    const out = preprocessMarkdown("**Final Answer:** $x = 2 or x = -2$");
    expect(out).toContain("**Final Answer:**");
    expect(out).toContain("$x = 2 or x = -2$");
  });

  it("keeps a short ```math fence inside a numbered solution step intact", () => {
    const input = `1. Start with the equation:
1 + 4 = 5 + x

2. Simplify the left side:
\`\`\`math
5 = 5 + x
\`\`\`

3. Subtract 5 from both sides to isolate x:
5 - 5 = 5 + x - 5

4. Final result:
\`\`\`math
x = 0
\`\`\``;

    const out = preprocessMarkdown(input);

    // Both math fences must survive as ```math fences, not be dropped/unwrapped.
    expect(out).toContain("```math\n5 = 5 + x\n```");
    expect(out).toContain("```math\nx = 0\n```");
    // The ordered list numbering must stay intact — no renumbering/splitting.
    expect(out).toContain("2. Simplify the left side:");
    expect(out).toContain("3. Subtract 5 from both sides to isolate x:");
    expect(out).toContain("4. Final result:");
  });

  it("BUG FIX regression: does not unwrap a math fence just because its content starts with a dollar sign", () => {
    // The price-tier-corruption check matched any body starting with "$",
    // not just the specific "$)" artifact left on its own line by a botched
    // ($$) price-tier split. A legitimate ```math fence whose body happens
    // to start with "$" — e.g. one normalizeImplicitMath had already
    // dollar-wrapped as a bare-equation line before BLOCK_MATH_BRACKET_RE
    // promoted it into a fence — used to get incorrectly unwrapped back to
    // plain inline text.
    const input = "```math\n$x^2 = 4$\n```";
    const out = preprocessMarkdown(input);
    expect(out).toContain("```math");
    expect(out).toContain("$x^2 = 4$");
  });

  it("still repairs a genuine bare-$ (no closing paren) price-tier artifact, stripping the leading $", () => {
    const input = "```math\n$\n1. **Benu** – fusion ($$$)\n```";
    const out = preprocessMarkdown(input);
    expect(out).not.toContain("```math");
    expect(out.trim()).toBe("1. **Benu** – fusion ($$$)");
  });

  it("does not unwrap a math fence just because its content has bold text", () => {
    const input = "```math\n**x** = 5\n```";
    const out = preprocessMarkdown(input);
    expect(out).toContain("```math");
    expect(out).toContain("**x** = 5");
  });

  it("BUG FIX regression: keeps a mis-tagged ```copy fence with a bare math-answer body as a real fence, not unwrapped prose", () => {
    // Reported live: "2c^2" (a simplified final result) sent as ```copy\n2c^2\n```
    // used to get unwrapped into plain prose text by unwrapNonCodeFences
    // (which has no concept of "this looks like a math answer") before it
    // ever reached renderFence's AnswerBlock dispatch — losing the fence
    // entirely and rendering as a bare paragraph instead of a boxed answer.
    const input = "```copy\n2c^2\n```";
    const out = preprocessMarkdown(input);
    expect(out).toContain("```");
    expect(out).toContain("2c^2");
  });

  it("BUG FIX regression: converts \\[...\\] display math with multiple commands to a clean fence, not a $-corrupted one", () => {
    // Reported live (screenshots): "x = $\\pm$ $\\sqrt{4}$" rendered in red
    // inside a ```math fence. normalizeImplicitMath's wrapInlineLatexCommands
    // used to wrap each bare command inside a \\[...\\] span in $...$ before
    // this function's own BLOCK_MATH_BRACKET_RE converted the span into a
    // ```math fence, leaving the fence body with embedded $ characters KaTeX
    // can't parse as bare LaTeX (rendered in errorColor red instead).
    const input = "Solve:\n\n\\[ x = \\pm \\sqrt{4} \\]\n\nSo x = 2 or x = -2";
    const out = preprocessMarkdown(input);
    expect(out).toContain("```math\nx = \\pm \\sqrt{4}\n```");
    expect(out).not.toContain("$\\pm$");
    expect(out).not.toContain("$\\sqrt{4}$");
  });

  it("BUG FIX regression: prose parentheticals with nested $math$ do not steal the next $$ display block", () => {
    const input = [
      "like a hidden quadratic (e.g., in disguise like $x^4$)",
      "",
      "### Title",
      "",
      "$$",
      String.raw`\frac{2x - 1}{x + 3} = \frac{x + 4}{x - 2}`,
      "$$",
      "",
      "⚠️ **Wait — this isn’t *technically* quadratic yet**",
      "- Domain restrictions (excluded values: $x \\neq -3, 2$)",
    ].join("\n");
    const out = preprocessMarkdown(input);
    expect(out).toContain("```math\n\\frac{2x - 1}{x + 3} = \\frac{x + 4}{x - 2}\n```");
    expect(out).toContain("⚠️ **Wait — this isn’t *technically* quadratic yet**");
    expect(out).toContain("excluded values: $x \\neq -3, 2$");
    // Prose must not land inside a math fence
    expect(out).not.toMatch(/```math\n⚠️/);
  });
});

describe("normalizeMarkdownTables", () => {
  it("adds separator row for loose pipe tables", () => {
    const input = `Name | Score
Alice | 95
Bob | 88`;
    const out = normalizeMarkdownTables(input);
    expect(out).toContain("| Name | Score |");
    expect(out).toMatch(/\|\s*---\s*\|/);
  });

  it("unwraps fenced markdown tables", () => {
    const input = "```markdown\nA | B\n1 | 2\n```";
    const out = normalizeMarkdownTables(input);
    expect(out).not.toContain("```");
    expect(out).toContain("| A | B |");
  });

  it("strips divider-only lines between table rows", () => {
    const input = `| Col A | Col B |
---
| one | two |`;
    const out = normalizeMarkdownTables(input);
    expect(out).not.toMatch(/^---$/m);
    expect(out).toContain("| one | two |");
  });
});

describe("isPipeTable", () => {
  it("returns true for valid pipe tables", () => {
    expect(
      isPipeTable(`| Name | Value |
| --- | --- |
| foo | 1 |`),
    ).toBe(true);
  });

  it("returns false for plain prose", () => {
    expect(isPipeTable("Just a paragraph with | pipes | inline.")).toBe(false);
  });
});
