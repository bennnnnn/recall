import { render, screen } from "@testing-library/react-native";

import { MathText } from "@/components/rich/MathText";

describe("MathText", () => {
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
    // Numerator is parenthesized (has "+"); den "2a" stays bare. Sqrt
    // radicand uses combining overline in the flattened plain path.
    expect(getByText("(-b + √2̅)")).toBeOnTheScreen();
    expect(getByText("2a")).toBeOnTheScreen();
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
    expect(screen.getByText(/m = ±√/)).toBeOnTheScreen();
  });
});
