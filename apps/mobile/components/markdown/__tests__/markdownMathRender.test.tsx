import { render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { formatAssistantMathExpr } from "@/lib/math/formatMathInput";

jest.mock("@/components/LinkPreviewCard", () => ({
  LinkPreviewCard: "LinkPreviewCard",
}));
jest.mock("expo-clipboard", () => ({ setStringAsync: jest.fn() }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  selectionAsync: jest.fn(),
}));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("@/components/WebPreviewCodeBlock", () => ({
  WebPreviewCodeBlock: "WebPreviewCodeBlock",
}));
jest.mock("@/components/rich/CircularClockBlock", () => ({
  CircularClockBlock: "CircularClockBlock",
}));
jest.mock("@/components/rich/AnswerBlock", () => ({
  AnswerBlock: "AnswerBlock",
}));
jest.mock("react-native-webview", () => {
  throw new Error("react-native-webview native module is not linked (test)");
});
jest.mock("@expo/dom-webview", () => {
  throw new Error("@expo/dom-webview native module is not linked (test)");
});
jest.mock("@/components/CodeBlock", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    CodeBlock: ({ code, lang }: { code: string; lang: string }) => (
      <RNText>{`${lang}:${code}`}</RNText>
    ),
  };
});

describe("MarkdownContent math rendering", () => {
  it("renders the exact H22 explanation fractions without invented pi parentheses", async () => {
    const { getByText, getAllByText, getAllByTestId, queryByText } = await render(
      <MarkdownContent content={String.raw`- Convert angle: $90^\circ = \frac{\pi}{2}$ radians
- Calculation: $4 \times \frac{\pi}{2} = 2\pi \approx 6.28$`} />,
    );
    expect(getByText("Convert angle:")).toBeOnTheScreen();
    expect(getByText("radians")).toBeOnTheScreen();
    expect(getByText(/= 2π ≈ 6.28/)).toBeOnTheScreen();
    expect(getAllByText("π")).toHaveLength(2);
    expect(getAllByTestId("math-frac")).toHaveLength(2);
    expect(queryByText(/\(π\)|\\frac|\\pi/)).toBeNull();
  });

  it("renders the exact S04 mean line without stray dollar delimiters", async () => {
    const { getByText, queryByText, getByTestId } = await render(
      <MarkdownContent content={String.raw`- Mean (\(\mu\)) = \( \frac{1+2+3}{3} = 2 \),`} />,
    );
    expect(getByText(/Mean \(μ\) =/)).toBeOnTheScreen();
    expect(getByText("1+2+3")).toBeOnTheScreen();
    expect(getByText("= 2,")).toBeOnTheScreen();
    expect(getByTestId("math-frac")).toBeOnTheScreen();
    expect(queryByText(/\$/)).toBeNull();
  });

  it("does not flash an unfinished inline fraction as raw LaTeX", async () => {
    const { queryByText, getByText } = await render(
      <MarkdownContent content={String.raw`Result: $\frac{1}`} streaming />,
    );
    expect(getByText("Result:")).toBeOnTheScreen();
    expect(queryByText(/\\frac|\$|frac/)).toBeNull();
  });

  it("gives a heavy inline integral full width outside a Text parent", async () => {
    const { getByTestId } = await render(
      <MarkdownContent content={String.raw`Evaluate $\int_0^1 x^2\,dx$.`} />,
    );
    expect(getByTestId("md-math-inline-wrap")).toBeOnTheScreen();
    expect(getByTestId("md-heavy-math-run")).toHaveStyle({ width: "100%" });
  });

  it("keeps prose and punctuation together beside a heavy limit", async () => {
    const { getByTestId, queryByText } = await render(
      <MarkdownContent content={String.raw`For $A \subseteq B$, use $\lim_{x\to0} x=0$.`} />,
    );
    expect(getByTestId("md-heavy-math-run")).toHaveStyle({ width: "100%" });
    expect(queryByText(/^,$/)).toBeNull();
    expect(queryByText(/^\.$/)).toBeNull();
  });

  it.each([",", ";"])("keeps leading %s with a heavy formula while retaining the following prose", async (punctuation) => {
    const { getByText, queryByText } = await render(
      <MarkdownContent content={String.raw`Evaluate $\int_0^1 x\,dx$${punctuation} then compare.`} />,
    );
    expect(getByText(`x dx${punctuation}`)).toBeOnTheScreen();
    expect(getByText("then compare.")).toBeOnTheScreen();
    expect(queryByText(/^[,;]\s*then compare\./)).toBeNull();
  });

  it("keeps the exact H11 inline prose together and punctuation attached to its fraction", async () => {
    const { getByText, queryByText, getByTestId } = await render(
      <MarkdownContent content={String.raw`Since $3^2 + 4^2 = 5^2$, it's a right triangle with legs 3 and 4, so area $= \tfrac{1}{2}(3)(4) = 6$.`} />,
    );
    expect(getByText(/Since 3² \+ 4² = 5², it[’']s a right triangle/)).toBeOnTheScreen();
    expect(getByText("(3)(4) = 6.")).toBeOnTheScreen();
    expect(queryByText(/^, it[’']s a right triangle/)).toBeNull();
    expect(queryByText(/^\.$/)).toBeNull();
    expect(getByTestId("md-math-inline-wrap")).toBeOnTheScreen();
    expect(getByTestId("math-frac")).toBeOnTheScreen();
  });

  it("attaches a root's comma while retaining following prose and simple math", async () => {
    const { getByText, queryByText, getByTestId } = await render(
      <MarkdownContent content={String.raw`Use $\sqrt{2}$, then compare $x^2$ with 4.`} />,
    );
    expect(getByText(/then compare x² with 4\./)).toBeOnTheScreen();
    expect(queryByText(/^, then compare/)).toBeNull();
    expect(getByTestId("md-math-inline-wrap")).toBeOnTheScreen();
  });

  it("typesets the exact cube-root callout note without raw LaTeX", async () => {
    const { getByTestId, queryByText } = await render(
      <MarkdownContent content={String.raw`> [!NOTE]
> The expression doesn’t simplify to a whole number or a simpler radical, so $\sqrt[3]{3}$ is the exact form.`} />,
    );
    expect(getByTestId("rich-math-body")).toBeOnTheScreen();
    expect(queryByText(/\\sqrt|\$\\/)).toBeNull();
  });

  it("typesets math in a callout title and preserves source examples in code", async () => {
    const { getAllByTestId, getByText, queryByText } = await render(
      <MarkdownContent content={'```callout-note\nExact $x^2$\nUse $\\frac{1}{2}$; code: `x_1` costs $5 and $10.\n```'} />,
    );
    expect(getAllByTestId("rich-math-body")).toHaveLength(2);
    expect(getByText("x_1")).toBeOnTheScreen();
    expect(getByText("$5")).toBeOnTheScreen();
    expect(getByText("$10.")).toBeOnTheScreen();
    expect(queryByText(/\\frac/)).toBeNull();
  });

  it("keeps explicit LaTeX source code literal inside a callout", async () => {
    const { getByText } = await render(
      <MarkdownContent content={'```callout-note\nWrite `$\\frac{1}{2}$` to display $x^2$.\n```'} />,
    );
    expect(getByText('$\\frac{1}{2}$')).toBeOnTheScreen();
  });

  it("typesets inline math in a numbered step, not raw \\frac", async () => {
    const { getByTestId, queryByText } = await render(
      <MarkdownContent content={"1. So $m = \\frac{1}{2}$."} />,
    );
    expect(getByTestId("math-frac")).toBeOnTheScreen();
    expect(getByTestId("md-math-inline-wrap")).toBeOnTheScreen();
    expect(queryByText(/\\frac/)).toBeNull();
  });

  it("typesets inline math inside a list item", async () => {
    const { getByText } = await render(
      <MarkdownContent content="- Let $x^2$ be the square." />,
    );
    expect(getByText("x²")).toBeOnTheScreen();
  });

  it("keeps a bold math label and its value on one list line", async () => {
    const { queryByText } = await render(
      <MarkdownContent content={"- **Slope ($m$):** 3, meaning y increases by 3."} />,
    );
    expect(queryByText(/^:$/)).toBeNull();
    expect(queryByText(")")).toBeNull();
    expect(queryByText("m")).toBeOnTheScreen();
  });

  it("BUG FIX regression: inline split-± fractions keep numerators visible", async () => {
    // Live: "Now we split it for the ±" + $x = \frac{5+1}{2}$ painted the
    // stacked frac over the prose (iOS View-in-Text 0×0) so the numbers
    // above the vinculum could not be read.
    const { getAllByTestId, getByText, queryByText } = await render(
      <MarkdownContent
        content={
          "Now, we split it for the ±:\n\n" +
          "* **Solution 1:** $x = \\frac{5+1}{2} = \\frac{6}{2} = 3$\n" +
          "* **Solution 2:** $x = \\frac{5-1}{2} = \\frac{4}{2} = 2$"
        }
      />,
    );
    expect(getAllByTestId("md-math-inline-wrap").length).toBeGreaterThan(0);
    expect(getAllByTestId("math-frac").length).toBeGreaterThanOrEqual(4);
    expect(getByText("5+1")).toBeOnTheScreen();
    expect(getByText("5-1")).toBeOnTheScreen();
    expect(queryByText(/\\frac/)).toBeNull();
  });

  it("BUG FIX regression: bare-ASCII quadratic-formula steps stack a real fraction (not literal '/'), given the assistant mathFormat", async () => {
    // Live bug: Recall answered "3x^2 - 11x + 6 = 0" with steps written as
    // plain ASCII division ("(11 ± 7) / 6", "√(49)") because the model
    // never wrapped them in \frac{}/\sqrt{} — MessageBubble now passes
    // `formatAssistantMathExpr` as `mathFormat` so normalizeImplicitMath's
    // bare-equation wrap also converts the slash/radical, not just ±→\pm.
    const { getAllByTestId, queryByText } = await render(
      <MarkdownContent
        content={
          "Steps\n\n" +
          "4. Split the two roots:\n" +
          "- x = (11 + 7) / 6 = 18 / 6 = 3\n" +
          "- x = (11 - 7) / 6 = 4 / 6 = 2/3"
        }
        mathFormat={formatAssistantMathExpr}
      />,
    );
    expect(getAllByTestId("math-frac").length).toBeGreaterThanOrEqual(4);
    // No leftover literal division text once every fraction is stacked.
    expect(queryByText(/\(11 \+ 7\) \/ 6/)).toBeNull();
    expect(queryByText(/\(11 - 7\) \/ 6/)).toBeNull();
    expect(queryByText(/\\frac/)).toBeNull();
  });

  it("treats a single newline in a list item as a space, not a stacked line", async () => {
    const { queryByText } = await render(
      <MarkdownContent
        content={"- It's a\n**linear equation**\nin slope-intercept form."}
      />,
    );
    expect(queryByText(/^It's a$/)).toBeNull();
    expect(queryByText(/linear equation/)).toBeOnTheScreen();
  });

  it("BUG FIX regression: second quadratic root stays on the solve bullet", async () => {
    const { getByText, queryByText } = await render(
      <MarkdownContent
        content={[
          "4. **Solve for x**:",
          "   - $2x - 1 = 0 \\rightarrow x = 1/2$",
          "   -",
          "",
          "```math",
          "x - 3 = 0 \\rightarrow x = 3",
          "```",
        ].join("\n")}
      />,
    );
    expect(queryByText(/\\rightarrow/)).toBeNull();
    expect(getByText(/x = 3/)).toBeOnTheScreen();
  });

  it("BUG FIX regression: For x = 3: check is not packed onto the formula line", async () => {
    const { getAllByText, queryByText } = await render(
      <MarkdownContent
        content={
          "You can check:\n" +
          "- For $x = 3$: $2(3)^2 - 7(3) + 3 = 18 - 21 + 3 = 0$ ✓\n" +
          "- For $x$ = $\\frac{1}{2}$\n" +
          "$2(\\frac{1}{2})^2 - 7(\\frac{1}{2}) + 3 = \\frac{1}{2} - \\frac{7}{2} + 3 = -3 + 3 = 0$\n" +
          "✓"
        }
      />,
    );
    expect(getAllByText(/For/).length).toBeGreaterThanOrEqual(2);
    expect(queryByText(/18 - 21 \+ 3 = 0/)).toBeNull();
    expect(queryByText(/1\/2 - 7\/2 \+ 3 = 0/)).toBeNull();
    expect(getAllByText("= 0").length).toBeGreaterThanOrEqual(2);
    expect(getAllByText("= 18 - 21 + 3").length).toBeGreaterThanOrEqual(1);
  });
});
