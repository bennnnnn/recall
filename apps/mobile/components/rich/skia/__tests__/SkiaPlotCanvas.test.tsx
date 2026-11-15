/**
 * The Skia plot renders each server plot (docs/fixtures/plot_fences.json) from the same
 * layout as its SVG fallback, without crashing: pieces with open circles, asymptotes, a
 * washer's region, slice and axis. The mocked Canvas draws nothing itself; the layout the
 * two renderers share is held in `lib/__tests__/plotGraph.test.ts`.
 */
import { render } from "@testing-library/react-native";

import { GRAPH_AXIS_PAD } from "@/components/rich/GraphCanvas";
import { PLOT_HEIGHT } from "@/components/rich/plotPaint";
import { SkiaPlotCanvas } from "@/components/rich/skia/SkiaPlotCanvas";
import { parsePlotGraph, plotLayout } from "@/lib/math/plotGraph";
import { lightTheme } from "@/lib/theme";

declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

type Case = { id: string; body: Record<string, unknown> };
const CASES: Case[] = JSON.parse(
  readFileSync(join(__dirname, "../../../../../../docs/fixtures/plot_fences.json"), "utf8"),
).cases;

describe("SkiaPlotCanvas", () => {
  it.each(CASES.map((c) => [c.id, c.body] as const))("renders %s", async (_id, body) => {
    const graph = parsePlotGraph(JSON.stringify(body))!;
    const layout = plotLayout(graph, 320, PLOT_HEIGHT, GRAPH_AXIS_PAD);
    const { getByTestId } = await render(
      <SkiaPlotCanvas graph={graph} layout={layout} width={320} theme={lightTheme} />,
    );
    expect(getByTestId("plot-graph-skia")).toBeTruthy();
  });
});
