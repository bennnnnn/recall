import {
  evalGraphExpr,
  formatSeriesExpr,
  inequalityFillPoints,
  normalizePlotExpr,
  parseGraphExpr,
  parseGraphRelation,
  sampleGraphExpr,
} from "@/lib/graphExpr";

describe("graphExpr", () => {
  it("evaluates 4x^2-5x-12 at the vertex and origin", () => {
    const node = parseGraphExpr("4x^2-5x-12");
    expect(node).not.toBeNull();
    expect(evalGraphExpr(node!, 0)).toBe(-12);
    expect(evalGraphExpr(node!, 0.625)).toBeCloseTo(-13.5625, 6);
  });

  it("strips y= and a trailing =0 so a quadratic equation plots as a U", () => {
    expect(normalizePlotExpr("y = 4x^2-5x-12")).toBe("4x^2-5x-12");
    expect(normalizePlotExpr("4x^2-5x-12=0")).toBe("4x^2-5x-12");
    const node = parseGraphExpr("4x^2-5x-12=0");
    expect(evalGraphExpr(node!, 0)).toBe(-12);
  });

  it("leaves an ellipse as a relation (not y=f(x))", () => {
    expect(parseGraphExpr("x^2 + y^2 = 1")).toBeNull();
  });

  it("handles implicit multiplication, powers, and unary minus", () => {
    const node = parseGraphExpr("-x^2 + 2(x+1)");
    expect(evalGraphExpr(node!, 3)).toBe(-9 + 8);
    expect(evalGraphExpr(parseGraphExpr("2^3^2")!, 0)).toBe(512);
  });

  it("samples sin and splits 1/x at the pole", () => {
    expect(evalGraphExpr(parseGraphExpr("sin(0)")!, 0)).toBeCloseTo(0);
    const sampled = sampleGraphExpr(parseGraphExpr("1/x")!, -2, 2, 40);
    expect(sampled.segments?.length).toBeGreaterThanOrEqual(2);
  });

  it("rejects unknown identifiers and empty input", () => {
    expect(parseGraphExpr("hello")).toBeNull();
    expect(parseGraphExpr("")).toBeNull();
  });

  it("evaluates x^2/3 as (x^2)/3", () => {
    expect(evalGraphExpr(parseGraphExpr("x^2/3")!, 3)).toBe(3);
  });

  it("parses y < 2x and y > x^2 as relations", () => {
    const below = parseGraphRelation("y < 2x");
    expect(below?.cmp).toBe("<");
    expect(evalGraphExpr(below!.node, 1)).toBe(2);
    const above = parseGraphRelation("y > x^2");
    expect(above?.cmp).toBe(">");
    expect(evalGraphExpr(above!.node, 2)).toBe(4);
    expect(parseGraphRelation("y <= 2x")?.cmp).toBe("<=");
    expect(parseGraphRelation("y ≥ 2x")?.cmp).toBe(">=");
    expect(parseGraphRelation("x^2")?.cmp).toBe("=");
  });

  it("seeds the editor with a full relation so = can become <", () => {
    expect(formatSeriesExpr("x**2")).toBe("y = x^2");
    expect(formatSeriesExpr("y < 2x")).toBe("y < 2x");
    expect(formatSeriesExpr("4x^2-5x-12=0")).toBe("y = 4x^2-5x-12");
    expect(formatSeriesExpr("x^2 + y^2 = 1")).toBe("x^2 + y^2 = 1");
  });

  it("closes an inequality fill against the matching y edge", () => {
    const curve: [number, number][] = [
      [0, 0],
      [2, 4],
    ];
    expect(inequalityFillPoints(curve, -3, 5, "<")).toEqual([
      [0, 0],
      [2, 4],
      [2, -3],
      [0, -3],
    ]);
    expect(inequalityFillPoints(curve, -3, 5, ">")).toEqual([
      [0, 0],
      [2, 4],
      [2, 5],
      [0, 5],
    ]);
    expect(inequalityFillPoints(curve, -3, 5, "=")).toEqual([]);
  });
});
