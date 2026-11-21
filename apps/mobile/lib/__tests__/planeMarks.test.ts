import { arrowHead, pointLabelAt, rightAngleSquare, segmentLabelAt, tickStrokes } from "@/lib/math/planeMarks";

const FRAME = { width: 300, height: 300, pad: 16 };

describe("marks on a coordinate plane", () => {
  it("crosses a segment's middle with one stroke per tick, square to it", () => {
    const strokes = tickStrokes({ px: 0, py: 0 }, { px: 100, py: 0 }, 2);
    expect(strokes).toHaveLength(2);
    for (const [a, b] of strokes) {
      expect(a.px).toBeCloseTo(b.px);
      expect(Math.abs(a.py - b.py)).toBeCloseTo(8);
    }
    expect(strokes.map(([a]) => a.px).sort((x, y) => x - y)).toEqual([48, 52]);
    expect(tickStrokes({ px: 1, py: 1 }, { px: 1, py: 1 }, 1)).toEqual([]);
  });

  it("draws a right angle's square along both arms", () => {
    const square = rightAngleSquare({ px: 10, py: 10 }, { px: 50, py: 10 }, { px: 10, py: -30 });
    expect(square).toEqual([
      { px: 19, py: 10 },
      { px: 19, py: 1 },
      { px: 10, py: 1 },
    ]);
  });

  it("points an arrowhead the way its segment runs", () => {
    const [tip, one, two] = arrowHead({ px: 0, py: 0 }, { px: 0, py: 40 });
    expect(tip).toEqual({ px: 0, py: 40 });
    expect(one.py).toBeCloseTo(32);
    expect(two.py).toBeCloseTo(32);
    expect(one.px).toBeCloseTo(-two.px);
  });

  it("puts a label on its side, and back inside the plane at an edge", () => {
    expect(pointLabelAt({ px: 100, py: 100 }, "sw", 40, FRAME)).toEqual({ x: 94, y: 114, anchor: "end" });
    expect(pointLabelAt({ px: 280, py: 100 }, "ne", 40, FRAME)).toEqual({ x: 274, y: 94, anchor: "end" });
    expect(pointLabelAt({ px: 20, py: 100 }, "nw", 40, FRAME)).toEqual({ x: 26, y: 94, anchor: "start" });
    expect(pointLabelAt({ px: 100, py: 5 }, "ne", 40, FRAME).y).toBe(19);
  });

  it("sets a segment's label off away from the figure's middle", () => {
    const below = segmentLabelAt({ px: 0, py: 100 }, { px: 100, py: 100 }, { px: 50, py: 50 });
    expect(below.py).toBeGreaterThan(100);
    const right = segmentLabelAt({ px: 100, py: 0 }, { px: 100, py: 100 }, { px: 50, py: 50 });
    expect(right.px).toBeGreaterThan(100);
  });
});
