import {
  computeCircleLabels,
  computeRectangleLabels,
  computeRightTriangleLabels,
  computeTriangleLabels,
  equalSideTickCounts,
  footOfPerpendicular,
  formatAngleDeg,
  isRightAngleDeg,
  estimateAngleLabelSize,
  padDiagramForAngleLabels,
  polygonInteriorAngleMarks,
  isIsoscelesSides,
  midpoint,
  parseGeometrySpec,
  diagonalAngleArcPath,
  rectangleAngleDisplay,
  scaleToFit,
  sideTickMarks,
  parallelogramLayout,
  baseHeightTriangleVertices,
} from "@/lib/geometryBlock";
import {
  expandBoundsForAxes,
  formatGraphExpr,
  formatInequalityExpr,
  graphBounds,
  graphPolylinePoints,
  numberLineBounds,
  numberLineTicks,
  parseGraphSpec,
} from "@/lib/graphBlock";

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
      expect(labels.angle).toBe("90°");
      expect(labels.angle_at_base).toContain("33.7");
      expect(labels.angle_at_height).toContain("56.3");
    }
  });

  it("labels every interior vertex of a 3-4-5 right triangle", () => {
    expect(formatAngleDeg(90)).toBe("90°");
    expect(formatAngleDeg(36.869897)).toBe("36.9°");
    const marks = polygonInteriorAngleMarks([
      { x: 0, y: 40 },
      { x: 30, y: 40 },
      { x: 0, y: 0 },
    ]);
    const degs = marks.map((m) => Math.round(m.deg)).sort((a, b) => a - b);
    expect(degs).toEqual([37, 53, 90]);
    expect(marks.some((m) => isRightAngleDeg(m.deg))).toBe(true);
  });

  it("sizes 60.5° labels so the decimal and degree sign fit a backdrop", () => {
    const size = estimateAngleLabelSize("60.5°");
    expect(size.width).toBeGreaterThan(40);
    expect(size.height).toBeGreaterThanOrEqual(18);
  });

  it("places acute degree labels farther in than the arc so they clear the sides", () => {
    const vertices = [
      { x: 0, y: 160 },
      { x: 120, y: 160 },
      { x: 0, y: 0 },
    ];
    const marks = polygonInteriorAngleMarks(vertices);
    const acute = marks.filter((m) => !isRightAngleDeg(m.deg));
    expect(acute.length).toBe(2);
    marks.forEach((mark, i) => {
      if (isRightAngleDeg(mark.deg)) return;
      const b = vertices[i];
      const dist = Math.hypot(mark.labelX - b.x, mark.labelY - b.y);
      expect(dist).toBeGreaterThan(16 + 12);
      expect(mark.labelWidth).toBeGreaterThan(24);
      expect(mark.leader).toBeNull();
    });
  });

  it("puts 10° and 90° outside a skinny right triangle with leader lines", () => {
    const vertices = [
      { x: 0, y: 200 },
      { x: 20, y: 200 },
      { x: 0, y: 0 },
    ];
    const marks = polygonInteriorAngleMarks(vertices);
    const tight = marks.filter((m) => Math.round(m.deg) <= 12 || isRightAngleDeg(m.deg));
    expect(tight.length).toBeGreaterThanOrEqual(2);
    for (const mark of tight) {
      expect(mark.leader).not.toBeNull();
      const inBox =
        mark.labelX >= 2 && mark.labelX <= 18 && mark.labelY >= 2 && mark.labelY <= 198;
      expect(inBox).toBe(false);
    }
    const padded = padDiagramForAngleLabels(vertices, 20, 200);
    expect(padded.svgW).toBeGreaterThan(20);
    expect(padded.svgH).toBeGreaterThan(200);
  });

  it("parses triangle spec", () => {
    const spec = parseGeometrySpec(
      '{"type":"triangle","base":8,"height":5,"unit":"cm","show_labels":true}',
    );
    expect(spec?.type).toBe("triangle");
    if (spec?.type === "triangle") {
      expect(spec.base).toBe(8);
      expect(spec.height).toBe(5);
      expect(spec.show_labels).toBe(true);
    }
  });

  it("BUG FIX regression: copies show_labels false so the renderer can hide labels", () => {
    const spec = parseGeometrySpec(
      '{"type":"triangle","base":8,"height":5,"show_labels":false}',
    );
    expect(spec?.type).toBe("triangle");
    if (spec?.type === "triangle") {
      expect(spec.show_labels).toBe(false);
    }
    const right = parseGeometrySpec(
      '{"type":"right_triangle","base":3,"height":4,"show_hypotenuse":false,"show_angle":false}',
    );
    expect(right?.type).toBe("right_triangle");
    if (right?.type === "right_triangle") {
      expect(right.show_hypotenuse).toBe(false);
      expect(right.show_angle).toBe(false);
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

  it("BUG FIX regression: base+height vertices are not isosceles", () => {
    const v = baseHeightTriangleVertices(8, 5);
    expect(v.x2).not.toBeCloseTo((v.x0 + v.x1) / 2);
    expect(v.x2).toBeCloseTo(2);
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

  it("fits a parallelogram inside the bubble — does not double-count shear", () => {
    const bubble = 390 - 32;
    for (const spec of [
      { base: 8, height: 5, side: 6 },
      { base: 10, height: 6, side: 7 },
      { base: 6, height: 3, side: 5 },
    ]) {
      const layout = parallelogramLayout(spec, 390);
      expect(layout.tx0).toBeCloseTo(40);
      expect(layout.bx1).toBeCloseTo(layout.svgW - 40);
      expect(layout.svgW).toBeCloseTo(layout.b + layout.shear + 80);
      const doubled = layout.b + layout.shear + layout.offsetX + 40;
      expect(layout.svgW).toBeLessThan(doubled);
      expect(layout.svgW).toBeLessThanOrEqual(bubble);
    }
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

  describe("diagonalAngleArcPath", () => {
    it("emits an SVG arc from the top edge toward the TL→BR diagonal", () => {
      const d = diagonalAngleArcPath(10, 20, 80, 60, 18);
      expect(d.startsWith("M ")).toBe(true);
      expect(d).toContain(" A ");
      // Start sits on the top edge (y = originY).
      expect(d).toMatch(/^M [\d.]+ 20 /);
      // End y is below the top (positive SVG y).
      const endY = Number(d.trim().split(/\s+/).pop());
      expect(endY).toBeGreaterThan(20);
    });
  });

  describe("tick / altitude helpers", () => {
    it("assigns matching tick counts to equal sides", () => {
      expect(equalSideTickCounts(5, 5, 6)).toEqual({ a: 1, b: 1, c: 0 });
      expect(equalSideTickCounts(3, 4, 5)).toEqual({ a: 0, b: 0, c: 0 });
      expect(equalSideTickCounts(5, 5, 5)).toEqual({ a: 1, b: 1, c: 1 });
    });

    it("builds perpendicular tick segments at the side midpoint", () => {
      const marks = sideTickMarks(0, 0, 10, 0, 1, 5);
      expect(marks).toHaveLength(1);
      expect(marks[0]?.x1).toBeCloseTo(5);
      expect(marks[0]?.x2).toBeCloseTo(5);
      expect(Math.abs((marks[0]?.y2 ?? 0) - (marks[0]?.y1 ?? 0))).toBeCloseTo(10);
    });

    it("computes the altitude foot and median midpoint", () => {
      const foot = footOfPerpendicular(0, 0, 6, 0, 3, 4);
      expect(foot.x).toBeCloseTo(3);
      expect(foot.y).toBeCloseTo(0);
      const mid = midpoint(0, 0, 6, 0);
      expect(mid).toEqual({ x: 3, y: 0 });
      expect(isIsoscelesSides(5, 5, 6)).toBe(true);
      expect(isIsoscelesSides(3, 4, 5)).toBe(false);
    });

    it("parses show_ticks / show_altitude / show_median on triangle_sides", () => {
      const spec = parseGeometrySpec(
        JSON.stringify({
          type: "triangle_sides",
          a: 5,
          b: 5,
          c: 6,
          show_ticks: true,
          show_altitude: true,
          show_median: true,
        }),
      );
      expect(spec?.type).toBe("triangle_sides");
      if (spec?.type !== "triangle_sides") return;
      expect(spec.show_ticks).toBe(true);
      expect(spec.show_altitude).toBe(true);
      expect(spec.show_median).toBe(true);
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

  it("BUG FIX regression: parses type=vertical fences (x = c)", () => {
    const spec = parseGraphSpec(
      JSON.stringify({
        type: "vertical",
        x: 4,
        y_min: -5,
        y_max: 5,
        title: "x = 4",
      }),
    );
    expect(spec?.type).toBe("vertical");
    expect(spec?.x).toBe(4);
    expect(spec?.points).toEqual([
      [4, -5],
      [4, 5],
    ]);
  });

  it("parses a number_line fence for x > 3", () => {
    const spec = parseGraphSpec(
      JSON.stringify({
        type: "number_line",
        expr: "x > 3",
        title: "x > 3",
        intervals: [{ start: 3, end: null, start_inclusive: false, end_inclusive: false }],
      }),
    );
    expect(spec?.type).toBe("number_line");
    expect(spec?.intervals).toEqual([
      { start: 3, end: null, start_inclusive: false, end_inclusive: false },
    ]);
  });

  it("pretty-prints inequality titles", () => {
    expect(formatInequalityExpr("x >= 3")).toBe("x ≥ 3");
    expect(formatInequalityExpr("1 <= x < 5")).toBe("1 ≤ x < 5");
  });

  it("pads number-line bounds so the axis continues through negatives", () => {
    const bounds = numberLineBounds([
      { start: 3, end: null, start_inclusive: false, end_inclusive: false },
    ]);
    expect(bounds.xMin).toBeLessThan(0);
    expect(bounds.xMax).toBeGreaterThan(3);
    const ticks = numberLineTicks(bounds.xMin, bounds.xMax);
    expect(ticks).toEqual(expect.arrayContaining([-1, 0, 1, 2, 3]));
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

  it("BUG FIX regression: downsamples oversized point dumps instead of rejecting them", () => {
    const points = Array.from({ length: 600 }, (_, i) => [i / 10, (i / 10) ** 2]);
    const spec = parseGraphSpec(
      JSON.stringify({ type: "function", expr: "x**2", points }),
    );
    expect(spec).not.toBeNull();
    expect(spec!.points.length).toBe(500);
    expect(spec!.points[0]).toEqual([0, 0]);
    expect(spec!.points[spec!.points.length - 1][0]).toBeCloseTo(59.9, 5);
  });

  it("BUG FIX regression: centers a single point instead of gluing it to the chart edge", () => {
    // A single point collapses both axes' ranges to zero. Without
    // symmetric padding (matching the existing yMin===yMax handling),
    // the point would render flush at the left/bottom edge.
    const bounds = graphBounds([[2, 3]]);
    expect(bounds).toEqual({ xMin: 1, xMax: 3, yMin: 2, yMax: 4 });
  });

  it("BUG FIX regression: parses segments split at a discontinuity (e.g. tan(x) asymptote)", () => {
    const spec = parseGraphSpec(
      JSON.stringify({
        type: "function",
        expr: "tan(x)",
        points: [
          [0, 0],
          [1, 1.5],
          [2, -2.2],
        ],
        segments: [
          [
            [0, 0],
            [1, 1.5],
          ],
          [[2, -2.2]],
        ],
      }),
    );
    expect(spec?.segments).toEqual([
      [
        [0, 0],
        [1, 1.5],
      ],
      [[2, -2.2]],
    ]);
  });

  it("leaves segments undefined when absent (the common, no-discontinuity case)", () => {
    const spec = parseGraphSpec('{"type":"function","expr":"x**2","points":[[-2,4],[0,0],[2,4]]}');
    expect(spec?.segments).toBeUndefined();
  });

  it("ignores a malformed or single-piece segments field and falls back to plain points rendering", () => {
    // A single "segment" carries no gap information beyond `points` itself
    // — treat it the same as absent so the caller renders one continuous
    // polyline instead of needlessly branching into segment-rendering.
    const singlePiece = parseGraphSpec(
      JSON.stringify({
        type: "function",
        expr: "x",
        points: [
          [0, 0],
          [1, 1],
        ],
        segments: [
          [
            [0, 0],
            [1, 1],
          ],
        ],
      }),
    );
    expect(singlePiece?.segments).toBeUndefined();

    const malformed = parseGraphSpec(
      JSON.stringify({
        type: "function",
        expr: "x",
        points: [
          [0, 0],
          [1, 1],
        ],
        segments: "not-an-array",
      }),
    );
    expect(malformed?.segments).toBeUndefined();
  });

  it("BUG FIX regression: graphPolylinePoints maps segment points against shared, precomputed bounds", () => {
    // Rendering multiple segments of the same curve must use ONE shared
    // bounds object (computed from every point), not per-segment bounds —
    // otherwise each segment gets independently rescaled and the pieces no
    // longer line up on a common axis.
    const allPoints: [number, number][] = [
      [0, 0],
      [10, 100],
    ];
    const sharedBounds = graphBounds(allPoints);
    const segment: [number, number][] = [[0, 0]];
    const withSharedBounds = graphPolylinePoints(segment, 200, 120, sharedBounds);
    const withOwnBounds = graphPolylinePoints(segment, 200, 120);
    // A lone point at the origin maps to different screen coordinates
    // depending on whether it's scaled against the full [0,100] y-range
    // (shared bounds) or its own degenerate [-1,1] range (own bounds).
    expect(withSharedBounds).not.toBe(withOwnBounds);
  });

  it("downsamples oversized points and rejects overlong expr", () => {
    const tooMany = Array.from({ length: 301 }, (_, i) => [i, i] as [number, number]);
    const dense = parseGraphSpec(
      JSON.stringify({ type: "function", expr: "x", points: tooMany }),
    );
    expect(dense?.points.length).toBe(301);
    const huge = Array.from({ length: 600 }, (_, i) => [i, i] as [number, number]);
    expect(
      parseGraphSpec(JSON.stringify({ type: "function", expr: "x", points: huge }))
        ?.points.length,
    ).toBe(500);
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

  it("parses a second curve (expr2/points2/label2) for a comparison plot", () => {
    const spec = parseGraphSpec(
      JSON.stringify({
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
      }),
    );
    expect(spec?.expr2).toBe("2*x");
    expect(spec?.points2).toEqual([
      [-2, -4],
      [2, 4],
    ]);
    expect(spec?.label).toBe("y = x^2");
    expect(spec?.label2).toBe("y = 2x");
  });

  it("treats an incomplete second curve (expr2 with no points2) as single-curve", () => {
    const spec = parseGraphSpec(
      JSON.stringify({
        type: "function",
        expr: "x**2",
        points: [
          [0, 0],
          [1, 1],
        ],
        expr2: "2*x",
      }),
    );
    expect(spec?.expr2).toBeUndefined();
    expect(spec?.points2).toBeUndefined();
  });

  it("graphBounds folds a second point set into the same shared min/max", () => {
    const bounds = graphBounds(
      [
        [-2, 4],
        [2, 4],
      ],
      [
        [-2, -4],
        [2, 4],
      ],
    );
    expect(bounds.yMin).toBe(-4);
    expect(bounds.yMax).toBe(4);
  });

  it("formatGraphExpr turns SymPy powers into readable math", () => {
    expect(formatGraphExpr("3*x**2 - 12")).toBe("3x² - 12");
    expect(formatGraphExpr("x**2")).toBe("x²");
    expect(formatGraphExpr("2*sin(x)")).toBe("2sin(x)");
    expect(formatGraphExpr("x**2/9 + y**2/4 = 1")).toBe("x²/9 + y²/4 = 1");
    expect(formatGraphExpr("y = 3*x**2")).toBe("y = 3x²");
  });

  it("composes formatGraphExpr then formatInequalityExpr for inequality titles", () => {
    expect(formatInequalityExpr(formatGraphExpr("3*x - 6 >= 0"))).toBe("3x - 6 ≥ 0");
  });

  it("expandBoundsForAxes includes the origin so axes are not the data min", () => {
    const tight = graphBounds([
      [-2, 0],
      [0, -12],
      [2, 0],
    ]);
    expect(tight).toEqual({ xMin: -2, xMax: 2, yMin: -12, yMax: 0 });
    const view = expandBoundsForAxes(tight);
    expect(view.xMin).toBeLessThan(0);
    expect(view.xMax).toBeGreaterThan(0);
    expect(view.yMin).toBeLessThan(-12);
    expect(view.yMax).toBeGreaterThan(0);
  });

  it("expandBoundsForAxes rounds to clean integers (no -1.8 / 9.8 / 11.6 labels)", () => {
    // x=4 vertical line: data bounds x:[-1,9], y:[-10,10] (after the ±5 default
    // spread). The 8% pad would yield -1.8/9.8/±11.6 — round outwards instead.
    const tight = graphBounds([
      [-1, -10],
      [9, 10],
    ]);
    const view = expandBoundsForAxes(tight);
    expect(Number.isInteger(view.xMin)).toBe(true);
    expect(Number.isInteger(view.xMax)).toBe(true);
    expect(Number.isInteger(view.yMin)).toBe(true);
    expect(Number.isInteger(view.yMax)).toBe(true);
    expect(view.xMin).toBe(-2);
    expect(view.xMax).toBe(10);
    expect(view.yMin).toBe(-12);
    expect(view.yMax).toBe(12);
  });
});
