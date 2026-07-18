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

  it("renders two curves with a legend when expr2/points2 are present", async () => {
    const content = JSON.stringify({
      type: "function",
      expr: "x**2",
      points: [
        [-2, 4],
        [0, 0],
        [2, 4],
      ],
      expr2: "2*x",
      points2: [
        [-2, -4],
        [2, 4],
      ],
      label: "y = x^2",
      label2: "y = 2x",
    });
    const { getByText, toJSON } = await render(<FunctionGraphBlock content={content} />);

    expect(getByText("y = x^2")).toBeOnTheScreen();
    expect(getByText("y = 2x")).toBeOnTheScreen();
    // Polyline renders as RNSVGPath in this native mock (see the segmented
    // discontinuity test above) — one per curve.
    const pathCount = (JSON.stringify(toJSON()).match(/"RNSVGPath"/g) ?? []).length;
    expect(pathCount).toBe(2);
  });

  it("renders a single curve (no legend) when expr2 is absent", async () => {
    const content = JSON.stringify({
      type: "function",
      expr: "x**2",
      points: [
        [0, 0],
        [1, 1],
      ],
    });
    const { queryByText } = await render(<FunctionGraphBlock content={content} />);
    expect(queryByText(/y = 2x/)).toBeNull();
  });
});
