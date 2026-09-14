import {
  trajectoryPathLength,
  trajectoryPointAt,
  type ScreenPoint,
} from "@/lib/math/trajectory";

/** Three points on a right angle: (0,0) → (10,0) → (10,10). Length 20. */
const L_SHAPE: ScreenPoint[] = [
  { px: 0, py: 0 },
  { px: 10, py: 0 },
  { px: 10, py: 10 },
];

describe("trajectoryPointAt", () => {
  it("returns the first point at 0 and the last at 1", () => {
    expect(trajectoryPointAt(L_SHAPE, 0)).toEqual({ px: 0, py: 0 });
    expect(trajectoryPointAt(L_SHAPE, 1)).toEqual({ px: 10, py: 10 });
  });

  it("lands exactly on an interior sample at its own fraction", () => {
    // Index is the clock, so the midpoint of progress is the middle sample —
    // not the halfway point by distance.
    expect(trajectoryPointAt(L_SHAPE, 0.5)).toEqual({ px: 10, py: 0 });
  });

  it("interpolates between neighbouring samples", () => {
    expect(trajectoryPointAt(L_SHAPE, 0.25)).toEqual({ px: 5, py: 0 });
    expect(trajectoryPointAt(L_SHAPE, 0.75)).toEqual({ px: 10, py: 5 });
  });

  it("advances by index, not by distance", () => {
    // Deliberately uneven spacing: a long first leg, a short second one. Equal
    // progress steps must still take equal *index* steps, because the solver
    // sampled at uniform time. Distance-based easing would be wrong physics.
    const uneven: ScreenPoint[] = [
      { px: 0, py: 0 },
      { px: 100, py: 0 },
      { px: 101, py: 0 },
    ];
    expect(trajectoryPointAt(uneven, 0.5)).toEqual({ px: 100, py: 0 });
  });

  it("clamps out-of-range progress instead of reading past the array", () => {
    // A timing callback or an interrupted animation can overshoot; an
    // unclamped index would read undefined and render the dot at NaN.
    expect(trajectoryPointAt(L_SHAPE, 1.4)).toEqual({ px: 10, py: 10 });
    expect(trajectoryPointAt(L_SHAPE, -0.3)).toEqual({ px: 0, py: 0 });
  });

  it("survives degenerate inputs", () => {
    expect(trajectoryPointAt([], 0.5)).toEqual({ px: 0, py: 0 });
    expect(trajectoryPointAt([{ px: 3, py: 4 }], 0.5)).toEqual({ px: 3, py: 4 });
  });
});

describe("trajectoryPathLength", () => {
  it("sums the segment lengths", () => {
    expect(trajectoryPathLength(L_SHAPE)).toBe(20);
  });

  it("is zero for fewer than two points", () => {
    expect(trajectoryPathLength([])).toBe(0);
    expect(trajectoryPathLength([{ px: 5, py: 5 }])).toBe(0);
  });
});
