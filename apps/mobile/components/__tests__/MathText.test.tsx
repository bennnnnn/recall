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

  it("renders 1/2 as the precomposed vulgar fraction glyph", async () => {
    // Reported live: "¹─₂" (super + box-drawing bar + sub) does not read as
    // a fraction. Unicode's answer for common values is a single vulgar
    // glyph (½); for other digit pairs, superscript + FRACTION SLASH +
    // subscript (¹¹⁄₁₂).
    const { getByText } = await render(<MathText latex={"\\frac{1}{2}"} />);
    expect(getByText("½")).toBeOnTheScreen();
  });

  it("renders other simple digit fractions with Unicode fraction slash, single line", async () => {
    const { getByText } = await render(<MathText latex={"\\frac{11}{12}"} />);
    expect(getByText("¹¹⁄₁₂")).toBeOnTheScreen();
  });

  it("renders letter fractions as plain solidus, not raised/lowered letters", async () => {
    // `\frac{m}{m}` used to become ᵐ─ₘ via the super/sub+bar path — unreadable.
    const { getByText } = await render(<MathText latex={"\\frac{m}{m}"} />);
    expect(getByText("m/m")).toBeOnTheScreen();
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
