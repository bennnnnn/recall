import {
  computeCircleLabels,
  computeRectangleLabels,
  computeRightTriangleLabels,
  computeTriangleLabels,
  parseGeometrySpec,
  rectangleAngleDisplay,
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

  it("rejects dimensions above backend max", () => {
    expect(parseGeometrySpec('{"type":"square","side":2000000}')).toBeNull();
    expect(parseGeometrySpec('{"type":"triangle","base":2000000,"height":5}')).toBeNull();
  });

  it("BUG FIX regression: parses a circle spec (circles were previously unsupported entirely)", () => {
    // Circles were never a recognized geometry type — a model-emitted
    // ```geometry {"type":"circle",...} fence failed backend validation
    // and rendered as a raw "[!WARNING] Invalid geometry block" message
    // instead of a diagram.
    const spec = parseGeometrySpec(
      '{"type":"circle","radius":4,"unit":"cm","show_diameter":true,"show_area":true,"show_circumference":true}',
    );
    expect(spec?.type).toBe("circle");
    if (spec?.type !== "circle") return;
    expect(spec.radius).toBe(4);
    expect(spec.show_diameter).toBe(true);
  });

  it("computes circle labels (radius, diameter, area, circumference)", () => {
    const spec = parseGeometrySpec('{"type":"circle","radius":4}');
    expect(spec?.type).toBe("circle");
    if (spec?.type !== "circle") return;
    const labels = computeCircleLabels(spec);
    expect(labels.diameter).toContain("8");
    expect(labels.area).toContain((Math.PI * 16).toFixed(2));
    expect(labels.circumference).toContain((8 * Math.PI).toFixed(2));
  });

  it("rejects a circle with a non-positive or oversized radius", () => {
    expect(parseGeometrySpec('{"type":"circle","radius":0}')).toBeNull();
    expect(parseGeometrySpec('{"type":"circle","radius":2000000}')).toBeNull();
  });

  describe("rectangleAngleDisplay", () => {
    it("BUG FIX regression: never shows the 90° corner bracket alongside the diagonal's (non-90°) angle label", () => {
      // A rectangle's corners are always 90° — the bracket glyph means
      // that. The diagonal-vs-base angle is a different, generally
      // non-90° number, so drawing both at once reads as a contradiction
      // (a "this is 90°" glyph right next to e.g. "51.3°").
      const result = rectangleAngleDisplay({
        type: "rectangle",
        show_angle: true,
        show_diagonal: true,
      });
      expect(result.showCornerBracket).toBe(false);
      expect(result.showDiagonalAngleLabel).toBe(true);
    });

    it("shows the plain corner bracket (no angle number) when angle is requested without a diagonal", () => {
      const result = rectangleAngleDisplay({
        type: "rectangle",
        show_angle: true,
        show_diagonal: false,
      });
      expect(result.showCornerBracket).toBe(true);
      expect(result.showDiagonalAngleLabel).toBe(false);
    });

    it("shows neither when nothing was requested", () => {
      const result = rectangleAngleDisplay({ type: "rectangle" });
      expect(result.showCornerBracket).toBe(false);
      expect(result.showDiagonalAngleLabel).toBe(false);
    });

    it("always shows both corner brackets for a square regardless of angle/diagonal flags", () => {
      const result = rectangleAngleDisplay({ type: "square" });
      expect(result.showCornerBracket).toBe(true);
      expect(result.showDiagonalAngleLabel).toBe(false);
    });
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

  it("BUG FIX regression: accepts a single point (e.g. marking a specific coordinate)", () => {
    // Requiring 2+ points made sense for a function curve but not for
    // "plot the point (2, 3)" — a single point by definition. This used
    // to fail parsing entirely and fall back to "Could not render".
    const spec = parseGraphSpec('{"type":"function","expr":"(2, 3)","points":[[2,3]]}');
    expect(spec?.points).toEqual([[2, 3]]);
  });

  it("rejects an empty points array", () => {
    expect(parseGraphSpec('{"type":"function","expr":"x","points":[]}')).toBeNull();
  });

  it("BUG FIX regression: centers a single point instead of gluing it to the chart edge", () => {
    // A single point collapses both axes' ranges to zero. Without
    // symmetric padding (matching the existing yMin===yMax handling),
    // the point would render flush at the left/bottom edge.
    const bounds = graphBounds([[2, 3]]);
    expect(bounds).toEqual({ xMin: 1, xMax: 3, yMin: 2, yMax: 4 });
  });

  it("rejects too many points or long expr", () => {
    const tooMany = Array.from({ length: 301 }, (_, i) => [i, i] as [number, number]);
    expect(
      parseGraphSpec(
        JSON.stringify({ type: "function", expr: "x", points: tooMany }),
      ),
    ).toBeNull();
    expect(
      parseGraphSpec(
        JSON.stringify({
          type: "function",
          expr: "x".repeat(257),
          points: [
            [0, 0],
            [1, 1],
          ],
        }),
      ),
    ).toBeNull();
  });
});
