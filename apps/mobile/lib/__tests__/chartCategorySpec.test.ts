import { categoryChartToVegaLite } from "@/lib/chartCategorySpec";

type Spec = Record<string, unknown>;
const values = (spec: Spec | null): unknown[] => (spec?.data as { values: unknown[] }).values;
const enc = (spec: Spec | null): Record<string, Record<string, unknown>> =>
  spec?.encoding as Record<string, Record<string, unknown>>;

// The user's screenshot: "Could not render that chart."
const MONTHLY_INCOME = {
  type: "bar",
  title: "Monthly Income",
  xAxis: { label: "Month", values: ["Jan", "Feb", "Mar"] },
  yAxis: { label: "Income ($)", min: 0, max: 15000 },
  series: [{ name: "Monthly Income", color: "#4CAF50", values: [12500, 12500, 13000] }],
};

describe("categoryChartToVegaLite", () => {
  it("draws axis blocks and a coloured series as bars in the labels' order", () => {
    const spec = categoryChartToVegaLite(MONTHLY_INCOME);
    expect(spec).toMatchObject({
      title: "Monthly Income",
      mark: { type: "bar", color: "#4CAF50" },
      encoding: {
        x: { field: "x", type: "ordinal", sort: null, title: "Month" },
        y: { field: "y", type: "quantitative", title: "Income ($)", scale: { domainMin: 0, domainMax: 15000 } },
      },
    });
    expect(values(spec)[0]).toEqual({ x: "Jan", y: 12500, series: "Monthly Income" });
  });

  it("drops a y axis range the data does not fit in", () => {
    const spec = categoryChartToVegaLite({ ...MONTHLY_INCOME, yAxis: { min: 0, max: 10000 } });
    expect(enc(spec).y.scale).toEqual({ domainMin: 0 });
  });

  it.each([
    ["labels with series of values", { labels: ["A", "B"], series: [{ name: "n", values: [1, 2] }] }],
    ["Chart.js datasets without the data wrapper", { labels: ["A", "B"], datasets: [{ label: "n", data: [1, 2] }] }],
    ["categories with one series at the top level", { categories: ["A", "B"], values: [1, 2] }],
    ["an x axis block of categories", { xAxis: { categories: ["A", "B"] }, series: [{ name: "n", data: [1, 2] }] }],
    ["top-level x and y lists", { x: ["A", "B"], y: [1, 2] }],
  ])("reads %s", (_name, body) => {
    expect(values(categoryChartToVegaLite({ type: "bar", ...body }))).toEqual([
      { x: "A", y: 1, series: expect.any(String) },
      { x: "B", y: 2, series: expect.any(String) },
    ]);
  });

  it("puts several bar series side by side, coloured apart and named by the legend", () => {
    const spec = categoryChartToVegaLite({
      chart: { type: "column" },
      title: { text: "Fruit eaten" },
      xAxis: { categories: ["Apples", "Pears"] },
      series: [
        { name: "Jane", data: [1, 4] },
        { name: "John", data: [5, 3] },
      ],
    });
    expect(spec).toMatchObject({
      title: "Fruit eaten",
      mark: "bar",
      encoding: { color: { field: "series" }, xOffset: { field: "series" }, y: { title: null } },
    });
  });

  it("keeps year labels as written on a line, and a scatter's numbers as numbers", () => {
    const body = { xAxis: { title: "Year", labels: [2019, 2020] }, series: [{ name: "n", values: [3, 4] }] };
    const lineSpec = categoryChartToVegaLite({ type: "line", ...body });
    expect(enc(lineSpec).x).toMatchObject({ type: "ordinal", title: "Year" });
    expect(values(lineSpec)[0]).toMatchObject({ x: "2019" });
    const scatter = categoryChartToVegaLite({ type: "scatter", ...body });
    expect(enc(scatter).x).toMatchObject({ type: "quantitative" });
    expect(values(scatter)[0]).toMatchObject({ x: 2019 });
  });

  it("skips a missing value and keeps the rest in place", () => {
    const spec = categoryChartToVegaLite({
      type: "line",
      labels: ["Mon", "Tue", "Wed"],
      series: [{ name: "Steps", values: [4000, null, 6500] }],
    });
    expect(values(spec).map((row) => (row as { x: string }).x)).toEqual(["Mon", "Wed"]);
  });

  it.each([
    ["pie", { type: "arc" }],
    ["donut", { type: "arc", innerRadius: 50 }],
    ["doughnut", { type: "arc", innerRadius: 50 }],
  ])("draws a %s as slices in the order given", (type, mark) => {
    const spec = categoryChartToVegaLite({ type, labels: ["Rent", "Food"], values: [1200, 400] });
    expect(spec).toMatchObject({
      mark,
      encoding: { theta: { field: "y" }, color: { field: "x", sort: null } },
    });
    expect(values(spec).map((row) => (row as { x: string }).x)).toEqual(["Rent", "Food"]);
  });

  it("reads slices written as named values", () => {
    const spec = categoryChartToVegaLite({
      type: "pie",
      series: [{ name: "Share", data: [{ name: "Chrome", y: 61 }, ["Safari", 24]] }],
    });
    expect(values(spec)).toEqual([
      { x: "Chrome", y: 61, series: "Share" },
      { x: "Safari", y: 24, series: "Share" },
    ]);
  });

  it.each([
    ["labels and values of different lengths", { labels: ["A", "B", "C"], series: [{ values: [1, 2] }] }],
    ["values with no labels", { series: [{ name: "n", values: [1, 2] }] }],
    ["values written as text", { labels: ["A", "B"], series: [{ values: ["one", "two"] }] }],
    ["labels with no values", { labels: ["A", "B"] }],
    ["a series written as a formula", { series: [{ name: "f", fn: "x^2" }] }],
    ["a Vega-Lite spec", { mark: "bar", labels: ["A"], values: [1] }],
    ["a Chart.js config", { data: { labels: ["A"], datasets: [{ data: [1] }] } }],
  ])("does not read %s", (_name, body) => {
    expect(categoryChartToVegaLite({ type: "bar", ...body })).toBeNull();
  });
});
