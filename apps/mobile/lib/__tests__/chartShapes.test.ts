/**
 * The chart contract, drawn: every shape the server's chart hint shows the model
 * (apps/api/app/modules/chat/prompt_constants/chart_shapes.json) goes through the
 * card's reading, the page's layout and the page's own script, with the vendored
 * Vega and Vega-Lite doing the drawing, and puts data marks on the plot. So do the
 * bodies models wrote that once drew a blank card. A spec that draws nothing makes
 * the page report an error, so the card shows its data instead.
 */
import { buildVegaPageHtml, chartPreviewConfig } from "@/lib/chartPreviewHtml";
import { readChart } from "@/lib/chartSpec";

import { previewPageSandbox, settle } from "./fixtures/previewPageSandbox";

// The lib test project has Jest types but no Node type package.
declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");
const vm = jest.requireActual<{
  createContext(scope: Record<string, unknown>): Record<string, unknown>;
  runInContext(source: string, context: Record<string, unknown>): unknown;
}>("node:vm");

type VegaView = { runAsync(): Promise<unknown>; scenegraph(): unknown };
type Vega = {
  View: new (runtime: unknown, options: Record<string, unknown>) => VegaView;
  parse(spec: unknown): unknown;
  loader(): unknown;
};
type VegaLite = { compile(spec: unknown): { spec: unknown } };

const VENDOR = join(__dirname, "../vendor");
const SHAPES: Record<string, Record<string, unknown>> = JSON.parse(
  readFileSync(
    join(__dirname, "../../../api/app/modules/chat/prompt_constants/chart_shapes.json"),
    "utf8",
  ),
);
const theme = { bg: "#fff", text: "#111", textSecondary: "#666", border: "#ddd", danger: "#c00", isDark: false };

// Vega-Lite clones specs with structuredClone, which the test realm may not have; specs are JSON.
const clone = (value: unknown): unknown => JSON.parse(JSON.stringify(value));
const scope: Record<string, unknown> = {
  console,
  setTimeout,
  clearTimeout,
  URL,
  TextEncoder,
  TextDecoder,
  structuredClone: clone,
};
scope.window = scope;
scope.self = scope;
const context = vm.createContext(scope);
for (const file of ["vega.min.js.txt", "vega-lite.min.js.txt"]) {
  vm.runInContext(readFileSync(join(VENDOR, file), "utf8"), context);
}
const vega = context.vega as Vega;
const vegaLite = context.vegaLite as VegaLite;

/** Vega-Embed as the page calls it, drawing with the real libraries. */
async function vegaEmbed(_target: string, spec: Record<string, unknown>, options: { loader: unknown }) {
  const schema = typeof spec.$schema === "string" ? spec.$schema : "";
  const runtime = schema.includes("/vega/") ? spec : vegaLite.compile(spec).spec;
  const view = new vega.View(vega.parse(runtime), { renderer: "none", loader: options.loader });
  await view.runAsync();
  return { view };
}

/** What the chart page posts once it has drawn `body`. */
async function draw(body: string): Promise<unknown[]> {
  const page = previewPageSandbox({ vega, vegaEmbed });
  page.loadPage(buildVegaPageHtml({ vega: "", vegaLite: "", vegaEmbed: "" }));
  page.hand(chartPreviewConfig(body, theme, 320));
  for (let tick = 0; tick < 50 && page.posted.length === 0; tick += 1) {
    await settle();
    page.runFrames();
  }
  return page.posted;
}

const DRAWN = [{ kind: "chart-size", height: expect.any(Number) }];

// Bodies from replies that drew a blank card or stray points.
const MODEL_BODIES: [string, string][] = [
  [
    "a Chart.js config of sin and cos",
    JSON.stringify({
      type: "line",
      data: {
        labels: [0, "π/2", "π", "3π/2", "2π"],
        datasets: [
          { label: "y = sin(x)", data: [0, 1, 0, -1, 0] },
          { label: "y = cos(x)", data: [1, 0, -1, 0, 1] },
        ],
      },
    }),
  ],
  [
    "a scatter whose best-fit series is a line",
    JSON.stringify({
      type: "scatter",
      x_axis: { label: "x" },
      y_axis: { label: "y" },
      series: [
        { name: "Data points", points: [[1, 2.1], [2, 3.9], [3, 6.2], [4, 7.8], [5, 10.1]] },
        { name: "Best-fit line", points: [[0, 0.06], [6, 12.12]], type: "line" },
      ],
    }),
  ],
  [
    "a pre-binned histogram with a tooltip format Vega cannot read",
    JSON.stringify({
      $schema: "https://vega.github.io/schema/vega-lite/v5.json",
      data: { values: [55, 62, 68, 70, 71, 75, 78, 80, 82, 85, 88, 90, 95].map((score) => ({ score })) },
      transform: [
        { bin: true, field: "score", as: ["score_start", "score_end"] },
        { aggregate: [{ op: "count", as: "frequency" }], groupby: ["score_start", "score_end"] },
      ],
      mark: "bar",
      encoding: {
        x: { field: "score_start", type: "quantitative", bin: "binned" },
        y: { field: "frequency", type: "quantitative" },
        tooltip: [{ field: "score_start", type: "quantitative", format: "[datum.scoreStart, datum.scoreEnd)" }],
      },
    }),
  ],
  [
    "a box plot written as series of raw values",
    JSON.stringify({
      type: "boxplot",
      title: "Test scores",
      series: [
        { name: "Class A", values: [55, 62, 70, 74, 88] },
        { name: "Class B", values: [61, 72, 75, 80, 93] },
      ],
    }),
  ],
  [
    "a histogram with one closing brace too many and a config after it",
    '{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","data":{"values":[{"score":55},' +
      '{"score":62},{"score":80}]},"transform":[{"bin":true,"field":"score","as":["s0","s1"]}],' +
      '"mark":"bar","encoding":{"x":{"field":"s0","type":"quantitative"},"y":{"aggregate":"count",' +
      '"type":"quantitative"}}}},"config":{"view":{"stroke":"transparent"}}}',
  ],
];

describe("the chart contract", () => {
  it("shows the model six shapes", () => {
    expect(Object.keys(SHAPES)).toEqual([
      "bar",
      "line",
      "scatter with best-fit line",
      "histogram",
      "pie",
      "box plot",
    ]);
  });

  it.each(Object.entries(SHAPES))("draws the %s shape with data marks", async (_name, spec) => {
    const body = JSON.stringify(spec);
    expect(readChart(body).spec).not.toBeNull();
    expect(await draw(body)).toEqual(DRAWN);
  });

  it.each(MODEL_BODIES)("draws %s", async (_name, body) => {
    expect(readChart(body).spec).not.toBeNull();
    expect(await draw(body)).toEqual(DRAWN);
  });

  it("reports a spec that draws no data marks, so the card shows its data instead", async () => {
    const body = JSON.stringify({
      data: { values: [{ a: 1 }, { a: 2 }] },
      transform: [{ filter: { field: "a", gt: 5 } }],
      mark: "bar",
      encoding: { x: { field: "a", type: "quantitative" }, y: { aggregate: "count" } },
    });
    expect(await draw(body)).toEqual([{ kind: "chart-error", message: "No data marks were drawn." }]);
  });
});
