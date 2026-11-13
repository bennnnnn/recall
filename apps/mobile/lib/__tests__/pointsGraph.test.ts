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
