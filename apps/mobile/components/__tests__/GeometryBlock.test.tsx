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
});
