import {
  normalizeBoldInlineMath,
  normalizeMarkdownTables,
  isPipeTable,
  preprocessMarkdown,
  splitInlineMath,
  layoutCheckVerificationLines,
  breakAttachedMathFences,
  unwrapProseMathBackticks,
  mergeStrandedColons,
  stripBoldListLabelContinuationColons,
  breakMidlineAtxHeadings,
} from "@/lib/markdown/markdownPreprocess";
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

  it("keeps mid-span math inside bold so list labels stay one line", () => {
    // Unwrapping produced **Slope (**$m$**):** which stacked as
    // "Slope (" / "m" / "): 3" in list items.
    expect(normalizeBoldInlineMath("**Slope ($m$):** 3")).toBe("**Slope ($m$):** 3");
    expect(normalizeBoldInlineMath("**Y-intercept ($b$):** 4")).toBe(
      "**Y-intercept ($b$):** 4",
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
      "For $x = 2$:\n  $2^2 + 2 = 6$",
    );
    expect(layoutCheckVerificationLines("For $x = 2: 2^2 + 2 = 6$")).toBe(
      "For $x = 2$:\n  $2^2 + 2 = 6$",
    );
    expect(layoutCheckVerificationLines("- [x] For $x = -2$:$(-2)^2 + 2 = 6$")).toBe(
      "- [x] For $x = -2$:\n  $(-2)^2 + 2 = 6$",
    );
  });

  it("puts the check substitution on the line under For n = …", () => {
    expect(layoutCheckVerificationLines("• For F = 0: 0 + 3 = 3 ✓")).toBe(
      "• For F = 0:\n  0 + 3 = 3 ✓",
    );
    expect(layoutCheckVerificationLines("- For F = 0: 0 + 3 = 3")).toBe(
      "- For F = 0:\n  0 + 3 = 3",
    );
    expect(layoutCheckVerificationLines("For example: try again")).toBe("For example: try again");
  });

  it("preprocess keeps math adjacent to bold labels", () => {
    const out = preprocessMarkdown("**Final Answer:** $x = 2 or x = -2$");
    expect(out).toContain("**Final Answer:**");
    expect(out).toContain("$x = 2 or x = -2$");
  });

  it("mergeStrandedColons: merges a lone colon line onto the previous line", () => {
    // The model puts ":" on its own line after a bold step header, which
    // renders as a stranded "two dots" between the header and the math.
    expect(
      mergeStrandedColons("2. **Multiply**\n:\n   $3 \\times 2 = 6$"),
    ).toBe("2. **Multiply**:\n   $3 \\times 2 = 6$");
  });

  it("mergeStrandedColons: ignores lines that are not just a colon", () => {
    expect(mergeStrandedColons("Hello\n: world")).toBe("Hello\n: world");
    expect(mergeStrandedColons("**Step**\nSome text\n:")).toBe(
      "**Step**\nSome text:",
    );
  });

  it("mergeStrandedColons: does not merge a colon as the first line", () => {
    expect(mergeStrandedColons(":\nHello")).toBe(":\nHello");
  });

  it("breakMidlineAtxHeadings: pulls ### off the previous sentence", () => {
    expect(breakMidlineAtxHeadings("Here's a breakdown: ### Explanation")).toBe(
      "Here's a breakdown:\n\n### Explanation",
    );
    expect(breakMidlineAtxHeadings("$y = 3x + 4$: ### Explanation")).toBe(
      "$y = 3x + 4$:\n\n### Explanation",
    );
    // Already a real heading — leave it.
    expect(breakMidlineAtxHeadings("### Explanation\n\nHello")).toBe(
      "### Explanation\n\nHello",
    );
  });

  it("BUG FIX regression: mergeStrandedColons also merges stranded semicolons", () => {
    expect(mergeStrandedColons("**Step**\n;\n   $x = 5$")).toBe(
      "**Step**;\n   $x = 5$",
    );
    expect(mergeStrandedColons("Label\n;")).toBe("Label;");
    // Semicolon as first line is not merged
    expect(mergeStrandedColons(";\nHello")).toBe(";\nHello");
  });

  it("BUG FIX regression: mergeStrandedColons does not glue colon onto fence closer or table row (PRE-009)", () => {
    // Fence closer — colon should stay on its own line.
    expect(mergeStrandedColons("```math\n1+1\n```\n:")).toBe("```math\n1+1\n```\n:");
    // Table row — colon should stay on its own line.
    expect(mergeStrandedColons("| a | b |\n:")).toBe("| a | b |\n:");
    // Heading — colon should stay on its own line.
    expect(mergeStrandedColons("# Heading\n:")).toBe("# Heading\n:");
  });

  it("preprocessMarkdown removes stranded colons after bold list labels", () => {
    const input = `1. **Substitute** $n = 3$: $3! = 3 \\times 2 \\times 1$
2. **Multiply**
:
   $3 \\times 2 = 6$
3. **Final step**
:
   $6 \\times 1 = 6$`;
    const out = preprocessMarkdown(input);
    expect(out).toContain("**Multiply**\n");
    expect(out).toContain("**Final step**\n");
    expect(out).not.toMatch(/(?:\n:|\*\*:|·)/);
  });

  it("removes decorative colons before values under bold list labels", () => {
    const input = `- **Chemical Formula**
  : O₂
- **Appearance**
  : Colorless gas
1. **Role**
   : Essential for respiration`;

    expect(stripBoldListLabelContinuationColons(input)).toBe(`- **Chemical Formula**
  O₂
- **Appearance**
  Colorless gas
1. **Role**
   Essential for respiration`);
    expect(preprocessMarkdown(input)).not.toMatch(/^\s*:|·/m);
  });

  it("keeps unrelated and fenced colon-prefixed lines intact", () => {
    const input = `Regular label
: keep this
\`\`\`text
- **Chemical Formula**
  : keep in code
\`\`\``;

    expect(stripBoldListLabelContinuationColons(input)).toBe(input);
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

    expect(out).toContain("```math\n5 = 5 + x\n```");
    expect(out).toContain("```math\nx = 0\n```");
    expect(out).toContain("2. Simplify the left side:");
    expect(out).toContain("3. Subtract 5 from both sides to isolate x:");
    expect(out).toContain("4. Final result:");
  });

  it("BUG FIX regression: inline math fence tail does not absorb list items or headings", () => {
    // After inlining a short ```math fence, the code merges a following
    // line starting with ?!,.;: — but must NOT absorb headings, list
    // items, images, table rows, or blockquotes.
    const input = `\`\`\`math
x = 5
\`\`\`

# Next Section`;
    const out = preprocessMarkdown(input);
    expect(out).toContain("# Next Section");

    const input2 = `\`\`\`math
x = 5
\`\`\`

- A list item`;
    const out2 = preprocessMarkdown(input2);
    expect(out2).toContain("- A list item");

    const input3 = `\`\`\`math
x = 5
\`\`\`

![image](url.png)`;
    const out3 = preprocessMarkdown(input3);
    expect(out3).toContain("![image](url.png)");
  });

  it("BUG FIX regression: liftMathFencesOutOfLists strips body indent to match column-0 opener", () => {
    // A math fence inside a numbered list has its opener lifted to column 0,
    // but body lines used to keep their list indent (4+ spaces), causing
    // CommonMark to treat them as indented code blocks with visible backticks.
    const input = `1. Step:

   \`\`\`math
   x = 5
   \`\`\`

2. Next`;
    const out = preprocessMarkdown(input);
    // The math fence should be at column 0 with body at column 0 too
    expect(out).toContain("```math\nx = 5\n```");
    expect(out).not.toMatch(/```math\n\s+x = 5/);
  });

  it("keeps 2 + Y / Y in the sentence instead of a math card", () => {
    const input = `**Solve an equation** involving
\`\`\`math
2 + Y
\`\`\`
? (e.g., 2 + Y = 7)

what
\`\`\`math
Y
\`\`\`
represents`;
    const out = preprocessMarkdown(input);
    expect(out).not.toMatch(/```math/);
    expect(out).toContain("$2 + Y$");
    expect(out).toContain("$Y$");
    expect(out).toMatch(/involving \$2 \+ Y\$ \?/);
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

  it("BUG FIX regression: lifts glued code fence openers for all langs, not just math", () => {
    // The model also glues code fence openers to prose
    // ("Here's the code: ```python print('hello')```"). The old
    // breakAttachedMathFences only handled math/latex/tex/answer/graph/
    // geometry langs; now it handles all recognized fence langs.
    const out = breakAttachedMathFences("Here's the code: ```python print('hello')```");
    expect(out).not.toMatch(/code: ```python/);
    expect(out).toContain("Here's the code:");
    expect(out).toContain("```python");
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

  it("BUG FIX regression: ```graph glued to a sentence is a real fence, not raw JSON", () => {
    // The model puts ```graph on the same line as the preceding text
    // ("Here's the graph of y = x + 2: ```graph") — CommonMark only
    // recognizes a fence at the start of a line, so without breaking
    // it onto its own line the JSON body renders as a code block instead
    // of routing to FunctionGraphBlock. LIFT_MATH_FENCE_LANG now includes
    // graph|geometry, not just math|latex|tex|answer.
    const input =
      "Here's the graph of y = x + 2: ```graph\n" +
      '{"type":"function","expr":"x + 2","variable":"x","x_min":-10.0,"x_max":10.0,"points":[[-10.0,-8.0],[10.0,12.0]]}\n' +
      "```";
    const out = preprocessMarkdown(input);
    expect(out).not.toMatch(/2: ```graph/);
    expect(out).toContain("Here's the graph of y = x + 2:");
    const tokens = markdownItInstance.parse(out, {});
    const fences = tokens.filter((t) => t.type === "fence");
    expect(fences.length).toBeGreaterThanOrEqual(1);
    expect(fences.some((t) => t.info?.trim() === "graph")).toBe(true);
  });

  it("BUG FIX regression: ```geometry glued to a sentence is a real fence", () => {
    const input =
      "Here's the diagram: ```geometry\n" +
      '{"type":"triangle","vertices":[[0,0],[4,0],[2,3]]}\n' +
      "```";
    const out = preprocessMarkdown(input);
    expect(out).not.toMatch(/diagram: ```geometry/);
    expect(out).toContain("Here's the diagram:");
    const tokens = markdownItInstance.parse(out, {});
    const fences = tokens.filter((t) => t.type === "fence");
    expect(fences.some((t) => t.info?.trim() === "geometry")).toBe(true);
  });

  it("BUG FIX regression: ```molecule3d glued to a sentence is a real fence (digits in lang)", () => {
    // takeLang only read [a-zA-Z-], so "molecule3d" was split into
    // "molecule" (unrecognized) + "3d" (body), and the glued opener
    // was never lifted — the fence rendered as prose with literal backticks.
    const input =
      "Here's the 3D structure: ```molecule3d\nO2\n\n     RDKit          3D\n\n  2  1  0  0  0  0  0  0  0  0999 V2000\nM  END\n```";
    const out = preprocessMarkdown(input);
    expect(out).not.toMatch(/structure: ```molecule3d/);
    expect(out).toContain("Here's the 3D structure:");
    const tokens = markdownItInstance.parse(out, {});
    const fences = tokens.filter((t) => t.type === "fence");
    expect(fences.some((t) => t.info?.trim() === "molecule3d")).toBe(true);
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

  it("BUG FIX regression: toStrictPipeRow respects math pipes inside cells", () => {
    const input = `Name | Value
$|x|$ | 5
$|a+b|$ | 10`;
    const out = normalizeMarkdownTables(input);
    expect(out).toContain("| $|x|$ | 5 |");
    expect(out).toContain("| $|a+b|$ | 10 |");
    expect(out).toMatch(/\|\s*---\s*\|/);
  });

  it("BUG FIX regression: separator row count matches columns with math pipes", () => {
    const input = `A | $|x|$ | C
1 | 2 | 3`;
    const out = normalizeMarkdownTables(input);
    const lines = out.split("\n");
    const sep = lines.find((l) => l.match(/^\|.*---.*\|$/));
    expect(sep).toBeTruthy();
    const sepCells = sep!.split("|").filter((c) => c.trim().length > 0);
    expect(sepCells.length).toBe(3);
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

describe("GFM table parsing (markdownItInstance)", () => {
  it("BUG FIX regression: markdownItInstance parses GFM tables (tables: true)", () => {
    const src = `| Name | Value |
| --- | --- |
| foo | 1 |`;
    const tokens = markdownItInstance.parse(src, {});
    const types = tokens.map((t) => t.type);
    expect(types).toContain("table_open");
    expect(types).toContain("thead_open");
    expect(types).toContain("tr_open");
    expect(types).toContain("th_open");
    expect(types).toContain("tbody_open");
    expect(types).toContain("td_open");
  });

  it("BUG FIX regression: markdownItInstance parses loose pipe tables after preprocessing", () => {
    const raw = `Name | Value
foo | 1`;
    const prepared = preprocessMarkdown(raw);
    const tokens = markdownItInstance.parse(prepared, {});
    const types = tokens.map((t) => t.type);
    expect(types).toContain("table_open");
  });
});
