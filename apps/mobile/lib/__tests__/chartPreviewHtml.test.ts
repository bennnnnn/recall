import {
  buildVegaPageHtml,
  CHART_PAGE,
  chartPreviewConfig,
  normalizeChartSpec,
} from "@/lib/chartPreviewHtml";
import { PREVIEW_PAGE_LINK_KIND } from "@/lib/previewPage";
import { CHART_PREVIEW_CSP, PREVIEW_CSP } from "@/lib/previewSandbox";

import { previewPageSandbox, settle } from "./fixtures/previewPageSandbox";

const SOURCES = { vega: "/*vega*/", vegaLite: "/*vega-lite*/", vegaEmbed: "/*vega-embed*/" };

const theme = {
  bg: "#fff",
  text: "#111",
  textSecondary: "#666",
  border: "#ddd",
  danger: "#c00",
  isDark: false,
};

describe("normalizeChartSpec", () => {
  it("sets sort null on nominal x so months keep data.values order", () => {
    const spec = {
      encoding: { x: { field: "month", type: "nominal" }, y: { field: "inches", type: "quantitative" } },
    };
    normalizeChartSpec(spec);
    expect((spec.encoding.x as { sort?: unknown }).sort).toBeNull();
  });

  it("does not override an explicit sort", () => {
    const spec = {
      encoding: { x: { field: "month", type: "nominal", sort: "ascending" } },
    };
    normalizeChartSpec(spec);
    expect(spec.encoding.x.sort).toBe("ascending");
  });

  it("leaves quantitative and temporal x alone", () => {
    const quant = { encoding: { x: { field: "n", type: "quantitative" } } };
    const time = { encoding: { x: { field: "t", type: "temporal" } } };
    normalizeChartSpec(quant);
    normalizeChartSpec(time);
    expect("sort" in quant.encoding.x).toBe(false);
    expect("sort" in time.encoding.x).toBe(false);
  });

  it("walks layer children", () => {
    const spec = {
      layer: [{ encoding: { x: { field: "month", type: "nominal" } } }],
    };
    normalizeChartSpec(spec);
    expect((spec.layer[0].encoding.x as { sort?: unknown }).sort).toBeNull();
  });

  it("swaps named-category x to y so month labels sit on the left", () => {
    const spec = {
      mark: "bar",
      data: { values: [{ month: "Jan", inches: 5.7 }] },
      encoding: {
        x: { field: "month", type: "nominal" },
        y: { field: "inches", type: "quantitative" },
      },
    };
    normalizeChartSpec(spec);
    expect((spec.encoding.y as { field?: string }).field).toBe("month");
    expect((spec.encoding.x as { field?: string }).field).toBe("inches");
    expect((spec.encoding.y as { sort?: unknown }).sort).toBeNull();
  });

  it("does not swap line charts", () => {
    const spec = {
      mark: "line",
      encoding: {
        x: { field: "month", type: "nominal" },
        y: { field: "inches", type: "quantitative" },
      },
    };
    normalizeChartSpec(spec);
    expect((spec.encoding.x as { field?: string }).field).toBe("month");
  });

  it("moves xOffset to yOffset when flipping grouped bars horizontal", () => {
    const spec: Record<string, unknown> = {
      mark: "bar",
      encoding: {
        x: { field: "month", type: "nominal" },
        y: { field: "inches", type: "quantitative" },
        xOffset: { field: "series", type: "nominal" },
      },
    };
    normalizeChartSpec(spec);
    const enc = spec.encoding as Record<string, { field?: string } | undefined>;
    expect(enc.y?.field).toBe("month");
    expect(enc.x?.field).toBe("inches");
    expect(enc.yOffset?.field).toBe("series");
    expect(enc.xOffset).toBeUndefined();
  });

  it("leaves already-horizontal grouped bars on yOffset", () => {
    const spec: Record<string, unknown> = {
      mark: "bar",
      encoding: {
        x: { field: "inches", type: "quantitative" },
        y: { field: "month", type: "nominal" },
        yOffset: { field: "series", type: "nominal" },
      },
    };
    normalizeChartSpec(spec);
    const enc = spec.encoding as Record<string, { field?: string } | undefined>;
    expect(enc.yOffset?.field).toBe("series");
    expect(enc.xOffset).toBeUndefined();
  });
});

describe("buildVegaPageHtml", () => {
  it("injects the chart CSP so Vega Function() compile is allowed", () => {
    const html = buildVegaPageHtml(SOURCES);
    expect(html).toContain(`content="${CHART_PREVIEW_CSP}"`);
    expect(html).toContain("unsafe-eval");
    expect(html).not.toContain(`content="${PREVIEW_CSP}"`);
    expect(html).toContain("JSON.parse");
    expect(html).toContain("connect-src 'none'");
  });

  it("inlines Vega, Vega-Lite and Vega-Embed once each, in load order", () => {
    const html = buildVegaPageHtml(SOURCES);
    const at = Object.values(SOURCES).map((source) => html.indexOf(source));
    expect(at.every((index, i) => index > (at[i - 1] ?? 0))).toBe(true);
    for (const source of Object.values(SOURCES)) expect(html.split(source)).toHaveLength(2);
  });

  it("reports SVG size, disables tooltip, and does not use a 100vh body", () => {
    const html = buildVegaPageHtml(SOURCES);
    expect(html).not.toContain("100vh");
    expect(html).toContain("chart-size");
    expect(html).toContain("tooltip: false");
    expect(html).toContain("overflow: hidden");
  });

  it("is one page for every chart: the spec and theme arrive as config", () => {
    expect(CHART_PAGE.libraries).toEqual(["vega", "vegaLite", "vegaEmbed"]);
    const html = CHART_PAGE.build(SOURCES);
    expect(html).toBe(buildVegaPageHtml(SOURCES));
    expect(html).not.toContain(theme.bg);
  });
});

