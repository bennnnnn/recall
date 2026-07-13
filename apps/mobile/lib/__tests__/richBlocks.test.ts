import { detectJsonRichFenceKind } from "@/lib/richBlocks";

describe("detectJsonRichFenceKind", () => {
  it("BUG FIX regression: recognizes a mistagged ```json geometry fence", () => {
    // The model is instructed to use ```geometry (never ```json) for
    // diagrams, but routinely ignores that. Without this detection the
    // fence fell through to a plain syntax-highlighted JSON code block
    // instead of the triangle/rectangle/square diagram it describes.
    const json = JSON.stringify({
      type: "right_triangle",
      base: 4,
      height: 5,
      unit: "cm",
      show_labels: true,
      show_hypotenuse: true,
      show_angle: true,
    });
    expect(detectJsonRichFenceKind(json)).toBe("geometry");
  });

  it("recognizes a mistagged ```json graph fence", () => {
    const json = JSON.stringify({
      type: "function",
      expr: "x**2",
      points: [
        [-2, 4],
        [0, 0],
        [2, 4],
      ],
    });
    expect(detectJsonRichFenceKind(json)).toBe("graph");
  });

  it("returns null for ordinary json that is not a geometry/graph spec", () => {
    expect(detectJsonRichFenceKind(JSON.stringify({ foo: "bar" }))).toBeNull();
  });

  it("returns null for non-JSON content", () => {
    expect(detectJsonRichFenceKind("not json at all")).toBeNull();
  });
});
