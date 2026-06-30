import {
  computeRectangleLabels,
  computeRightTriangleLabels,
  computeTriangleLabels,
  parseGeometrySpec,
  scaleToFit,
} from "@/lib/geometryBlock";
import { graphBounds, graphPolylinePoints, parseGraphSpec } from "@/lib/graphBlock";

describe("geometryBlock", () => {
  it("parses square spec from side", () => {
    const spec = parseGeometrySpec('{"type":"square","side":5,"unit":"cm","show_area":true}');
    expect(spec?.type).toBe("square");
    if (spec?.type === "square" || spec?.type === "rectangle") {
      expect(spec.width).toBe(5);
      expect(spec.height).toBe(5);
    }
  });

  it("parses rect alias with length and breadth", () => {
    const spec = parseGeometrySpec('{"type":"rect","length":8,"breadth":5,"unit":"cm"}');
    expect(spec?.type).toBe("rectangle");
    if (spec?.type === "rectangle" || spec?.type === "square") {
      expect(spec.width).toBe(8);
      expect(spec.height).toBe(5);
    }
  });

  it("parses right triangle spec", () => {
    const spec = parseGeometrySpec(
      '{"type":"right_triangle","base":6,"height":4,"unit":"cm","show_hypotenuse":true,"show_angle":true}',
    );
    expect(spec?.type).toBe("right_triangle");
    if (spec?.type === "right_triangle") {
      expect(spec.base).toBe(6);
      expect(spec.height).toBe(4);
    }
  });

  it("computes right triangle labels", () => {
    const spec = parseGeometrySpec('{"type":"right_triangle","base":6,"height":4}');
    expect(spec?.type).toBe("right_triangle");
    if (spec?.type === "right_triangle") {
      const labels = computeRightTriangleLabels(spec);
      expect(labels.hypotenuse).toContain("7.21");
      expect(labels.area).toContain("12");
    }
  });

  it("parses triangle spec", () => {
    const spec = parseGeometrySpec(
      '{"type":"triangle","base":8,"height":5,"unit":"cm","show_labels":true}',
    );
    expect(spec?.type).toBe("triangle");
    if (spec?.type === "triangle") {
      expect(spec.base).toBe(8);
      expect(spec.height).toBe(5);
    }
  });

  it("computes triangle labels", () => {
    const spec = parseGeometrySpec('{"type":"triangle","base":8,"height":5}');
    expect(spec?.type).toBe("triangle");
    if (spec?.type === "triangle") {
      const labels = computeTriangleLabels(spec);
      expect(labels.area).toContain("20");
    }
  });

  it("parses rectangle spec", () => {
    const spec = parseGeometrySpec(
      '{"type":"rectangle","width":8,"height":5,"unit":"cm","show_diagonal":true}',
    );
    expect(spec?.type).toBe("rectangle");
    if (spec?.type === "rectangle") {
      expect(spec.width).toBe(8);
      expect(spec.height).toBe(5);
    }
  });

  it("computes labels", () => {
    const spec = parseGeometrySpec('{"type":"rectangle","width":8,"height":5}');
    expect(spec?.type).toBe("rectangle");
    if (spec?.type !== "rectangle") return;
    const labels = computeRectangleLabels(spec);
    expect(labels.diagonal).toContain("9.43");
  });

  it("scales to fit width", () => {
    const scaled = scaleToFit(8, 5, 300);
    expect(scaled.w).toBeGreaterThan(0);
    expect(scaled.h).toBeGreaterThan(0);
  });
});

describe("graphBlock", () => {
  it("parses graph spec with points", () => {
    const spec = parseGraphSpec(
      '{"type":"function","expr":"x**2","points":[[-2,4],[0,0],[2,4]]}',
    );
    expect(spec?.expr).toBe("x**2");
    expect(spec?.points.length).toBe(3);
  });

  it("builds polyline points", () => {
    const points: [number, number][] = [
      [-2, 4],
      [0, 0],
      [2, 4],
    ];
    const poly = graphPolylinePoints(points, 200, 120);
    expect(poly).toContain(",");
    expect(graphBounds(points).yMax).toBe(4);
  });
});
