import { parsePointsGraph, pointsChartHeight, quadrantNumerals } from "@/lib/math/pointsGraph";

const G16 = {
  type: "points",
  title: "A(2, 3), B(−1, 4), C(−3, −2), D(4, −1)",
  points: [
    { x: 2, y: 3, label: "A(2, 3)" },
    { x: -1, y: 4, label: "B(−1, 4)" },
    { x: -3, y: -2, label: "C(−3, −2)" },
    { x: 4, y: -1, label: "D(4, −1)" },
  ],
  x_min: -5,
  x_max: 5,
  y_min: -5,
  y_max: 5,
  quadrants: true,
};

describe("points on a coordinate plane", () => {
  it("reads the server's points and their quadrants", () => {
    const graph = parsePointsGraph(JSON.stringify(G16));
    expect(graph?.points.map((p) => p.label)).toEqual(["A(2, 3)", "B(−1, 4)", "C(−3, −2)", "D(4, −1)"]);
    expect(graph && quadrantNumerals(graph).map((q) => q.text)).toEqual(["I", "II", "III", "IV"]);
  });

  it.each([
    ["a point outside its plane", { ...G16, x_max: 3 }],
    ["a point with no label", { ...G16, points: [{ x: 1, y: 1 }] }],
    ["bounds the wrong way round", { ...G16, y_min: 5, y_max: -5 }],
    ["another kind of graph", { ...G16, type: "function" }],
  ])("refuses %s", (_name, raw) => {
    expect(parsePointsGraph(JSON.stringify(raw))).toBeNull();
  });

  it.each([
    ["one axis far taller", { ...G16, points: [{ x: 1, y: 60, label: "(1, 60)" }], y_min: -181, y_max: 181 }],
    ["one axis far wider", { ...G16, points: [{ x: 100, y: 2, label: "(100, 2)" }], x_min: -101, x_max: 101 }],
  ])("keeps the card a sensible shape with %s", (_name, raw) => {
    const graph = parsePointsGraph(JSON.stringify(raw));
    const height = graph ? pointsChartHeight(graph, 330, 16) : 0;
    expect(height).toBeGreaterThanOrEqual(0.5 * 298 + 32);
    expect(height).toBeLessThanOrEqual(1.25 * 298 + 32);
  });

  it("draws a unit as tall as it is wide when that fits", () => {
    const graph = parsePointsGraph(JSON.stringify(G16));
    expect(graph && pointsChartHeight(graph, 330, 16)).toBeCloseTo(330);
  });
});

// Triangle ABC reflected in y = x, as the server draws it (`math/figure/plane`).
const REFLECTED = {
  type: "points",
  points: [
    { x: 1, y: 3, label: "A(1, 3)", side: "nw" },
    { x: 3, y: 1, label: "A′", role: "image", side: "se" },
  ],
  x_min: -2,
  x_max: 6,
  y_min: -2,
  y_max: 6,
  segments: [
    { start: [1, 3], end: [4, 1], ticks: 1 },
    { start: [3, 1], end: [1, 4], role: "image", dashed: true },
    { start: [-2, -2], end: [6, 6], role: "guide", label: "y = x" },
    { start: [0, 0], end: [4, 1], role: "guide", dashed: true, arrow: true },
  ],
  polygons: [{ points: [[1, 3], [4, 1], [5, 4]] }, { points: [[3, 1], [1, 4], [4, 5]], role: "image" }],
  circles: [{ center: [0, 0], radius: 2 }],
  right_angles: [{ at: [0, 0], a: [1, 0], b: [0, 1] }],
};

describe("coordinate geometry on the plane", () => {
  it("reads the server's segments, shapes, circles, marks and the image's roles", () => {
    const graph = parsePointsGraph(JSON.stringify(REFLECTED));
    expect(graph?.points.map((p) => [p.label, p.role, p.side])).toEqual([
      ["A(1, 3)", "shape", "nw"],
      ["A′", "image", "se"],
    ]);
    expect(graph?.segments.map((s) => [s.role, s.dashed, s.arrow, s.ticks, s.label])).toEqual([
      ["shape", false, false, 1, ""],
      ["image", true, false, 0, ""],
      ["guide", false, false, 0, "y = x"],
      ["guide", true, true, 0, ""],
    ]);
    expect(graph?.polygons.map((p) => p.role)).toEqual(["shape", "image"]);
    expect(graph?.circles).toEqual([{ center: [0, 0], radius: 2, role: "shape" }]);
    expect(graph?.rightAngles).toHaveLength(1);
  });

  it("leaves out a malformed part, never the plane", () => {
    const graph = parsePointsGraph(
      JSON.stringify({
        ...REFLECTED,
        segments: [{ start: [1, "x"], end: [2, 2] }, { start: [0, 0], end: [1, 1], role: "paint", ticks: 9 }],
        polygons: [{ points: [[0, 0], [1, 1]] }],
        circles: [{ center: [0, 0], radius: -1 }],
        right_angles: [{ at: [0, 0], a: [1, 0] }],
      }),
    );
    expect(graph?.points).toHaveLength(2);
    expect(graph?.segments).toEqual([
      { start: [0, 0], end: [1, 1], label: "", role: "shape", dashed: false, arrow: false, ticks: 3 },
    ]);
    expect(graph?.polygons).toEqual([]);
    expect(graph?.circles).toEqual([]);
    expect(graph?.rightAngles).toEqual([]);
  });

  it("reads an older plane with no parts as points alone", () => {
    const graph = parsePointsGraph(JSON.stringify(G16));
    expect(graph && [graph.segments, graph.polygons, graph.circles, graph.rightAngles]).toEqual([[], [], [], []]);
    expect(graph?.points.every((p) => p.role === "shape" && p.side === "ne")).toBe(true);
  });
});
