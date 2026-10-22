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
