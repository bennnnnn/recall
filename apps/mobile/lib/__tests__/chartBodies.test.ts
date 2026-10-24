/**
 * Chart bodies as models write them (docs/fixtures/chart_bodies.json, which the server
 * tests against too): each one the fixture says draws is read, drawn by the real page
 * with data marks, and fills the card's width; each one it says does not is left to the
 * card's "Could not render that chart." Then what a phone card needs to read a drawn
 * chart: short labels for big numbers, lines not pinned to zero, legends in the order given.
 */
import { readChart } from "@/lib/chartSpec";

import { CARD_WIDTH, drawChart, drawnLabels } from "./fixtures/chartPage";

// The lib test project has Jest types but no Node type package.
declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

type ChartBody = { name: string; body: string; draws: boolean };

const BODIES: ChartBody[] = JSON.parse(
  readFileSync(join(__dirname, "../../../../docs/fixtures/chart_bodies.json"), "utf8"),
);
const named = (name: string): string => {
  const entry = BODIES.find((body) => body.name === name);
  if (!entry) throw new Error(`no fixture body named ${name}`);
  return entry.body;
};

describe("chart bodies models write", () => {
  it.each(BODIES.filter((entry) => entry.draws).map((entry) => [entry.name, entry.body]))(
    "draws %s across the card",
    async (_name, body) => {
      expect(readChart(body).spec).not.toBeNull();
      const { posted, view } = await drawChart(body);
      expect(posted).toEqual([{ kind: "chart-size", height: expect.any(Number) }]);
      // A plot with no x axis or a few named categories drew 20 px wide.
      expect(view?.width()).toBeGreaterThanOrEqual(CARD_WIDTH / 2);
    },
  );

  it.each(BODIES.filter((entry) => !entry.draws).map((entry) => [entry.name, entry.body]))(
    "does not draw %s",
    (_name, body) => {
      expect(readChart(body).spec).toBeNull();
    },
  );
});

describe("a drawn chart on a phone card", () => {
  it("writes billions, millions and thousands short instead of cutting them off", async () => {
    const { view } = await drawChart(named("world population in billions (labels written short)"));
    const labels = await drawnLabels(view!);
    expect(labels).toEqual(expect.arrayContaining(["4B", "8B"]));
    expect(labels.join(" ")).not.toMatch(/000,000/);

    // One unit for the whole axis: 0, 2k … 14k, not 8,000 beside 10k.
    const income = await drawChart(named("xAxis and yAxis blocks with a coloured series (monthly income)"));
    const axis = await drawnLabels(income.view!);
    expect(axis).toEqual(expect.arrayContaining(["0", "2k", "10k"]));
    expect(axis).not.toContain("8,000");
  });

  it("starts a line's value axis near its data, not at zero", async () => {
    const { view } = await drawChart(named("weight from 80 to 75 kg (a line not pinned to zero)"));
    const [low] = view!.scale("y")!.domain() as number[];
    expect(low).toBeGreaterThan(70);
  });

  it("keeps bars pinned to zero", async () => {
    const { view } = await drawChart(named("labels with series of values (bar)"));
    expect((view!.scale("x")!.domain() as number[])[0]).toBe(0);
  });

  it("lists pie slices in the order the reply gave them", async () => {
    const { view } = await drawChart(named("a pie of labels and top-level values"));
    const labels = await drawnLabels(view!);
    const order = ["Rent", "Food", "Transport", "Fun"].map((label) => labels.indexOf(label));
    expect(order.every((at, i) => at >= 0 && (i === 0 || at > order[i - 1]))).toBe(true);
  });
});
