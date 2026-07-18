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
});
