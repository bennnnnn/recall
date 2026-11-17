/**
 * A server-drawn plot in the chat: a ```graph fence of type `plot` renders with the function
 * graph's own canvas (SVG where Skia is not linked, as in Expo Go), with every region, line
 * and point the server sent and a legend of the server's equations. The bodies are the server's
 * own (docs/fixtures/plot_fences.json).
 */
import { render, screen } from "@testing-library/react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";
import { plotDrawing } from "@/components/rich/plotDrawing";
import { PLOT_NEUTRAL, plotColor, plotStroke } from "@/components/rich/plotPaint";
import { parsePlotGraph } from "@/lib/math/plotGraph";
import { lightTheme } from "@/lib/theme";

jest.mock("@/lib/skiaAvailability", () => ({ isSkiaAvailable: () => false }));

declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

type Case = { id: string; body: Record<string, unknown> };
const CASES: Case[] = JSON.parse(
  readFileSync(join(__dirname, "../../../../docs/fixtures/plot_fences.json"), "utf8"),
).cases;
const body = (id: string) => CASES.find((c) => c.id === id)!.body;
const content = (id: string) => JSON.stringify(CASES.find((c) => c.id === id)!.body);

describe("a plot fence", () => {
  it("draws a function in pieces apart, with its open and filled circles", async () => {
    await render(<FunctionGraphBlock content={content("c008")} />);
    expect(screen.getByTestId("plot-graph")).toBeTruthy();
    expect(screen.getAllByTestId(/^graph-hole-/)).toHaveLength(2);
    expect(screen.getAllByTestId(/^graph-mark-\d+$/)).toHaveLength(2);
  });

  it("draws asymptotes dashed and names them in the legend", async () => {
    await render(<FunctionGraphBlock content={content("c029")} />);
    expect(screen.getAllByTestId("plot-line-asymptote")).toHaveLength(2);
    expect(screen.getByText("x = 2")).toBeTruthy();
    expect(screen.getByText("y = x")).toBeTruthy();
    // The turning points' labels, the server's, set on the canvas; none of the phone's own.
    expect(screen.getAllByTestId(/^graph-mark-label-/)).toHaveLength(2);
  });

  it("strokes an asymptote in its curve's colour, so its legend row names that curve's", () => {
    expect(plotStroke(lightTheme, "asymptote", 1)).toEqual({ color: lightTheme.graphSeries[1], width: 1.5 });
  });

  it("paints the server's neutral colour as no curve's", () => {
    expect(plotColor(lightTheme, PLOT_NEUTRAL)).toBe(lightTheme.textSecondary);
    expect(plotStroke(lightTheme, "asymptote", PLOT_NEUTRAL).color).toBe(lightTheme.textSecondary);
  });

  it("draws a washer's region, its slice, its turn and the axis", async () => {
    await render(<FunctionGraphBlock content={content("washer")} />);
    expect(screen.getAllByTestId("plot-region-shade").length).toBeGreaterThan(0);
    expect(screen.getByTestId("plot-region-strip")).toBeTruthy();
    expect(screen.getByTestId("plot-region-mirror")).toBeTruthy();
    expect(screen.getByTestId("plot-line-axis")).toBeTruthy();
  });

  it("names what it plots when it labels nothing", async () => {
    const curves = [{ label: "", segments: [[[0, 0], [1, 1]]] }];
    const bare = { type: "plot", x_min: -1, x_max: 1, y_min: -1, y_max: 1, x_label: "t", y_label: "v", curves };
    await render(<FunctionGraphBlock content={JSON.stringify(bare)} />);
    // Never an empty label: the card names its graph (the key, where tests load no language).
    expect(screen.getByLabelText(/Graph of v\(t\)|rich\.graph_card_a11y/)).toBeTruthy();
  });

  it("refuses a plot it cannot read, as any graph", async () => {
    await render(<FunctionGraphBlock content={JSON.stringify({ type: "plot", x_min: 1, x_max: 0 })} />);
    expect(screen.queryByTestId("plot-graph")).toBeNull();
  });
});

describe("plotDrawing", () => {
  const drawing = (id: string) => plotDrawing(parsePlotGraph(JSON.stringify(body(id)))!, lightTheme);

  it("hands a function in pieces to the function graph apart, with its circles (round 3, c008)", () => {
    const { drawn, points } = drawing("c008");
    expect(points.holes).toHaveLength(2);
    expect(points.marks).toHaveLength(2);
    // Three pieces drawn apart: never one line across a jump.
    expect(drawn[0].segments).toHaveLength(3);
  });

  it("draws asymptotes as layers of their own, named in the legend (c029)", () => {
    const { drawn, layers, legend, points } = drawing("c029");
    expect(layers.lines.filter((l) => l.role === "asymptote")).toHaveLength(2);
    expect(legend.map((row) => row.label)).toEqual(expect.arrayContaining(["x = 2", "y = x"]));
    expect(drawn[0].segments).toHaveLength(2);
    expect(points.marks.map((m) => m.label)).toEqual(["(0, \u22122)", "(4, 6)"]);
  });

  it("paints a point in the neutral colour as the lines are, not as a curve's", () => {
    const graph = { ...body("c008"), points: [{ x: 0, y: 0, open: false, label: "", color: PLOT_NEUTRAL }] };
    const { points } = plotDrawing(parsePlotGraph(JSON.stringify(graph))!, lightTheme);
    expect(points.marks[0].color).toBe(lightTheme.textSecondary);
  });

  it("names a nearest point's distance in the legend, and dots no curve sample", () => {
    const line = { start: [0, 2], end: [1.2, 1.5], role: "segment", label: "≈ 1.323", color: 2 };
    const graph = { ...body("c008"), lines: [line] };
    const { legend, drawn } = plotDrawing(parsePlotGraph(JSON.stringify(graph))!, lightTheme);
    expect(legend.map((row) => row.label)).toContain("≈ 1.323");
    expect(drawn.every((series) => series.marked === false)).toBe(true);
  });

  it("draws a washer's region, its slice and the slice turned about the axis", () => {
    const { layers } = drawing("washer");
    expect(layers.regions.map((r) => r.kind).sort()).toEqual(["mirror", "shade", "strip"]);
    expect(layers.lines.filter((l) => l.role === "axis")).toHaveLength(1);
  });
});
