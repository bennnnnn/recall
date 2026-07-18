import { render } from "@testing-library/react-native";

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

  it("renders a simple numeric fraction as raised/lowered Unicode digits, single line", async () => {
    // BUG FIX regression: the old renderer stacked numerator/denominator
    // across two rows via a "\n" inside a nested Text — React Native
    // doesn't grow the *surrounding* paragraph's line height for that, so
    // the stack visually overlapped whatever text came before/after it
    // whenever the fraction wasn't the only thing on its line (reported
    // live: "3/4 = 9/12 and 1/6 = 2/12" read as a jumbled column of
    // numbers). Simple digit fractions now render on one line as raised/
    // lowered Unicode digits either side of a fraction slash.
    const { getByText } = await render(<MathText latex={"\\frac{11}{12}"} />);
    expect(getByText("¹¹⁄₁₂")).toBeOnTheScreen();
  });

  it("renders a complex fraction (non-digit numerator) on one line, parenthesized", async () => {
    const { getByText } = await render(
      <MathText latex={"\\frac{-b + \\sqrt{2}}{2a}"} />,
    );
    // "2a" is a single atomic token (no operator) so it stays bare; the
    // numerator has an internal "+" so it's wrapped to avoid ambiguity. The
    // sqrt's own radicand sits under a combining overline, not in parens.
    expect(getByText("(-b + √2̅)/2a")).toBeOnTheScreen();
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

  it("BUG FIX regression: a fraction inside \\sqrt{} renders the fraction, not raw \\frac text", async () => {
    // Reported live: "m = \pm\sqrt{\frac{M}{2}}" showed literal, unrendered
    // "\frac{M}{2}" text inside the root instead of a fraction.
    const { getByText, queryByText } = await render(
      <MathText latex={String.raw`m = \pm\sqrt{\frac{M}{2}}`} />,
    );
    expect(getByText("m = ±√M̅/̅2̅")).toBeOnTheScreen();
    expect(queryByText(/\\frac/)).toBeNull();
  });
});
