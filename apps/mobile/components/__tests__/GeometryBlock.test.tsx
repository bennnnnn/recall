import { render } from "@testing-library/react-native";

import { GeometryBlock } from "@/components/rich/GeometryBlock";

// react-native-svg's <Text>/<TSpan> render as RNSVGText/RNSVGTSpan native
// components, not RN's built-in Text — RTL's getByText only matches the
// latter, so diagram labels are asserted via the serialized render tree.
describe("GeometryBlock", () => {
  it("renders a rectangle diagram with computed width/height labels", async () => {
    const content = JSON.stringify({ type: "rectangle", width: 6, height: 4, unit: "cm" });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());

    expect(tree).toContain("6 cm");
    expect(tree).toContain("4 cm");
  });

  it("renders a circle diagram with a radius label", async () => {
    const content = JSON.stringify({ type: "circle", radius: 5, unit: "cm" });
    const { toJSON } = await render(<GeometryBlock content={content} />);

    expect(JSON.stringify(toJSON())).toContain("5 cm");
  });

  it("renders the fallback message for unparseable content", async () => {
    const { getByText } = await render(<GeometryBlock content="not json" />);
    expect(getByText("Could not render geometry diagram.")).toBeOnTheScreen();
  });

  it("renders a triangle-by-sides (SSS) diagram with side labels", async () => {
    const content = JSON.stringify({ type: "triangle_sides", a: 3, b: 4, c: 5, unit: "cm" });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());

    expect(tree).toContain("3 cm");
    expect(tree).toContain("4 cm");
    expect(tree).toContain("5 cm");
    expect(tree).toContain("90°");
    expect(tree).toContain("36.9°");
    expect(tree).toContain("53.1°");
  });

  it("falls back for an impossible triangle (sides that can't close)", async () => {
    const content = JSON.stringify({ type: "triangle_sides", a: 1, b: 1, c: 10, unit: "cm" });
    const { getByText } = await render(<GeometryBlock content={content} />);
    expect(getByText("Could not render geometry diagram.")).toBeOnTheScreen();
  });

  it("renders a trapezoid diagram with top/bottom/height labels", async () => {
    const content = JSON.stringify({ type: "trapezoid", top: 4, bottom: 8, height: 5, unit: "cm" });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());

    expect(tree).toContain("4 cm");
    expect(tree).toContain("8 cm");
    expect(tree).toContain("5 cm");
  });

  it("renders a parallelogram diagram with base/height/side labels", async () => {
    const content = JSON.stringify({
      type: "parallelogram",
      base: 8,
      height: 4,
      side: 5,
      unit: "cm",
    });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());

    expect(tree).toContain("8 cm");
    expect(tree).toContain("4 cm");
    expect(tree).toContain("5 cm");
  });

  it("falls back when the parallelogram's side is shorter than its height", async () => {
    const content = JSON.stringify({
      type: "parallelogram",
      base: 8,
      height: 10,
      side: 3,
      unit: "cm",
    });
    const { getByText } = await render(<GeometryBlock content={content} />);
    expect(getByText("Could not render geometry diagram.")).toBeOnTheScreen();
  });

  it("renders a circle sector diagram with an angle label", async () => {
    const content = JSON.stringify({ type: "sector", radius: 5, angle_deg: 90, unit: "cm" });
    const { toJSON } = await render(<GeometryBlock content={content} />);

    expect(JSON.stringify(toJSON())).toContain("90");
  });

  it("draws a right-angle mark and 90° label on a right triangle", async () => {
    const content = JSON.stringify({
      type: "right_triangle",
      base: 3,
      height: 4,
      unit: "cm",
      show_angle: true,
    });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());
    expect(tree).toContain("90°");
    expect(tree).toContain("36.9°");
    expect(tree).toContain("53.1°");
    expect(tree).toContain("3 cm");
    expect(tree).toContain("4 cm");
    expect(tree).toContain("RNSVGRect");
    expect(tree).not.toContain("right-angle-mark");
  });

  it("draws leader lines when a skinny right triangle cannot fit 10° inside", async () => {
    const content = JSON.stringify({
      type: "right_triangle",
      base: 2,
      height: 34,
      unit: "cm",
      show_angle: true,
    });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());
    expect(tree).toContain("90°");
    expect(tree).toContain("RNSVGLine");
    expect(tree).not.toContain("interior-angle-leader");
  });

  it("draws a diagonal-angle arc when rectangle show_angle + show_diagonal", async () => {
    const content = JSON.stringify({
      type: "rectangle",
      width: 8,
      height: 5,
      unit: "cm",
      show_diagonal: true,
      show_angle: true,
      diagonal: 9.43,
      angle_deg: 32.01,
    });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());
    expect(tree).toContain("∠");
    expect(tree).toContain("RNSVGPath");
    expect(tree).not.toContain("90°");
  });

  it("draws side tick marks on a square by default", async () => {
    const content = JSON.stringify({ type: "square", side: 5, unit: "cm" });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    expect(JSON.stringify(toJSON())).toContain("RNSVGLine");
  });

  it("does not draw altitude on an SSS triangle unless asked", async () => {
    const content = JSON.stringify({
      type: "triangle_sides",
      a: 5,
      b: 9.4,
      c: 12.66,
      unit: "cm",
      show_angle: true,
    });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    expect(JSON.stringify(toJSON())).not.toContain("\"strokeDasharray\":[\"5\",\"4\"]");
  });

  it("draws altitude and equal-side ticks on an isosceles SSS triangle", async () => {
    const content = JSON.stringify({
      type: "triangle_sides",
      a: 6,
      b: 5,
      c: 5,
      unit: "cm",
      show_altitude: true,
      show_ticks: true,
      show_median: true,
    });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());
    expect(tree).toContain("\"strokeDasharray\":[\"5\",\"4\"]");
    expect(tree).toContain("RNSVGLine");
  });

  it("draws a separate median when scalene and show_median is set", async () => {
    const content = JSON.stringify({
      type: "triangle_sides",
      a: 3,
      b: 4,
      c: 5,
      unit: "cm",
      show_altitude: true,
      show_median: true,
      show_ticks: false,
    });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());
    expect(tree).toContain("\"strokeDasharray\":[\"5\",\"4\"]");
    expect(tree).toContain("\"strokeDasharray\":[\"2\",\"3\"]");
  });

  it("hides labels when show_labels is false", async () => {
    const content = JSON.stringify({
      type: "triangle",
      base: 8,
      height: 5,
      unit: "cm",
      show_labels: false,
    });
    const { toJSON } = await render(<GeometryBlock content={content} />);
    const tree = JSON.stringify(toJSON());
    expect(tree).not.toContain("8 cm");
    expect(tree).not.toContain("5 cm");
  });

  it("BUG FIX regression: SSS area label sits inside the SVG height", async () => {
    const content = JSON.stringify({ type: "triangle_sides", a: 3, b: 4, c: 5, unit: "cm" });
    const { getByTestId } = await render(<GeometryBlock content={content} />);
    const svg = getByTestId("sss-svg");
    const label = getByTestId("sss-area-label");
    expect(Number(label.props.y)).toBeLessThan(Number(svg.props.height));
  });
});
