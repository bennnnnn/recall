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

  it("does not unwrap a math fence just because its content has bold text", () => {
    const input = "```math\n**x** = 5\n```";
    const out = preprocessMarkdown(input);
    expect(out).toContain("```math");
    expect(out).toContain("**x** = 5");
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
