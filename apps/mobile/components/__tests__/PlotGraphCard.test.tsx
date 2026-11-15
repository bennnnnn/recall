/**
 * A server-drawn plot in the chat: a ```graph fence of type `plot` renders with the function
 * graph's own canvas (SVG where Skia is not linked, as in Expo Go), with every region, line
 * and point the server sent and a legend of the server's equations. The bodies are the server's
 * own (docs/fixtures/plot_fences.json).
 */
import { render, screen } from "@testing-library/react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";
import { plotDrawing } from "@/components/rich/plotDrawing";
import { parsePlotGraph } from "@/lib/math/plotGraph";

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

  it("draws a washer's region, its slice, its turn and the axis", async () => {
    await render(<FunctionGraphBlock content={content("washer")} />);
    expect(screen.getAllByTestId("plot-region-shade").length).toBeGreaterThan(0);
    expect(screen.getByTestId("plot-region-strip")).toBeTruthy();
    expect(screen.getByTestId("plot-region-mirror")).toBeTruthy();
    expect(screen.getByTestId("plot-line-axis")).toBeTruthy();
  });

  it("refuses a plot it cannot read, as any graph", async () => {
    await render(<FunctionGraphBlock content={JSON.stringify({ type: "plot", x_min: 1, x_max: 0 })} />);
    expect(screen.queryByTestId("plot-graph")).toBeNull();
  });
});

describe("plotDrawing", () => {
  const PALETTE = ["#111111", "#222222", "#333333", "#444444"];
  const drawing = (id: string) => plotDrawing(parsePlotGraph(JSON.stringify(body(id)))!, PALETTE);

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

  it("draws a washer's region, its slice and the slice turned about the axis", () => {
    const { layers } = drawing("washer");
    expect(layers.regions.map((r) => r.kind).sort()).toEqual(["mirror", "shade", "strip"]);
    expect(layers.lines.filter((l) => l.role === "axis")).toHaveLength(1);
  });
});
