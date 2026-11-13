import { figureLayout, parseFigure } from "@/lib/math/geometryFigure";
import { geometryFigureLabel, parseGeometrySpec } from "@/lib/math/geometryBlock";
import { type FigureSpec } from "@/lib/math/geometryTypes";

/** The server's parallelogram for "angle A = 70°" (textbook run, 2026-11-13). */
const PARALLELOGRAM = {
  type: "figure",
  shape: "parallelogram",
  points: [
    { name: "A", x: 0, y: 0, show: true },
    { name: "B", x: 6, y: 0, show: true },
    { name: "C", x: 7.368, y: 3.759, show: true },
    { name: "D", x: 1.368, y: 3.759, show: true },
  ],
  segments: [
    { a: "A", b: "B", arrows: 1 },
    { a: "B", b: "C", arrows: 2 },
    { a: "C", b: "D", arrows: 1 },
    { a: "D", b: "A", arrows: 2 },
  ],
  angles: [{ at: "A", a: "B", b: "D", label: "70°" }],
  faces: [["A", "B", "C", "D"]],
};

/** A right triangle with legs 12 (along the bottom) and 9. */
const RIGHT_TRIANGLE = {
  type: "figure",
  shape: "right_triangle",
  points: [
    { name: "A", x: 0, y: 0 },
    { name: "B", x: 12, y: 0 },
    { name: "C", x: 0, y: 9 },
  ],
  segments: [
    { a: "A", b: "B", label: "12 cm" },
    { a: "B", b: "C" },
    { a: "C", b: "A", label: "9 cm" },
  ],
  angles: [{ at: "A", a: "B", b: "C", right: true }],
  faces: [["A", "B", "C"]],
};

function figure(raw: object): FigureSpec {
  const spec = parseFigure(raw as Record<string, unknown>);
  if (!spec) throw new Error("not a figure");
  return spec;
}

describe("a server-drawn figure", () => {
  it("is read as a geometry fence", () => {
    const spec = parseGeometrySpec(JSON.stringify(PARALLELOGRAM));
    expect(spec?.type).toBe("figure");
    expect(spec && geometryFigureLabel(spec)).toBe("A, B, C, D, 70°");
  });

  it.each([
    ["a side naming a point it lacks", { ...PARALLELOGRAM, segments: [{ a: "A", b: "Z" }] }],
    ["a point that is not a number", { ...PARALLELOGRAM, points: [{ name: "A", x: "1", y: 0 }] }],
    ["nothing to draw", { ...PARALLELOGRAM, segments: [], arcs: [] }],
    ["two points of one name", { ...PARALLELOGRAM, points: [...PARALLELOGRAM.points, { name: "A", x: 1, y: 1 }] }],
    ["an arc that ends before it starts", { ...PARALLELOGRAM, arcs: [{ center: "A", rx: 1, ry: 1, start: 90, end: 10 }] }],
  ])("refuses %s", (_name, raw) => {
    expect(parseFigure(raw as Record<string, unknown>)).toBeNull();
  });

  it("fits the card and keeps every label on it", () => {
    for (const width of [240, 312, 360]) {
      for (const raw of [PARALLELOGRAM, RIGHT_TRIANGLE]) {
        const layout = figureLayout(figure(raw), width);
        for (const line of layout.lines) {
          for (const end of [line.from, line.to]) {
            expect(end.x).toBeGreaterThanOrEqual(0);
            expect(end.x).toBeLessThanOrEqual(width);
            expect(end.y).toBeGreaterThanOrEqual(0);
            expect(end.y).toBeLessThanOrEqual(layout.height);
          }
        }
        for (const label of layout.labels) {
          const reach = label.text.length * 7;
          const left = label.anchor === "end" ? label.x - reach : label.anchor === "middle" ? label.x - reach / 2 : label.x;
          expect(left).toBeGreaterThanOrEqual(0);
          expect(left + reach).toBeLessThanOrEqual(width);
        }
      }
    }
  });

  it("puts a side's length outside the shape and an angle inside it", () => {
    const layout = figureLayout(figure(RIGHT_TRIANGLE), 320);
    const base = layout.labels.find((label) => label.text === "12 cm");
    const leg = layout.labels.find((label) => label.text === "9 cm");
    const bottom = Math.max(...layout.lines.map((line) => Math.max(line.from.y, line.to.y)));
    const left = Math.min(...layout.lines.map((line) => Math.min(line.from.x, line.to.x)));
    expect(base && base.y).toBeGreaterThan(bottom);
    expect(leg && leg.x).toBeLessThan(left);
    expect(leg?.anchor).toBe("end");
    const angle = figureLayout(figure(PARALLELOGRAM), 320).labels.find((label) => label.text === "70°");
    const a = figureLayout(figure(PARALLELOGRAM), 320).labels.find((label) => label.text === "A");
    expect(angle && a && angle.x > a.x && angle.y < a.y).toBe(true);
  });

  it("marks a right angle with a square and parallel sides with arrowheads", () => {
    expect(figureLayout(figure(RIGHT_TRIANGLE), 320).angleArcs[0]).toHaveLength(3);
    // Four sides, one or two arrowheads each, two strokes per arrowhead.
    expect(figureLayout(figure(PARALLELOGRAM), 320).marks).toHaveLength(12);
  });

  it("labels a diagonal three quarters along when the server says so", () => {
    const raw = {
      ...RIGHT_TRIANGLE,
      segments: [...RIGHT_TRIANGLE.segments.slice(0, 2), { a: "C", b: "A", label: "9 cm", label_at: 0.75 }],
    };
    const near = figureLayout(figure(raw), 320).labels.find((label) => label.text === "9 cm");
    const middle = figureLayout(figure(RIGHT_TRIANGLE), 320).labels.find((label) => label.text === "9 cm");
    expect(near && middle && near.y > middle.y).toBe(true);
  });

  it("draws a circle as an arc round its centre", () => {
    const circle = figure({
      type: "figure",
      shape: "circle_chord",
      points: [{ name: "O", x: 0, y: 0, dot: true, show: true }, { name: "_1", x: 3, y: 0 }],
      segments: [{ a: "O", b: "_1", label: "3 cm" }],
      arcs: [{ center: "O", rx: 3, ry: 3 }],
    });
    const layout = figureLayout(circle, 300);
    const [arc] = layout.arcs;
    const xs = arc.points.map((p) => p.x);
    const ys = arc.points.map((p) => p.y);
    // Round on the screen: as wide as it is tall.
    expect(Math.max(...xs) - Math.min(...xs)).toBeCloseTo(Math.max(...ys) - Math.min(...ys), 0);
    expect(layout.dots).toHaveLength(1);
  });
});
