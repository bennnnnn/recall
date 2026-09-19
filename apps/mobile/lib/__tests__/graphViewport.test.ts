import { graphAxisTicks, graphTickCount } from "@/lib/math/graphBlock";
import {
  defaultInteractiveBounds,
  expandGraphView,
  panGraphView,
  zoomGraphView,
} from "@/lib/math/graphViewport";

describe("interactive graph viewport", () => {
  it("starts with unit ticks including −3…3", () => {
    const view = defaultInteractiveBounds(1.75);
    const xTicks = graphAxisTicks(
      view.xMin,
      view.xMax,
      graphTickCount(view.xMin, view.xMax),
      true,
    );
    const yTicks = graphAxisTicks(
      view.yMin,
      view.yMax,
      graphTickCount(view.yMin, view.yMax),
      true,
    );
    expect(xTicks).toEqual(expect.arrayContaining([-3, -2, -1, 0, 1, 2, 3]));
    expect(yTicks).toEqual(expect.arrayContaining([-3, -2, -1, 0, 1, 2, 3]));
  });

  it("zooms in around the origin so tick spacing shrinks", () => {
    const start = defaultInteractiveBounds(1.75);
    const zoomed = zoomGraphView(start, 4, 0, 0);
    expect(zoomed.xMax - zoomed.xMin).toBeCloseTo((start.xMax - start.xMin) / 4);
    const step = (a: number[]) => {
      const diffs = a.slice(1).map((n, i) => n - a[i]);
      return Math.min(...diffs);
    };
    const startTicks = graphAxisTicks(
      start.xMin,
      start.xMax,
      graphTickCount(start.xMin, start.xMax),
      true,
    );
    const zoomTicks = graphAxisTicks(
      zoomed.xMin,
      zoomed.xMax,
      graphTickCount(zoomed.xMin, zoomed.xMax),
      true,
    );
    expect(step(zoomTicks)).toBeLessThan(step(startTicks));
  });

  it("zooms out so tick spacing grows", () => {
    const start = defaultInteractiveBounds(1.75);
    const zoomed = zoomGraphView(start, 0.25, 0, 0);
    expect(zoomed.xMax - zoomed.xMin).toBeCloseTo((start.xMax - start.xMin) * 4);
    const startTicks = graphAxisTicks(
      start.xMin,
      start.xMax,
      graphTickCount(start.xMin, start.xMax),
      true,
    );
    const zoomTicks = graphAxisTicks(
      zoomed.xMin,
      zoomed.xMax,
      graphTickCount(zoomed.xMin, zoomed.xMax),
      true,
    );
    const step = (a: number[]) => Math.min(...a.slice(1).map((n, i) => n - a[i]));
    expect(step(zoomTicks)).toBeGreaterThan(step(startTicks));
  });

  it("pans so dragging right reveals more negative x", () => {
    const start = defaultInteractiveBounds(1.75);
    const moved = panGraphView(start, 100, 0, 360, 220, 28);
    expect(moved.xMin).toBeLessThan(start.xMin);
    expect(moved.xMax - moved.xMin).toBeCloseTo(start.xMax - start.xMin);
  });

  it("expandGraphView widens around the center", () => {
    const view = { xMin: -2, xMax: 4, yMin: -1, yMax: 5 };
    const wide = expandGraphView(view, 3);
    expect(wide.xMax - wide.xMin).toBeCloseTo(18);
    expect(wide.yMax - wide.yMin).toBeCloseTo(18);
    expect((wide.xMin + wide.xMax) / 2).toBeCloseTo(1);
    expect((wide.yMin + wide.yMax) / 2).toBeCloseTo(2);
    expect(expandGraphView(view, Number.NaN)).toEqual(view);
  });
});
