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
});
