import { chartPreviewConfig } from "@/lib/chartPreviewHtml";
import { parseChartBody, seriesChartToVegaLite } from "@/lib/chartSeriesSpec";

const theme = {
  bg: "#fff",
  text: "#111",
  textSecondary: "#666",
  border: "#ddd",
  danger: "#c00",
  isDark: false,
};

// What a reply to "Plot" stored: a caption line, then a series chart instead of Vega-Lite.
const PLOT_REPLY_BODY = [
  "x^2 over [-5, 5]",
  '{"type":"line","title":"y = x²","xLabel":"x","yLabel":"y","series":[{"name":"y = x²",' +
    '"points":[[-2,4],[-1,1],[0,0],[1,1],[2,4]]}]}',
].join("\n");

describe("parseChartBody", () => {
  it.each([
    ["the JSON alone", '{"mark":"bar"}'],
    ["a caption line before it", 'Rainfall by month\n{"mark":"bar"}'],
    ["a sentence after it", '{"mark":"bar"}\nThat is the chart.'],
  ])("reads %s", (_name, body) => {
    expect(parseChartBody(body)).toEqual({ mark: "bar" });
  });

  it.each(["x^2 over [-5, 5]", "{not json}", ""])("is null for %j", (body) => {
    expect(parseChartBody(body)).toBeNull();
  });

  it("reads the object a model closed early and wrote past", () => {
    // A histogram reply: one `}` too many, then a "config" outside the object.
    const body = '{"mark":"bar","encoding":{"y":{"aggregate":"count"}}}},"config":{"view":{}}}';
    expect(parseChartBody(body)).toEqual({ mark: "bar", encoding: { y: { aggregate: "count" } } });
  });

  it("does not count braces inside strings", () => {
    expect(parseChartBody('Scores\n{"title":"a } b","mark":"bar"} and a stray }')).toEqual({
      title: "a } b",
      mark: "bar",
    });
  });
});

describe("seriesChartToVegaLite", () => {
  it("draws a series chart as a Vega-Lite line with its title and axes", () => {
    const spec = seriesChartToVegaLite(parseChartBody(PLOT_REPLY_BODY) as Record<string, unknown>);
    expect(spec).toMatchObject({
      title: "y = x²",
      mark: "line",
      data: { values: expect.arrayContaining([{ x: -2, y: 4, series: "y = x²" }]) },
      encoding: { x: { field: "x", title: "x" }, y: { field: "y", title: "y" } },
    });
    expect((spec?.data as { values: unknown[] }).values).toHaveLength(5);
    expect((spec?.encoding as Record<string, unknown>).color).toBeUndefined();
  });

  it("colours two series apart and reads {x, y} points", () => {
    const spec = seriesChartToVegaLite({
      type: "scatter",
      series: [
        { name: "a", points: [{ x: 1, y: 2 }] },
        { name: "b", points: [[3, 4]] },
      ],
    });
    expect(spec).toMatchObject({ mark: "point", encoding: { color: { field: "series" } } });
  });

  it("draws a best-fit series as a line over the scattered points", () => {
    // A scatter reply: the second series says "type": "line"; it drew as two stray points.
    const spec = seriesChartToVegaLite({
      type: "scatter",
      title: "Experiment",
      x_axis: { label: "time (s)" },
      y_axis: { label: "distance (m)" },
      series: [
        { name: "Data points", points: [[1, 2.1], [2, 3.9], [3, 6.2]] },
        { name: "Best-fit line", points: [[0, 0.06], [6, 12.12]], type: "line" },
      ],
    });
    expect(spec).toMatchObject({
      title: "Experiment",
      encoding: {
        x: { title: "time (s)", type: "quantitative" },
        y: { title: "distance (m)" },
        color: { field: "series" },
      },
      layer: [
        { mark: "point", transform: [{ filter: { field: "series", oneOf: ["Data points"] } }] },
        { mark: "line", transform: [{ filter: { field: "series", oneOf: ["Best-fit line"] } }] },
      ],
    });
    expect(spec).not.toHaveProperty("mark");
  });

  it("leaves a series given as a formula for the server", () => {
    expect(
      seriesChartToVegaLite({
        type: "line",
        series: [{ name: "sin", type: "function", fn: "sin(x)", domain: [0, 6.2832] }],
      }),
    ).toBeNull();
  });

  it.each([
    ["a Vega-Lite spec", { mark: "bar", data: { values: [] } }],
    ["no series", { type: "line" }],
    ["a point that is not a number", { series: [{ points: [["a", 1]] }] }],
  ])("leaves %s alone", (_name, spec) => {
    expect(seriesChartToVegaLite(spec)).toBeNull();
  });
});

it("builds the Plot reply's chart as Vega-Lite instead of failing on its caption line", () => {
  const { spec } = chartPreviewConfig(PLOT_REPLY_BODY, theme);
  expect(spec).toContain('"mark":"line"');
  expect(spec).not.toContain("x^2 over");
});
