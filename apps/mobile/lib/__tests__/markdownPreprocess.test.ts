import { normalizeBoldInlineMath, normalizeMarkdownTables, isPipeTable, preprocessMarkdown, splitInlineMath, layoutCheckVerificationLines, breakAttachedMathFences, unwrapProseMathBackticks } from "@/lib/markdownPreprocess";
import { repairBrokenMarkdownLinks } from "@/lib/placesList";
import { markdownItInstance } from "@/lib/markdownIt";
import {
  PROTECTED_ESCAPE_MARKER,
  PROTECTED_MATH_STAR_MARKER,
  PROTECTED_MATH_UNDERSCORE_MARKER,
  parseSimpleLatex,
  segmentsToPlain,
} from "@/lib/mathText";

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

  it("BUG FIX regression: check lines keep a space after 'x = 2:' so 2:2² does not glue", () => {
    // Live: "For $x = 2$: $2^2 + 2 = 6$" (or one $x = 2: 2^2$ span) rendered
    // as 2:2². Split the label from the formula and force a space after `:`.
    expect(layoutCheckVerificationLines("For $x = 2$:$2^2 + 2 = 6$")).toBe(
      "For $x = 2$: $2^2 + 2 = 6$",
    );
    expect(layoutCheckVerificationLines("For $x = 2: 2^2 + 2 = 6$")).toBe(
      "For $x = 2$: $2^2 + 2 = 6$",
    );
    expect(layoutCheckVerificationLines("- [x] For $x = -2$:$(-2)^2 + 2 = 6$")).toBe(
      "- [x] For $x = -2$: $(-2)^2 + 2 = 6$",
    );
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

  it("lifts an indented evaluation-bar ```math fence out of a numbered step", () => {
    const input = `2. Apply the limits 2 and 8:
   \`\`\`math
   \\left.\\frac{x^{3}}{3}\\right|_{2}^{8}
   = \\frac{8^{3}}{3}-\\frac{2^{3}}{3}
   = \\frac{512}{3}-\\frac{8}{3}
   = \\frac{504}{3}
   \`\`\`

3. Simplify:
   \`\`\`math
   \\frac{504}{3} = 168
   \`\`\``;
    const out = preprocessMarkdown(input);
    expect(out).toContain("```math\n");
    expect(out).not.toMatch(/^[ \t]+```math/m);
    const tokens = markdownItInstance.parse(out, {});
    const fenceBodies = tokens
      .filter((t) => t.type === "fence")
      .map((t) => t.content);
    expect(fenceBodies.some((b) => b.includes("\\left."))).toBe(true);
    expect(fenceBodies.some((b) => b.includes("504"))).toBe(true);
    const asText = tokens
      .filter((t) => t.type === "inline" || t.type === "paragraph_open")
      .map((t) => t.content)
      .join("\n");
    expect(asText).not.toContain("```math");
  });

  it("BUG FIX regression: ```math glued to a sentence is a real fence, not raw LaTeX", () => {
    // Live: "Multiply both sides by r: ```math" then the equation — CommonMark
    // ignored the mid-line opener and painted ```math, \frac, \quad, \Rightarrow.
    const input =
      "Multiply both sides by r: ```math\n" +
      "r^2 + 1 = \\frac{17}{4}r \\quad \\Rightarrow \\quad 4r^2 - 17r + 4 = 0\n" +
      "```\n\n*Solve:*\n```math\n(4r-1)(r-4)=0\n```";
    const out = preprocessMarkdown(input);
    expect(out).not.toMatch(/r: ```math/);
    expect(breakAttachedMathFences("Multiply both sides by r: ```math")).toContain(
      "```math",
    );
    expect(out).toContain("Multiply both sides by r:");
    const tokens = markdownItInstance.parse(out, {});
    const fences = tokens.filter((t) => t.type === "fence");
    expect(fences.length).toBeGreaterThanOrEqual(2);
    expect(fences.some((t) => t.content.includes("\\frac{17}{4}"))).toBe(true);
    const asText = tokens
      .filter((t) => t.type === "inline")
      .map((t) => t.content)
      .join("\n");
    expect(asText).not.toContain("```math");
    expect(asText).not.toContain("\\frac");
  });

  it("BUG FIX regression: does not leave a stray backtick on a check-sum line", () => {
    // Live: "✅ Check sum: 2 + 8 + 32 = 42`" — leftover markdown tick.
    const input = "✅ Check sum: `2 + 8 + 32 = 42`\n✅ Check sum: 2 + 8 + 32 = 42`";
    const out = preprocessMarkdown(input);
    expect(out).not.toMatch(/42`/);
    expect(unwrapProseMathBackticks("✅ Check sum: 2 + 8 + 32 = 42`")).toBe(
      "✅ Check sum: 2 + 8 + 32 = 42",
    );
    expect(out).toContain("2 + 8 + 32 = 42");
  });

  it("does not unwrap non-math inline code", () => {
    const input = "Install with `npm install` then run.";
    expect(preprocessMarkdown(input)).toContain("`npm install`");
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

  it("BUG FIX regression: protects punctuation-led LaTeX commands (\\, \\; \\!) inside inline math from markdown-it's own CommonMark backslash-escape, which otherwise silently drops the backslash and leaves a stray comma/semicolon/exclamation mark mid-formula", () => {
    // Reported live: markdown-it's built-in escape rule treats "\" + any
    // ASCII punctuation char as an escape and drops the backslash *before*
    // splitInlineMath/MathText ever see the text — confirmed by parsing the
    // real markdownItInstance directly. "\," (an invisible thin space) used
    // to render as a bare, visible "," sitting where the space belongs.
    const input = "Body: $\\int x^2\\,dx = C$ end.";
    const prepared = preprocessMarkdown(input);

    // The backslash before the comma must survive as the protected marker,
    // not vanish, and no bare "x^2,dx" (the corrupted shape) should appear.
    expect(prepared).toContain(PROTECTED_ESCAPE_MARKER);
    expect(prepared).not.toContain("x^2,dx");

    // Round-trip through the app's real markdown-it instance, exactly as
    // the render path does, then decode via mathText.ts (as MathText does)
    // and confirm the final rendered text has a real space, not a comma.
    const tokens = markdownItInstance.parse(prepared, {});
    const inline = tokens.find((t) => t.type === "inline");
    const textToken = inline?.children?.find((c) => c.type === "text");
    expect(textToken?.content).toContain(PROTECTED_ESCAPE_MARKER);
    const mathSpan = textToken!.content.match(/\$([^$]+)\$/)![1];
    const finalText = segmentsToPlain(parseSimpleLatex(mathSpan));
    expect(finalText).toBe("∫ x^2 dx = C");
  });

  it("does not protect letter-led LaTeX commands (\\int, \\frac, \\sqrt) — unaffected by CommonMark's escape rule, which only fires on punctuation", () => {
    const input = "Body: $\\int \\frac{1}{2}\\,dx$ end.";
    const prepared = preprocessMarkdown(input);
    expect(prepared).toContain("\\int");
    expect(prepared).toContain("\\frac");
  });

  it("does not touch backslash-punctuation outside a math span", () => {
    const input = "Note: a\\, b (not math) and $x\\,y$ (math)";
    const prepared = preprocessMarkdown(input);
    expect(prepared).toContain("a\\, b");
  });

  it("BUG FIX regression: converts \\(...\\) inline math to $...$ so markdown-it cannot strip the delimiters into raw (\\frac{...})", () => {
    // Reported live: model emits `\(\frac{m}{m}\)`; CommonMark escapes `\(` / `\)`
    // to bare parentheses during inline tokenization, so splitInlineMath never
    // sees a math span and the UI shows literal `(\frac{m}{m})`.
    const input =
      "1. Divide both sides by \\(\\frac{m}{m}\\):\n" +
      "Cancel \\(\\frac{m}{m}\\) (since \\(m \\neq 0\\)) to get \\(1 = 2m\\).\n" +
      "\\(m = \\frac{1}{2}\\)";
    const prepared = preprocessMarkdown(input);
    expect(prepared).toContain("$\\frac{m}{m}$");
    expect(prepared).toContain("$m \\neq 0$");
    expect(prepared).toContain("$m = \\frac{1}{2}$");
    expect(prepared).not.toContain("\\(");
    expect(prepared).not.toContain("\\)");

    const tokens = markdownItInstance.parse(prepared, {});
    const textContents: string[] = [];
    type WalkToken = { type: string; content?: string; children?: WalkToken[] | null };
    const walk = (ts: WalkToken[]) => {
      for (const t of ts) {
        if (t.type === "text" && t.content) textContents.push(t.content);
        if (t.children) walk(t.children);
      }
    };
    walk(tokens as unknown as WalkToken[]);

    const allText = textContents.join("\n");
    const mathParts = textContents.flatMap((c) =>
      splitInlineMath(c).filter((p) => p.type === "math"),
    );
    expect(mathParts.length).toBeGreaterThanOrEqual(3);
    expect(mathParts.some((p) => p.value.includes("\\frac{m}{m}"))).toBe(true);
    // Must not surface the post-escape raw shape with bare parens + \frac.
    expect(allText).not.toMatch(/\(\\frac\{m\}\{m\}\)/);
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

  it("treats spaced divider chars as divider lines (linear check)", () => {
    const input = `| Col A | Col B |
- - - - -
| one | two |`;
    const out = normalizeMarkdownTables(input);
    expect(out).not.toMatch(/^- - - - -$/m);
    expect(out).toContain("| one | two |");
  });

  it("keeps YAML document separators inside a fence", () => {
    const input = "```yaml\n---\nname: deploy\non: push\n---\n```";
    const out = normalizeMarkdownTables(input);
    expect(out).toBe(input);
  });

  it("keeps a bare tilde fence closer", () => {
    const input = "~~~python\nprint('hi')\n~~~";
    const out = normalizeMarkdownTables(input);
    expect(out).toBe(input);
  });

  it("keeps a thematic break surrounded by blank lines", () => {
    const input = "Intro.\n\n---\n\nAfter.";
    const out = normalizeMarkdownTables(input);
    expect(out).toBe(input);
  });

  it("keeps a setext heading underline", () => {
    const input = "My Heading\n===\n\nBody.";
    const out = normalizeMarkdownTables(input);
    expect(out).toBe(input);
  });

  it("preprocessMarkdown does not strip YAML front matter from a fence", () => {
    const input = "```yaml\n---\nname: deploy\non: push\n---\n```";
    const out = preprocessMarkdown(input);
    expect(out).toContain("---");
    expect(out).toContain("name: deploy");
  });

  it("does not turn composer abs-bars $|5|3$ into a GFM table", () => {
    const input = "$|5|3$";
    expect(normalizeMarkdownTables(input)).toBe(input);
    expect(preprocessMarkdown(input)).not.toMatch(/---/);
  });
});

describe("vega retag (linear)", () => {
  it("retags json fences that contain a Vega schema", () => {
    const body = `{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": { "values": [{"a": 1}] },
  "mark": "bar"
}`;
    const out = preprocessMarkdown("```json\n" + body + "\n```");
    expect(out).toContain("```vega-lite");
    expect(out).toContain("vega.github.io/schema");
  });

  it("wraps bare Vega JSON blocks", () => {
    const body = `{
"$schema": "https://vega.github.io/schema/vega-lite/v5.json",
"mark": "point"
}`;
    const out = preprocessMarkdown("Chart:\n\n" + body + "\n\nDone.");
    expect(out).toContain("```vega-lite");
  });

  it("protects bare _ and * inside $...$ so markdown-it cannot emphasize them", () => {
    const prepared = preprocessMarkdown("See $x_1 * y_2$ and $a_i^2$.");
    expect(prepared).toContain(PROTECTED_MATH_UNDERSCORE_MARKER);
    expect(prepared).toContain(PROTECTED_MATH_STAR_MARKER);
    expect(prepared).not.toMatch(/\$x_1 \* y_2\$/);

    const tokens = markdownItInstance.parse(prepared, {});
    const inline = tokens.find((t) => t.type === "inline");
    const types = (inline?.children ?? []).map((c) => c.type);
    expect(types).not.toContain("em_open");
    expect(types).not.toContain("strong_open");

    const textToken = inline?.children?.find((c) => c.type === "text" && c.content.includes("$"));
    expect(textToken?.content).toContain(PROTECTED_MATH_UNDERSCORE_MARKER);
    const spans = [...(textToken?.content.matchAll(/\$([^$]+)\$/g) ?? [])].map((m) => m[1]);
    expect(segmentsToPlain(parseSimpleLatex(spans[0]!))).toBe("x_1 * y_2");
    expect(segmentsToPlain(parseSimpleLatex(spans[1]!))).toBe("a_i^2");
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
