/**
 * Self-contained Vega-Lite preview HTML for the chart WebView.
 *
 * Extracted so CSP injection and spec layout are unit-testable without ChartBlock.
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

export type ChartPreviewTheme = Pick<
  Theme,
  "bg" | "text" | "textSecondary" | "border" | "danger" | "isDark"
>;

const COMPOSITE_KEYS = ["layer", "hconcat", "vconcat", "concat"] as const;
const BAND_PX = 28;
const BAND_HEIGHT_MIN = 120;
const BAND_HEIGHT_MAX = 280;

function markIsBar(mark: unknown): boolean {
  if (mark === "bar") return true;
  if (mark && typeof mark === "object" && !Array.isArray(mark)) {
    return (mark as { type?: unknown }).type === "bar";
  }
  return false;
}

function channelType(ch: unknown): string | undefined {
  if (!ch || typeof ch !== "object" || Array.isArray(ch)) return undefined;
  const t = (ch as { type?: unknown }).type;
  return typeof t === "string" ? t : undefined;
}

function isCategoryType(t: string | undefined): boolean {
  return t === "nominal" || t === "ordinal";
}

function applyNominalSort(encoding: Record<string, unknown>, key: string): void {
  const ch = encoding[key];
  if (!ch || typeof ch !== "object" || Array.isArray(ch)) return;
  const chan = ch as Record<string, unknown>;
  if ("sort" in chan) return;
  if (chan.type === "quantitative" || chan.type === "temporal") return;
  chan.sort = null;
}

/**
 * Named categories on x become unreadable on a phone (labels clip under the
 * plot). ChatGPT-shaped: months/items on y, values on x.
 */
export function preferHorizontalCategoryBars(spec: Record<string, unknown>): void {
  if (!markIsBar(spec.mark)) return;
  const encoding = spec.encoding;
  if (!encoding || typeof encoding !== "object" || Array.isArray(encoding)) return;
  const enc = encoding as Record<string, unknown>;
  const xt = channelType(enc.x);
  const yt = channelType(enc.y);
  if (isCategoryType(xt) && yt === "quantitative" && !isCategoryType(yt)) {
    const x = enc.x;
    enc.x = enc.y;
    enc.y = x;
  }
}

function setHorizontalBandHeight(spec: Record<string, unknown>): void {
  if (!markIsBar(spec.mark) || spec.height != null) return;
  const encoding = spec.encoding;
  if (!encoding || typeof encoding !== "object" || Array.isArray(encoding)) return;
  if (!isCategoryType(channelType((encoding as Record<string, unknown>).y))) return;
  const data = spec.data;
  const values =
    data && typeof data === "object" && !Array.isArray(data)
      ? (data as { values?: unknown }).values
      : undefined;
  const n = Array.isArray(values) ? values.length : 6;
  spec.height = Math.min(BAND_HEIGHT_MAX, Math.max(BAND_HEIGHT_MIN, n * BAND_PX));
}

function normalizeUnit(spec: Record<string, unknown>): void {
  preferHorizontalCategoryBars(spec);
  const encoding = spec.encoding;
  if (encoding && typeof encoding === "object" && !Array.isArray(encoding)) {
    const enc = encoding as Record<string, unknown>;
    applyNominalSort(enc, "x");
    applyNominalSort(enc, "y");
  }
  setHorizontalBandHeight(spec);
}

/** Layout + category order for a Vega-Lite spec (mutates). */
export function normalizeChartSpec(spec: Record<string, unknown>): void {
  normalizeUnit(spec);
  for (const key of COMPOSITE_KEYS) {
    const kids = spec[key];
    if (!Array.isArray(kids)) continue;
    for (const child of kids) {
      if (child && typeof child === "object" && !Array.isArray(child)) {
        normalizeChartSpec(child as Record<string, unknown>);
      }
    }
  }
  const nested = spec.spec;
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    normalizeChartSpec(nested as Record<string, unknown>);
  }
}

function specPayloadForEmbed(raw: string): string {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      normalizeChartSpec(parsed as Record<string, unknown>);
    }
    return JSON.stringify(parsed);
  } catch {
    return raw;
  }
}

/** Build a page that renders a Vega / Vega-Lite spec via vendored Vega-Embed. */
export function buildVegaHtml(
  spec: string,
  theme: ChartPreviewTheme,
  plotWidth = 320,
): string {
  const safeSpec = escapeForInlineJsTemplate(specPayloadForEmbed(spec));
  const vegaTheme = theme.isDark ? "dark" : "vox";
  const axisColor = theme.textSecondary;
  const textColor = theme.text;
  const gridColor = theme.border;
  const width = Math.max(120, Math.floor(plotWidth));
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
  html, body { overflow: hidden; }
  body { padding: 8px; font-family: -apple-system, sans-serif; background: ${theme.bg}; }
  #chart { width: 100%; max-width: 100%; overflow: hidden; }
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
  function reportSize() {
    var svg = document.querySelector('#chart svg');
    var h = 0;
    if (svg) {
      var box = svg.getBoundingClientRect();
      h = box.height;
    }
    if (!h) h = document.body.scrollHeight;
    try { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify({ kind: 'chart-size', height: Math.ceil(h + 16) })); } catch (e) {}
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
      tooltip: false,
      renderer: 'svg',
      width: ${width},
      theme: ${JSON.stringify(vegaTheme)},
      config: themedConfig,
    }).then(function() {
      requestAnimationFrame(reportSize);
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
