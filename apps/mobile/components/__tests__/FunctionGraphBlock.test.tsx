import { render } from "@testing-library/react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";

describe("FunctionGraphBlock", () => {
  it("renders the expression as the chart title", async () => {
    const content = JSON.stringify({
      type: "function",
      expr: "x**2",
      points: [
        [0, 0],
        [1, 1],
        [2, 4],
      ],
    });
    const { getByText } = await render(<FunctionGraphBlock content={content} />);

    expect(getByText("y = x**2")).toBeOnTheScreen();
  });

  it("prefers an explicit title over the default y = expr label", async () => {
    const content = JSON.stringify({
      type: "function",
      expr: "x**2",
      title: "Parabola",
      points: [
        [0, 0],
        [1, 1],
      ],
    });
    const { getByText } = await render(<FunctionGraphBlock content={content} />);

    expect(getByText("Parabola")).toBeOnTheScreen();
  });

  it("renders one polyline per segment for a discontinuous (segmented) function", async () => {
    // Segments are how a backend-detected asymptote (e.g. tan(x)) is drawn
    // as separate Polylines instead of one line straight across the gap —
    // this exercises the segmentPolylines branch, not the single-polyline one.
    const content = JSON.stringify({
      type: "function",
      expr: "tan(x)",
      points: [
        [-1, -1.5],
        [1, 1.5],
      ],
      segments: [
        [
          [-1, -1.5],
          [0, 0],
        ],
        [
          [0.1, 0.5],
          [1, 1.5],
        ],
      ],
    });
    const { toJSON } = await render(<FunctionGraphBlock content={content} />);
    const tree = toJSON();
    const pathCount = (JSON.stringify(tree).match(/"RNSVGPath"/g) ?? []).length;

    expect(pathCount).toBe(2);
  });

  it("renders the fallback message for unparseable content", async () => {
    const { getByText } = await render(<FunctionGraphBlock content="not json" />);
    expect(getByText("rich.graph_error")).toBeOnTheScreen();
  });

  it("BUG FIX regression: renders a vertical line fence (x = c)", async () => {
    const content = JSON.stringify({
      type: "vertical",
      x: 4,
      y_min: -5,
      y_max: 5,
      title: "x = 4",
    });
    const { getByText, toJSON } = await render(<FunctionGraphBlock content={content} />);
    expect(getByText("x = 4")).toBeOnTheScreen();
    expect(JSON.stringify(toJSON())).toContain("RNSVGSvgView");
  });
});
