import { render, waitFor } from "@testing-library/react-native";

import { MATH_SVG_EX_PX, MathSvgView } from "@/components/rich/MathSvgView";
import { setSvgMathRendererForTest } from "@/lib/math/svgMath";

// Capture the xml instead of mounting react-native-svg's native view.
const mockSvgXml = jest.fn((_props: { xml: string; width: number; height: number }) => null);
jest.mock("react-native-svg", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    const React = jest.requireActual<typeof import("react")>("react");
    const { View } = jest.requireActual<typeof import("react-native")>("react-native");
    return React.createElement(View, props);
  },
  Path: (props: Record<string, unknown>) => {
    const React = jest.requireActual<typeof import("react")>("react");
    const { View } = jest.requireActual<typeof import("react-native")>("react-native");
    return React.createElement(View, props);
  },
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

  it("keeps a short formula at its own height", async () => {
    await render(<MathSvgView latex="gt" textColor="#111111" minHeight={48} />);
    await waitFor(() => expect(mockSvgXml).toHaveBeenCalled());
    const props = mockSvgXml.mock.calls[0][0];
    expect(props.height).toBeLessThan(48);
    expect(props.width / props.height).toBeGreaterThan(1);
    expect(props.xml).toContain("<path");
    expect(props.xml).not.toContain('data-background="true"');
  });

  it.each([
    String.raw`\frac{mg}{k}`,
    String.raw`e^{-(k/m)t}`,
    String.raw`\lim_{k \to 0} v(t) = gt`,
    String.raw`\int_0^t v(t)\,dt`,
    String.raw`v_{T}`,
    String.raw`v(t)=\frac{mg}{k}\left(1-e^{-(k/m)t}\right)`,
  ])("renders %s as glyphs, not an error bar", async (latex) => {
    await render(<MathSvgView latex={latex} textColor="#111111" />);
    await waitFor(() => expect(mockSvgXml).toHaveBeenCalled());
    const props = mockSvgXml.mock.calls.at(-1)?.[0];
    expect(props?.xml).toContain("<path");
    expect(props?.xml).not.toContain('data-background="true"');
    expect(props?.height).toBeGreaterThan(1);
    expect(props?.width).toBeGreaterThan(1);
  });

  it("falls back when MathJax paints only an error bar", async () => {
    const { findByTestId } = await render(
      <MathSvgView latex={String.raw`\frac{mg}{`} textColor="#111111" />,
    );
    await findByTestId("math-svg-fallback");
    expect(mockSvgXml).not.toHaveBeenCalled();
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

describe("MathSvgView does not stretch a short SVG to minHeight", () => {
  beforeEach(() => {
    setSvgMathRendererForTest(
      () =>
        '<mjx-container><svg xmlns="http://www.w3.org/2000/svg" width="1.88ex" height="1.2ex" viewBox="0 0 800 500">' +
        '<path d="M0 0"></path></svg></mjx-container>',
    );
  });

  it("sizes the drawing from ex, not the 48px loading slot", async () => {
    await render(<MathSvgView latex="gt" textColor="#111111" minHeight={48} />);
    await waitFor(() => expect(mockSvgXml).toHaveBeenCalled());
    const props = mockSvgXml.mock.calls[0][0];
    expect(props.height).toBeCloseTo(1.2 * MATH_SVG_EX_PX, 5);
    expect(props.width).toBeCloseTo(1.88 * MATH_SVG_EX_PX, 5);
    expect(props.height).toBeLessThan(48);
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
