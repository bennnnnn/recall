import { render, within } from "@testing-library/react-native";
import { Dimensions, StyleSheet } from "react-native";

import { MathText } from "@/components/rich/MathText";

const slantHeight = String.raw`\text{Slant Height} = \sqrt{ \left( \frac{6}{2} \right)^2 + 4^2 } = \sqrt{3^2 + 4^2} = \sqrt{9 + 16} = \sqrt{25} = 5\text{.}`;

describe("inline tall math overflow", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
  });
  afterEach(() => jest.restoreAllMocks());

  it("keeps the entire B12 chain reachable inside a paragraph-bounded horizontal viewport", async () => {
    const { getByTestId } = await render(<MathText latex={slantHeight} scrollOverflow />);
    const viewport = getByTestId("math-text-scroll");
    const formula = within(viewport).getByTestId("math-text-tall");
    const frameStyle = StyleSheet.flatten(viewport.props.style);
    const contentStyle = StyleSheet.flatten(formula.props.style);
    expect(viewport.props.horizontal).toBe(true);
    expect(viewport.props.showsHorizontalScrollIndicator).toBe(true);
    expect(viewport.props.bounces).toBe(false);
    expect(frameStyle).toMatchObject({ maxWidth: "100%", flexGrow: 0, flexShrink: 1 });
    expect(contentStyle.flexShrink).toBe(0);
    // A 300px list column constrains the viewport, never the math row. The
    // complete width remains scrollable, including the final equality.
    expect(contentStyle.width).toBeUndefined();
    expect(contentStyle.minWidth).toBeGreaterThan(500);
    expect(frameStyle.width).toBe(contentStyle.minWidth);
    expect(contentStyle.minWidth - Math.min(300, frameStyle.width)).toBeGreaterThan(200);
    expect(within(viewport).getByText(/Slant Height =/)).toHaveStyle({ fontSize: 16 });
    expect(within(viewport).getByText(/= 5\./)).toBeOnTheScreen();
    expect(within(viewport).getAllByTestId("math-sqrt")).toHaveLength(4);
    expect(within(viewport).getByText("6")).toHaveStyle({ fontSize: 14 });
    expect(viewport.props.accessibilityLabel).toMatch(/Slant Height.*= 5\./);
    expect(viewport.props.accessibilityLabel).not.toMatch(/\\sqrt|\\frac|\\text/);
  });

  it("lets native glyph width extend the scroll content beyond its estimate", async () => {
    const { getByTestId, getByText } = await render(
      <MathText latex={String.raw`\sqrt{99999999999999999999}`} scrollOverflow />,
    );
    const formula = getByTestId("math-text-tall");
    const style = StyleSheet.flatten(formula.props.style);
    // SpaceMono's20-digit radicand plus radical/margins is wider than198px.
    // A fixed child frame would hide its final digits outside contentSize.
    expect(style.minWidth).toBe(198);
    expect(style.width).toBeUndefined();
    expect(style.maxWidth).toBeUndefined();
    expect(style.flexShrink).toBe(0);
    expect(getByText("99999999999999999999")).toHaveStyle({ fontSize: 16 });
    expect(getByTestId("math-text-scroll").props.horizontal).toBe(true);
  });

  it("keeps a short fraction's original width, height, and type size", async () => {
    const { getByTestId, getByText } = await render(<MathText latex={String.raw`\frac{1}{2}`} scrollOverflow />);
    expect(getByTestId("math-text-scroll")).toHaveStyle({ width: 29, height: 44, maxWidth: "100%" });
    expect(getByTestId("math-text-tall")).toHaveStyle({ minWidth: 29, height: 44 });
    expect(getByText("1")).toHaveStyle({ fontSize: 14, lineHeight: 18 });
  });

  it("does not change ordinary prose/script wrapping or other math hosts", async () => {
    const { rerender, queryByTestId, getByText } = await render(<MathText latex="x^2 + 1" scrollOverflow />);
    expect(queryByTestId("math-text-scroll")).toBeNull();
    expect(getByText("x² + 1")).toBeOnTheScreen();
    await rerender(<MathText latex={slantHeight} />);
    expect(queryByTestId("math-text-scroll")).toBeNull();
  });
});
