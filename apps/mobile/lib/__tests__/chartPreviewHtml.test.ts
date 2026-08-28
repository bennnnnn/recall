import {
  buildVegaHtml,
  preserveChartCategoryOrder,
} from "@/lib/chartPreviewHtml";
import { CHART_PREVIEW_CSP, PREVIEW_CSP } from "@/lib/previewSandbox";

const theme = {
  bg: "#fff",
  text: "#111",
  textSecondary: "#666",
  border: "#ddd",
  danger: "#c00",
  isDark: false,
};

describe("preserveChartCategoryOrder", () => {
  it("sets sort null on nominal x so months keep data.values order", () => {
    const spec = {
      encoding: { x: { field: "month", type: "nominal" }, y: { field: "inches", type: "quantitative" } },
    };
    preserveChartCategoryOrder(spec);
    expect((spec.encoding.x as { sort?: unknown }).sort).toBeNull();
  });

  it("does not override an explicit sort", () => {
    const spec = {
      encoding: { x: { field: "month", type: "nominal", sort: "ascending" } },
    };
    preserveChartCategoryOrder(spec);
    expect(spec.encoding.x.sort).toBe("ascending");
  });

  it("leaves quantitative and temporal x alone", () => {
    const quant = { encoding: { x: { field: "n", type: "quantitative" } } };
    const time = { encoding: { x: { field: "t", type: "temporal" } } };
    preserveChartCategoryOrder(quant);
    preserveChartCategoryOrder(time);
    expect("sort" in quant.encoding.x).toBe(false);
    expect("sort" in time.encoding.x).toBe(false);
  });

  it("walks layer children", () => {
    const spec = {
      layer: [{ encoding: { x: { field: "month", type: "nominal" } } }],
    };
    preserveChartCategoryOrder(spec);
    expect((spec.layer[0].encoding.x as { sort?: unknown }).sort).toBeNull();
  });
});

describe("buildVegaHtml", () => {
  it("injects the chart CSP so Vega Function() compile is allowed", () => {
    const html = buildVegaHtml(
      '{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","mark":"bar"}',
      theme,
    );
    expect(html).toContain(`content="${CHART_PREVIEW_CSP}"`);
    expect(html).toContain("unsafe-eval");
    expect(html).not.toContain(`content="${PREVIEW_CSP}"`);
    expect(html).toContain("JSON.parse");
    expect(html).toContain("connect-src 'none'");
  });

  it("does not use a 100vh body, and embeds sort null for category x", () => {
    const html = buildVegaHtml(
      JSON.stringify({
        $schema: "https://vega.github.io/schema/vega-lite/v5.json",
        mark: "bar",
        encoding: { x: { field: "month", type: "nominal" } },
      }),
      theme,
    );
    expect(html).not.toContain("100vh");
    expect(html).toContain('"sort":null');
  });
});
