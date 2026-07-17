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
    // numerator has an internal "+" so it's wrapped to avoid ambiguity.
    expect(getByText("(-b + √(2))/2a")).toBeOnTheScreen();
  });
});
