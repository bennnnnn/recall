import { graphAxisTicks, graphTickCount } from "@/lib/math/graphBlock";
import {
  clampGraphView,
  defaultInteractiveBounds,
  panGraphView,
  zoomGraphView,
} from "@/lib/math/graphViewport";
import {
  axisTicksW,
  clampGraphViewW,
  formatShortW,
  formatTickW,
  mapPointW,
  nearestSampleW,
  panGraphViewW,
  unmapPointW,
  zoomGraphViewW,
} from "@/lib/math/graphWorklets";

// The worklet copies power the Skia explorer on the UI thread; these tests
// pin parity with the JS originals so the two explorers never disagree.
describe("graphWorklets parity", () => {
  it("zoom matches zoomGraphView", () => {
    const start = defaultInteractiveBounds(1.75);
    expect(zoomGraphViewW(start, 2.5, 1, 1)).toEqual(zoomGraphView(start, 2.5, 1, 1));
    expect(zoomGraphViewW(start, 0.4, -2, 3)).toEqual(zoomGraphView(start, 0.4, -2, 3));
  });

  it("pan matches panGraphView", () => {
    const start = defaultInteractiveBounds(1.75);
    expect(panGraphViewW(start, 40, -25, 360, 220, 28)).toEqual(
      panGraphView(start, 40, -25, 360, 220, 28),
    );
  });

  it("clamp falls back on a degenerate window", () => {
    const bad = { xMin: 2, xMax: 2, yMin: 0, yMax: 1 };
    const expected = clampGraphView(bad);
    const got = clampGraphViewW(bad);
    expect(got.xMax - got.xMin).toBeCloseTo(expected.xMax - expected.xMin);
    expect(got.yMax - got.yMin).toBeCloseTo(expected.yMax - expected.yMin);
  });

  it("ticks match graphAxisTicks on an integer window", () => {
    const view = defaultInteractiveBounds(1.75);
    expect(axisTicksW(view.xMin, view.xMax)).toEqual(
      graphAxisTicks(view.xMin, view.xMax, graphTickCount(view.xMin, view.xMax), true),
    );
  });

  it("map/unmap round-trips", () => {
    const b = { xMin: -6, xMax: 6, yMin: -4, yMax: 4 };
    const { px, py } = mapPointW(2.5, -1.5, b, 360, 220, 28);
    const back = unmapPointW(px, py, b, 360, 220, 28);
    expect(back.x).toBeCloseTo(2.5);
    expect(back.y).toBeCloseTo(-1.5);
  });
});

describe("nearestSampleW", () => {
  it("snaps to the closest sampled x and skips non-finite points", () => {
    const points: [number, number][] = [
      [0, 0],
      [Number.NaN, 5],
      [1.9, 3.61],
      [2.1, 4.41],
      [4, 16],
    ];
    const snap = nearestSampleW(points, 2.05);
    expect(snap).toEqual({ x: 2.1, y: 4.41, index: 3 });
  });

  it("returns null for an empty series", () => {
    expect(nearestSampleW([], 1)).toBeNull();
  });
});

describe("worklet tick formatting", () => {
  it("formatTickW keeps integers short and fractions precise", () => {
    expect(formatTickW(3)).toBe("3");
    expect(formatTickW(-0)).toBe("0");
    expect(formatTickW(0.5)).toBe("0.5");
  });

  it("formatShortW caps at two decimals for the trace callout", () => {
    expect(formatShortW(6.25)).toBe("6.25");
    expect(formatShortW(2.567)).toBe("2.57");
    expect(formatShortW(3)).toBe("3");
    expect(formatShortW(-0)).toBe("0");
  });
});
