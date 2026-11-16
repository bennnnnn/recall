/**
 * The server's plot fences (docs/fixtures/plot_fences.json, held to what the server draws
 * by the API's test_plot_fence_fixture.py) read and handed to the function graph's own
 * renderers: every curve piece, line, region and point the server sent, open circles where
 * it said, the server's labels and no others, and one scale on both axes when the plot asks
 * for it. A part that is malformed is left out, never the graph; a fence that is no plot is
 * refused.
 */
import { evalGraphExpr, parseGraphExpr, realPower } from "@/lib/math/graphExpr";
import { parsePlotGraph, plotHeight } from "@/lib/math/plotGraph";

declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

type Case = { id: string; body: Record<string, unknown> };
const CASES: Case[] = JSON.parse(
  readFileSync(join(__dirname, "../../../../docs/fixtures/plot_fences.json"), "utf8"),
).cases;

describe("plot fences the server draws", () => {
  it.each(CASES.map((c) => [c.id, c.body] as const))("reads %s whole", (_id, raw) => {
    const graph = parsePlotGraph(JSON.stringify(raw));
    expect(graph).not.toBeNull();
    const sent = raw as { curves: unknown[]; lines: unknown[]; regions: unknown[]; points: unknown[] };
    expect(graph!.curves).toHaveLength(sent.curves.length);
    expect(graph!.lines).toHaveLength(sent.lines.length);
    expect(graph!.regions).toHaveLength(sent.regions.length);
    expect(graph!.points).toHaveLength(sent.points.length);
  });

});

describe("parsePlotGraph", () => {
  const base = { type: "plot", x_min: -1, x_max: 1, y_min: -1, y_max: 1, curves: [{ segments: [[[0, 0], [1, 1]]] }] };

  it.each([
    ["another kind", { ...base, type: "function" }],
    ["a window that is no window", { ...base, x_max: -2 }],
    ["an infinite edge", { ...base, y_max: 1e400 }],
    ["no curve to draw", { ...base, curves: [{ segments: [[[0, 0]]] }] }],
  ])("refuses %s", (_name, raw) => {
    expect(parsePlotGraph(JSON.stringify(raw))).toBeNull();
  });

  it("leaves out a malformed part, never the graph", () => {
    const graph = parsePlotGraph(
      JSON.stringify({ ...base, points: [{ x: 0, y: "a" }, { x: 0.5, y: 0.5, label: "(1/2, 1/2)" }], lines: [{ start: [0, 0] }] }),
    );
    expect(graph?.points).toEqual([{ x: 0.5, y: 0.5, open: false, label: "(1/2, 1/2)", color: 0 }]);
    expect(graph?.lines).toEqual([]);
  });

  it("is as tall as a plot drawn to one scale asks, never widening its window", () => {
    // The server grew the window to one scale; the card takes its shape at this width.
    const graph = parsePlotGraph(JSON.stringify({ ...base, x_max: 2.3, equal: true }))!;
    const height = plotHeight(graph, 343, 16, 220);
    const xPerPx = (graph.xMax - graph.xMin) / (343 - 32);
    const yPerPx = (graph.yMax - graph.yMin) / (height - 32);
    expect(xPerPx).toBeCloseTo(yPerPx, 9);
    expect([graph.xMin, graph.xMax, graph.yMin, graph.yMax]).toEqual([-1, 2.3, -1, 1]);
  });

  it("keeps its own height when the plot asks for no one scale", () => {
    expect(plotHeight(parsePlotGraph(JSON.stringify(base))!, 343, 16, 220)).toBe(220);
  });
});

describe("realPower", () => {
  it.each([
    [-8, 1 / 3, -2],
    [-8, 2 / 3, 4],
    [-32, 3 / 5, -8],
    [8, 1 / 3, 2],
  ])("takes the real root: (%d)^%f is %d", (base, exponent, expected) => {
    expect(realPower(base, exponent)).toBeCloseTo(expected, 12);
  });

  it("has no real even root of a negative", () => {
    expect(realPower(-4, 0.5)).toBeNaN();
  });

  it("reads a decimal power as the server does: no odd root of a negative (x^0.4)", () => {
    expect(evalGraphExpr(parseGraphExpr("x^0.4")!, -32)).toBeNaN();
    expect(evalGraphExpr(parseGraphExpr("x^(2/5)")!, -32)).toBeCloseTo(4, 12);
  });
});

describe("one scale on both axes", () => {
  const graph = (equal: boolean, xMax: number) =>
    parsePlotGraph(JSON.stringify({ type: "plot", x_min: 0, x_max: xMax, y_min: 0, y_max: 1, equal,
      curves: [{ label: "", segments: [[[0, 0], [1, 1]]] }] }))!;

  it("never widens the server's window, whatever the card's size", () => {
    const plot = graph(true, 1);
    const height = plotHeight(plot, 330, 10, 220);
    expect([plot.xMin, plot.xMax, plot.yMin, plot.yMax]).toEqual([0, 1, 0, 1]);
    // A square window asks for a card as tall as it is wide, within its least and most.
    expect(height).toBe(330);
  });

  it("keeps a card within its height when the window is a thin strip", () => {
    expect(plotHeight(graph(true, 100), 330, 10, 220)).toBe(160);
  });
});

describe("the curves a plot keeps", () => {
  it("are the five the server draws", () => {
    const curve = { label: "", segments: [[[0, 0], [1, 1]]] };
    const curves = [curve, curve, curve, curve, curve];
    const plot = parsePlotGraph(JSON.stringify({ type: "plot", x_min: -1, x_max: 1, y_min: -1, y_max: 1, curves }));
    expect(plot?.curves).toHaveLength(5);
  });
});
