import { buildVegaHtml } from "@/lib/chartPreviewHtml";
import { CHART_PREVIEW_CSP, PREVIEW_CSP } from "@/lib/previewSandbox";

const theme = {
  bg: "#fff",
  text: "#111",
  textSecondary: "#666",
  border: "#ddd",
  danger: "#c00",
  isDark: false,
};

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
});
