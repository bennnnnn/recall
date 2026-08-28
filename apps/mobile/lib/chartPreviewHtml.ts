/**
 * Self-contained Vega-Lite preview HTML for the chart WebView.
 *
 * Extracted so CSP injection is unit-testable without mounting ChartBlock.
 */
import {
  CHART_PREVIEW_CSP,
  escapeForInlineJsTemplate,
  injectPreviewCsp,
  inlineScript,
} from "@/lib/previewSandbox";
import type { Theme } from "@/lib/theme";
import { VEGA_EMBED_MIN_JS } from "@/lib/vendor/vegaEmbedMinJs";
import { VEGA_LITE_MIN_JS } from "@/lib/vendor/vegaLiteMinJs";
import { VEGA_MIN_JS } from "@/lib/vendor/vegaMinJs";

export const CHART_PREVIEW_HEIGHT = 350;
export const CHART_WEBVIEW_WIDTH = 720;

export type ChartPreviewTheme = Pick<
  Theme,
  "bg" | "text" | "textSecondary" | "border" | "danger" | "isDark"
>;

const COMPOSITE_KEYS = ["layer", "hconcat", "vconcat", "concat"] as const;

/**
 * Vega-Lite alphabetizes nominal x by default, so Jan–Jun rainfall becomes
 * Apr, Feb, Jan, Jun, Mar, May. `sort: null` keeps `data.values` order.
 * Does not override an explicit sort, or quantitative/temporal x.
 */
export function preserveChartCategoryOrder(spec: Record<string, unknown>): void {
  const encoding = spec.encoding;
  if (encoding && typeof encoding === "object" && !Array.isArray(encoding)) {
    const x = (encoding as Record<string, unknown>).x;
    if (x && typeof x === "object" && !Array.isArray(x)) {
      const chan = x as Record<string, unknown>;
      if (!("sort" in chan) && chan.type !== "quantitative" && chan.type !== "temporal") {
        chan.sort = null;
      }
    }
  }
  for (const key of COMPOSITE_KEYS) {
    const kids = spec[key];
    if (!Array.isArray(kids)) continue;
    for (const child of kids) {
      if (child && typeof child === "object" && !Array.isArray(child)) {
        preserveChartCategoryOrder(child as Record<string, unknown>);
      }
    }
  }
  const nested = spec.spec;
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    preserveChartCategoryOrder(nested as Record<string, unknown>);
  }
}

function specPayloadForEmbed(raw: string): string {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      preserveChartCategoryOrder(parsed as Record<string, unknown>);
    }
    return JSON.stringify(parsed);
  } catch {
    return raw;
  }
}

/** Build a page that renders a Vega / Vega-Lite spec via vendored Vega-Embed. */
export function buildVegaHtml(spec: string, theme: ChartPreviewTheme): string {
  const safeSpec = escapeForInlineJsTemplate(specPayloadForEmbed(spec));
  const vegaTheme = theme.isDark ? "dark" : "vox";
  const axisColor = theme.textSecondary;
  const textColor = theme.text;
  const gridColor = theme.border;
  return injectPreviewCsp(
    `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>${inlineScript(VEGA_MIN_JS)}</script>
<script>${inlineScript(VEGA_LITE_MIN_JS)}</script>
<script>${inlineScript(VEGA_EMBED_MIN_JS)}</script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { padding: 8px; font-family: -apple-system, sans-serif; background: ${theme.bg}; }
  #chart { width: 100%; max-width: 100%; }
  #error { color: ${theme.danger}; padding: 16px; font-size: 13px; display: none; white-space: pre-wrap; word-break: break-word; }
</style>
</head>
<body>
<div id="chart"></div>
<div id="error"></div>
<script>
  const spec = \`${safeSpec}\`;
  function reportError(msg) {
    try { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify({ kind: 'chart-error', message: msg })); } catch (e) {}
    var el = document.getElementById('error');
    el.textContent = 'Chart error: ' + msg;
    el.style.display = 'block';
  }
  try {
    const parsed = JSON.parse(spec);
    const themedConfig = {
      background: ${JSON.stringify(theme.bg)},
      axis: { domainColor: ${JSON.stringify(axisColor)}, labelColor: ${JSON.stringify(textColor)}, titleColor: ${JSON.stringify(textColor)}, tickColor: ${JSON.stringify(axisColor)}, gridColor: ${JSON.stringify(gridColor)} },
      legend: { labelColor: ${JSON.stringify(textColor)}, titleColor: ${JSON.stringify(textColor)} },
      title: { color: ${JSON.stringify(textColor)} },
      view: { stroke: ${JSON.stringify(axisColor)} },
    };
    parsed.config = Object.assign({}, themedConfig, parsed.config || {});
    vegaEmbed('#chart', parsed, {
      actions: false,
      renderer: 'svg',
      width: ${CHART_WEBVIEW_WIDTH - 16},
      height: ${CHART_PREVIEW_HEIGHT - 24},
      theme: ${JSON.stringify(vegaTheme)},
      config: themedConfig,
    }).catch(function(err) { reportError(err && err.message ? err.message : String(err)); });
  } catch (e) {
    reportError(e && e.message ? e.message : String(e));
  }
</script>
</body>
</html>`,
    CHART_PREVIEW_CSP,
  );
}