/** Vega's loader as the page gets it from `vega.loader()`, sanitizing as Vega would. */
function fakeVega() {
  const sanitize = jest.fn(async (uri: string) => ({ href: uri }));
  return { vega: { loader: () => ({ sanitize }) }, sanitize };
}

type EmbedOptions = { loader: { sanitize: (uri: string, options: { context: string }) => Promise<unknown> } };

describe("the chart page", () => {
  it("embeds the spec it is handed, themed and fitted to the card", async () => {
    const vegaEmbed = jest.fn((_target: string, _spec: unknown, _options: EmbedOptions) => Promise.resolve());
    const page = previewPageSandbox({ vegaEmbed, ...fakeVega() });
    page.loadPage(buildVegaPageHtml(SOURCES));
    expect(vegaEmbed).not.toHaveBeenCalled();

    page.hand(chartPreviewConfig('{"mark":"bar","config":{"axis":{"grid":false}}}', theme, 296));
    expect(page.css).toEqual({ "--bg": "#fff", "--danger": "#c00" });
    const themed = {
      background: "#fff",
      axis: { domainColor: "#666", labelColor: "#111", titleColor: "#111", tickColor: "#666", gridColor: "#ddd" },
      legend: { labelColor: "#111", titleColor: "#111" },
      title: { color: "#111" },
      view: { stroke: "#666" },
    };
    expect(vegaEmbed).toHaveBeenCalledWith(
      "#chart",
      {
        mark: "bar",
        // The spec's own config wins over the theme's, key by key at the top level.
        config: { ...themed, axis: { grid: false } },
        autosize: { type: "fit-x", contains: "padding" },
      },
      {
        actions: false,
        tooltip: false,
        renderer: "svg",
        width: 296,
        theme: "vox",
        config: themed,
        loader: expect.anything(),
      },
    );
    await settle();
    page.runFrames();
    expect(page.posted).toEqual([{ kind: "chart-size", height: 116 }]);
  });

  it("hands a mark's link to the app instead of letting Vega follow it", async () => {
    const vegaEmbed = jest.fn((_target: string, _spec: unknown, _options: EmbedOptions) => Promise.resolve());
    const { vega, sanitize } = fakeVega();
    const page = previewPageSandbox({ vegaEmbed, vega });
    page.loadPage(buildVegaPageHtml(SOURCES));
    page.hand(chartPreviewConfig('{"mark":"bar"}', theme));
    const { loader } = vegaEmbed.mock.calls[0][2];

    await expect(loader.sanitize("https://example.com/?leak=1", { context: "href" })).rejects.toThrow();
    expect(page.posted).toEqual([{ kind: PREVIEW_PAGE_LINK_KIND, url: "https://example.com/?leak=1" }]);
    // Images and data still go through Vega's own checks.
    await expect(loader.sanitize("data:image/png;base64,AA", { context: "image" })).resolves.toEqual({
      href: "data:image/png;base64,AA",
    });
    expect(sanitize).toHaveBeenCalledTimes(1);
  });

  it("ignores a spec's own embed options, which would override the page's", () => {
    const vegaEmbed = jest.fn((_target: string, _spec: unknown, _options: EmbedOptions) => Promise.resolve());
    const page = previewPageSandbox({ vegaEmbed, ...fakeVega() });
    page.loadPage(buildVegaPageHtml(SOURCES));
    const spec = { mark: "bar", usermeta: { embedOptions: { actions: true, editorUrl: "https://evil.test" }, note: "kept" } };
    page.hand(chartPreviewConfig(JSON.stringify(spec), theme));
    expect(vegaEmbed.mock.calls[0][1]).toMatchObject({ usermeta: { note: "kept" } });
    expect(vegaEmbed.mock.calls[0][1]).not.toHaveProperty("usermeta.embedOptions");
  });

  it("reports a spec that is not JSON", () => {
    const page = previewPageSandbox({ vegaEmbed: jest.fn(), ...fakeVega() });
    page.loadPage(buildVegaPageHtml(SOURCES));
    page.hand(chartPreviewConfig("{not json", theme));
    expect(page.posted).toEqual([{ kind: "chart-error", message: expect.stringContaining("JSON") }]);
  });
});

describe("chartPreviewConfig", () => {
  it("lays the spec out for a phone before the page draws it", () => {
    const config = chartPreviewConfig(
      JSON.stringify({
        $schema: "https://vega.github.io/schema/vega-lite/v5.json",
        mark: "bar",
        encoding: { x: { field: "month", type: "nominal" } },
      }),
      theme,
    );
    expect(config.spec).toContain('"sort":null');
  });

  it("carries the theme and the card's width", () => {
    expect(chartPreviewConfig('{"mark":"bar"}', theme, 300.7)).toEqual({
      spec: '{"mark":"bar"}',
      width: 300,
      vegaTheme: "vox",
      colors: { bg: "#fff", text: "#111", axis: "#666", grid: "#ddd", danger: "#c00" },
    });
    expect(chartPreviewConfig('{"mark":"bar"}', { ...theme, isDark: true }).vegaTheme).toBe("dark");
    expect(chartPreviewConfig('{"mark":"bar"}', theme, 40).width).toBe(120);
  });

  it("hands the page a body it cannot read as written, so the page reports the error", () => {
    expect(chartPreviewConfig("{not json", theme).spec).toBe("{not json");
  });
});
