import { render, waitFor } from "@testing-library/react-native";

import { MathSvgView } from "@/components/rich/MathSvgView";
import { setSvgMathRendererForTest } from "@/lib/math/svgMath";

// Capture the xml instead of mounting react-native-svg's native view.
const mockSvgXml = jest.fn((_props: { xml: string; width: number; height: number }) => null);
jest.mock("react-native-svg", () => ({
  SvgXml: (props: { xml: string; width: number; height: number }) => mockSvgXml(props),
}));

afterEach(() => {
  setSvgMathRendererForTest(null);
  mockSvgXml.mockClear();
});

describe("MathSvgView (real MathJax conversion)", () => {
  it("renders a fraction as theme-colored SVG", async () => {
    await render(<MathSvgView latex={String.raw`x = \frac{1}{2}`} textColor="#123456" />);
    await waitFor(() => expect(mockSvgXml).toHaveBeenCalled());
    const props = mockSvgXml.mock.calls[0][0];
    expect(props.xml).toContain("<svg");
    // currentColor must be substituted — react-native-svg cannot resolve it.
    expect(props.xml).not.toContain("currentColor");
    expect(props.xml).toContain("#123456");
    expect(props.width).toBeGreaterThan(1);
    expect(props.height).toBeGreaterThan(10);
  });

  it("renders a multline environment (the old MathJax-WebView reason)", async () => {
    await render(
      <MathSvgView
        latex={String.raw`\begin{multline} a+b+c \\ d+e+f \end{multline}`}
        textColor="#eeeeee"
      />,
    );
    await waitFor(() => expect(mockSvgXml).toHaveBeenCalled());
    expect(mockSvgXml.mock.calls[0][0].xml).toContain("<svg");
  });
});

describe("MathSvgView fallback", () => {
  beforeEach(() => {
    setSvgMathRendererForTest(() => {
      throw new Error("parse failure");
    });
  });

  it("falls back to readable MathText when conversion fails", async () => {
    const { findByTestId, getByText } = await render(
      <MathSvgView latex="x + 1 = 2" textColor="#111111" />,
    );
    await findByTestId("math-svg-fallback");
    expect(getByText("x + 1 = 2")).toBeOnTheScreen();
    expect(mockSvgXml).not.toHaveBeenCalled();
  });

  it("BUG FIX regression: nested \\frac/\\sqrt fallback hosts a View, not a clipped Text", async () => {
    // iOS clips a View nested inside a Text to the line box — the radicand's
    // bottom was cut off. The fallback must render MathText in a plain View.
    const { findByTestId } = await render(
      <MathSvgView latex={String.raw`\frac{1}{2} + \sqrt{4}`} textColor="#111111" />,
    );
    await findByTestId("math-svg-fallback");
  });
});
