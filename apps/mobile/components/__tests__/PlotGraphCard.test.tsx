/**
 * A server-drawn plot in the chat: a ```graph fence of type `plot` renders as its own card
 * (SVG where Skia is not linked, as in Expo Go), with every curve piece, region, line and
 * point the server sent and a legend of the server's equations. The bodies are the server's
 * own (docs/fixtures/plot_fences.json).
 */
import { render, screen } from "@testing-library/react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";

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
const content = (id: string) => JSON.stringify(CASES.find((c) => c.id === id)!.body);

describe("a plot fence", () => {
  it("draws a function in pieces apart, with its open and filled circles", async () => {
    await render(<FunctionGraphBlock content={content("c008")} />);
    expect(screen.getByTestId("plot-graph")).toBeTruthy();
    expect(screen.getAllByTestId("plot-curve")).toHaveLength(3);
    expect(screen.getAllByTestId("plot-dot-open")).toHaveLength(2);
    expect(screen.getAllByTestId("plot-dot")).toHaveLength(2);
  });

  it("draws asymptotes dashed and names them in the legend", async () => {
    await render(<FunctionGraphBlock content={content("c029")} />);
    expect(screen.getAllByTestId("plot-line-asymptote")).toHaveLength(2);
    expect(screen.getByText("x = 2")).toBeTruthy();
    expect(screen.getByText("y = x")).toBeTruthy();
    // The turning points' labels, set on the canvas.
    expect(screen.getAllByTestId("plot-label")).toHaveLength(2);
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
