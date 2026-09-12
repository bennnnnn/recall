import { Dimensions, StyleSheet } from "react-native";
import { render, screen } from "@testing-library/react-native";

import { MathText } from "@/components/rich/MathText";

describe("MathText", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({
      width: 390, height: 844, scale: 3, fontScale: 1,
    });
  });

  afterEach(() => jest.restoreAllMocks());
  it("renders plain text with no math markup unchanged", async () => {
    const { getByText } = await render(<MathText latex="x + 1" />);
    expect(getByText("x + 1")).toBeOnTheScreen();
  });

  it("renders a superscript digit as a real Unicode superscript char", async () => {
    // "2" has a Unicode superscript mapping (unicodeSupSub.ts) — MathText
    // prefers that over the styled-smaller-Text fallback so it reads raised
    // in plain text with no WebView.
    const { getByText } = await render(<MathText latex="x^2" />);
    expect(getByText("x²")).toBeOnTheScreen();
  });

  it("renders nothing for empty latex", async () => {
    const { toJSON } = await render(<MathText latex="   " />);
    expect(toJSON()).toBeNull();
  });

  it("renders a simple fraction as a stacked vinculum (num / bar / den)", async () => {
    // User-requested: real stacked fraction with a straight horizontal
    // vinculum — not ½, not ¹⁄₂, and never the broken ¹─₂ bar hack.
    const { getByText, getByTestId } = await render(
      <MathText latex={"\\frac{1}{2}"} />,
    );
    expect(getByTestId("math-frac")).toBeOnTheScreen();
    expect(getByTestId("math-vinculum")).toBeOnTheScreen();
    expect(getByText("1")).toBeOnTheScreen();
    expect(getByText("2")).toBeOnTheScreen();
    // Root is a sized View (not Text wrapping a View) so the paragraph Text
    // can treat it as a character. Nested Text>View was 0×0 on iOS and the
    // next sentence painted on top of this one (live: part (b) smudge).
    expect(getByTestId("math-text-tall")).toHaveStyle({ width: 29, height: 44 });
    expect(getByTestId("math-frac")).toHaveStyle({ width: 23, height: 44 });
    expect(getByText("1")).toHaveStyle({ fontSize: 14, lineHeight: 18 });
  });

  it("renders letter fractions stacked the same way (m over m)", async () => {
    const { getByTestId, getAllByText } = await render(
      <MathText latex={"\\frac{m}{m}"} />,
    );
    expect(getByTestId("math-frac")).toBeOnTheScreen();
    expect(getByTestId("math-vinculum")).toBeOnTheScreen();
    expect(getAllByText("m")).toHaveLength(2);
  });

  it("renders a complex fraction stacked, with the multi-term numerator parenthesized", async () => {
    const { getByTestId, getByText } = await render(
      <MathText latex={"\\frac{-b + \\sqrt{2}}{2a}"} />,
    );
    expect(getByTestId("math-frac")).toBeOnTheScreen();
    expect(getByTestId("math-vinculum")).toBeOnTheScreen();
    expect(getByTestId("math-sqrt")).toBeOnTheScreen();
    expect(getByText("2")).toBeOnTheScreen();
    expect(getByText("2a")).toBeOnTheScreen();
  });

  it("BUG FIX regression: sqrt inside a fraction keeps one bar over b^2 - 4ac", async () => {
    // Live quadratic formula: flattened combining overlines turned `-` into a
    // fake `=` and sized the vinculum from those extra marks so it ran under
    // the following prose.
    const { getByTestId, getByText, queryByText } = await render(
      <MathText latex={String.raw`x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}`} />,
    );
    expect(getByTestId("math-sqrt")).toBeOnTheScreen();
    expect(getByTestId("math-sqrt-radicand")).toBeOnTheScreen();
    expect(queryByText(/̅/)).toBeNull();
    expect(getByText("b")).toBeOnTheScreen();
    expect(getByText(/4ac/)).toBeOnTheScreen();
    const frac = getByTestId("math-frac");
    const width = StyleSheet.flatten(frac.props.style).width as number;
    expect(width).toBeGreaterThan(40);
    expect(width).toBeLessThan(200);
  });

  it("BUG FIX regression: \\pm immediately followed by a digit does not become a false superscript", async () => {
    // Reported live: a step-by-step solve rendered "x = \pm\sqrt{4}" then
    // simplified to "x = \pm2" (no space) — the implicit-exponent heuristic
    // used to mistake the command's trailing letter for a bare variable and
    // rewrite it to "\pm^2", displaying "±²" ("plus or minus squared")
    // instead of "± 2".
    const { getByText } = await render(<MathText latex={String.raw`x = \pm2`} />);
    expect(getByText("x = ±2")).toBeOnTheScreen();
  });

  it("BUG FIX regression: a fraction inside \\sqrt{} still does not leak raw \\frac text", async () => {
    // Sqrt path flattens to plain text (radical + overline); nested View
    // stacks inside the radicand aren't used — but \\frac must not leak.
    const { queryByText } = await render(
      <MathText latex={String.raw`m = \pm\sqrt{\frac{M}{2}}`} />,
    );
    expect(queryByText(/\\frac/)).toBeNull();
    expect(screen.getByText(/m = ±/)).toBeOnTheScreen();
  });

  it("BUG FIX regression: \\neq / \\ne render as ≠, not ≡ or the word ne", async () => {
    const neq = await render(<MathText latex={String.raw`a \neq 0`} />);
    expect(neq.getByText(/≠/)).toBeOnTheScreen();
    expect(neq.queryByText(/≡/)).toBeNull();
    const ne = await render(<MathText latex={String.raw`a \ne 0`} />);
    expect(ne.getByText(/≠/)).toBeOnTheScreen();
    expect(ne.queryByText(/\bne\b/)).toBeNull();
  });

  it("does not turn \\cdots into a leftover s", async () => {
    const { getByText, queryByText } = await render(
      <MathText latex={String.raw`n \times (n-1) \times \cdots \times 1`} />,
    );
    expect(getByText(/⋯/)).toBeOnTheScreen();
    expect(queryByText(/·s/)).toBeNull();
    expect(queryByText(/\\cdots/)).toBeNull();
  });

  it("renders a square root with a vinculum, not nth-root brackets", async () => {
    const { getByTestId, queryByText } = await render(
      <MathText latex={String.raw`9\sqrt{9}`} />,
    );
    expect(getByTestId("math-sqrt")).toBeOnTheScreen();
    expect(queryByText(/√\[/)).toBeNull();
  });

  it("BUG FIX regression: the radicand is full size under the bar, not a subscript", async () => {
    // Reported live ("the square root is totally broken"): the radicand reused
    // the fraction-sized side renderer (11px) and bottom-aligned against the
    // 16px √, so `\sqrt{8}` read as "√ subscript 8" with the bar floating in
    // the sign's leading.
    const { getByTestId } = await render(<MathText latex={String.raw`\sqrt{8}`} />);
    expect(getByTestId("math-sqrt")).toHaveStyle({ alignItems: "flex-start" });
    expect(screen.getByText("8")).toHaveStyle({ fontSize: 16, lineHeight: 20 });
  });

  it("BUG FIX regression: a script inside \\sqrt{} does not leak a literal caret", async () => {
    // Live: "√ 8^3" — the radicand was flattened with segmentsToPlain, which
    // turns a sup segment back into `^3`.
    const { queryByText } = await render(<MathText latex={String.raw`\sqrt{8^3}`} />);
    expect(queryByText(/\^/)).toBeNull();
    expect(screen.getByText("8")).toBeOnTheScreen();
    expect(screen.getByText("³")).toBeOnTheScreen();
  });

  it("renders an nth-root index without \\sqrt[n] brackets", async () => {
    const { getByTestId, getAllByText, queryByText } = await render(
      <MathText latex={String.raw`\sqrt[9]{9}`} />,
    );
    expect(getByTestId("math-sqrt")).toBeOnTheScreen();
    expect(getAllByText("9")).toHaveLength(2);
    expect(queryByText("√[9]9̅")).toBeNull();
    expect(queryByText(/√\[9\]/)).toBeNull();
  });

  it.each(["9^{1/6}", String.raw`9^{\frac{1}{6}}`])(
    "keeps fractional exponent %s readable and raised in a sized native View",
    async (latex) => {
      const { getByTestId, getByText, queryByText } = await render(<MathText latex={latex} />);
      expect(getByText("1/6")).toHaveStyle({ fontSize: 14, lineHeight: 18 });
      expect(getByTestId("math-fractional-sup")).toHaveStyle({ paddingBottom: 12 });
      expect(getByTestId("math-text-tall")).toHaveStyle({ height: 30 });
      expect(queryByText("¹⁄⁶")).toBeNull();
    },
  );

  it("preserves scripts in fraction sides instead of flattening to literal carets", async () => {
    const { queryByText, getByText } = await render(<MathText latex={String.raw`\frac{x^2}{y_1}`} />);
    expect(queryByText(/\^|_/)).toBeNull();
    expect(getByText("²")).toBeOnTheScreen();
    expect(getByText("₁")).toBeOnTheScreen();
  });

  it("reserves the full height of nested fraction stacks", async () => {
    const { getAllByTestId, getByTestId } = await render(
      <MathText latex={String.raw`\frac{\frac{1}{2}}{\frac{3}{4}}`} />,
    );
    const stacks = getAllByTestId("math-frac");
    const outer = StyleSheet.flatten(stacks[0].props.style);
    const inner = StyleSheet.flatten(stacks[1].props.style);
    expect(outer.height).toBeGreaterThanOrEqual(2 * inner.height + 6);
    expect(getByTestId("math-text-tall")).toHaveStyle({ height: outer.height });
  });

  it("scales the native attachment bounds with the requested text size", async () => {
    const { getByTestId, getByText } = await render(
      <MathText latex={String.raw`\frac{1}{2}`} fontSize={24} />,
    );
    expect(getByText("1")).toHaveStyle({ fontSize: 21, lineHeight: 27 });
    expect(getByTestId("math-frac")).toHaveStyle({ width: 34.5, height: 66 });
  });

  it("reserves more space when the device increases its font scale", async () => {
    jest.spyOn(Dimensions, "get").mockReturnValue({
      width: 390, height: 844, scale: 3, fontScale: 1.5,
    });
    const { getByTestId } = await render(<MathText latex={String.raw`\frac{1}{2}`} />);
    expect(getByTestId("math-frac")).toHaveStyle({ width: 34.5, height: 66 });
    expect(getByTestId("math-text-tall")).toHaveStyle({ width: 43.5, height: 66 });
  });

  it("raises the root degree above the hook without shrinking the radicand", async () => {
    const { getByText } = await render(<MathText latex={String.raw`\sqrt[6]{9}`} />);
    expect(getByText("6")).toHaveStyle({ fontSize: 12, marginTop: -4 });
    expect(getByText("9")).toHaveStyle({ fontSize: 16 });
  });
});
