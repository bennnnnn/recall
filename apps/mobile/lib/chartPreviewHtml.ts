/**
 * The chart page for the preview WebView (vendored Vega / Vega-Lite /
 * Vega-Embed): built once and loaded from a file (lib/previewPageFile.ts);
 * each block hands it its spec with `chartPreviewConfig`.
 *
 * Extracted so CSP injection and spec layout are unit-testable without ChartBlock.
 */
import { previewPageStartScript, type PreviewPage } from "@/lib/previewPage";
import { CHART_PREVIEW_CSP, injectPreviewCsp, inlineScript } from "@/lib/previewSandbox";
import type { Theme } from "@/lib/theme";
import { parseChartBody, seriesChartToVegaLite } from "@/lib/chartSeriesSpec";

type ChartPreviewTheme = Pick<
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
function preferHorizontalCategoryBars(spec: Record<string, unknown>): void {
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
    const xOff = enc.xOffset;
    const yOff = enc.yOffset;
    if (xOff !== undefined || yOff !== undefined) {
      enc.xOffset = yOff;
      enc.yOffset = xOff;
      if (enc.xOffset === undefined) delete enc.xOffset;
      if (enc.yOffset === undefined) delete enc.yOffset;
    }
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
  const parsed = parseChartBody(raw);
  if (parsed === null) return raw;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return JSON.stringify(parsed);
  const record = parsed as Record<string, unknown>;
  const spec = seriesChartToVegaLite(record) ?? record;
  normalizeChartSpec(spec);
  return JSON.stringify(spec);
}

type VegaLibrary = "vega" | "vegaLite" | "vegaEmbed";

/** Runs in the WebView with one chart's config. */
const START = `function (config) {
  var colors = config.colors;
  var style = document.documentElement.style;
  style.setProperty('--bg', colors.bg);
  style.setProperty('--danger', colors.danger);
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
    // Vega follows a mark's href itself: its loader hands the link to the app instead.
    var loader = vega.loader();
    var sanitize = loader.sanitize;
    loader.sanitize = function(uri, options) {
      if (options && options.context === 'href') {
        postLink(uri);
        return Promise.reject(new Error('The app opens links.'));
      }
      return sanitize.call(loader, uri, options);
    };
    var parsed = JSON.parse(config.spec);
    // A spec's own embed options would override these (actions, editor URL, loader).
    if (parsed && parsed.usermeta) delete parsed.usermeta.embedOptions;
    var themedConfig = {
      background: colors.bg,
      axis: { domainColor: colors.axis, labelColor: colors.text, titleColor: colors.text, tickColor: colors.axis, gridColor: colors.grid },
      legend: { labelColor: colors.text, titleColor: colors.text },
      title: { color: colors.text },
      view: { stroke: colors.axis },
    };
    parsed.config = Object.assign({}, themedConfig, parsed.config || {});
    // The width is the card's, axes and labels included: a plain width sized only the
    // plot, and the y axis pushed its right edge out of the card.
    if (!parsed.autosize) parsed.autosize = { type: 'fit-x', contains: 'padding' };
    vegaEmbed('#chart', parsed, {
      actions: false,
      tooltip: false,
      renderer: 'svg',
      width: config.width,
      theme: config.vegaTheme,
      config: themedConfig,
      loader: loader,
    }).then(function() {
      requestAnimationFrame(reportSize);
    }).catch(function(err) { reportError(err && err.message ? err.message : String(err)); });
  } catch (e) {
    reportError(e && e.message ? e.message : String(e));
  }
}`;

/** The page that renders a Vega / Vega-Lite spec via vendored Vega-Embed. */
export function buildVegaPageHtml(sources: Readonly<Record<VegaLibrary, string>>): string {
  return injectPreviewCsp(
    `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>${inlineScript(sources.vega)}</script>
<script>${inlineScript(sources.vegaLite)}</script>
<script>${inlineScript(sources.vegaEmbed)}</script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { overflow: hidden; }
  body { padding: 8px; font-family: -apple-system, sans-serif; background: var(--bg); }
  #chart { width: 100%; max-width: 100%; overflow: hidden; }
  #error { color: var(--danger); padding: 16px; font-size: 13px; display: none; white-space: pre-wrap; word-break: break-word; }
</style>
</head>
<body>
<div id="chart"></div>
<div id="error"></div>
<script>${previewPageStartScript(START)}</script>
</body>
</html>`,
    CHART_PREVIEW_CSP,
  );
}

export const CHART_PAGE: PreviewPage<VegaLibrary> = {
  name: "chart",
  libraries: ["vega", "vegaLite", "vegaEmbed"],
  build: buildVegaPageHtml,
};

/** What one chart's WebView hands the page: the spec laid out for a phone, and the theme. */
type ChartPreviewConfig = {
  /** JSON text; the page parses it, so a body it cannot read shows as a chart error. */
  spec: string;
  width: number;
  vegaTheme: "dark" | "vox";
  colors: { bg: string; text: string; axis: string; grid: string; danger: string };
};

export function chartPreviewConfig(
  spec: string,
  theme: ChartPreviewTheme,
  plotWidth = 320,
): ChartPreviewConfig {
  return {
    spec: specPayloadForEmbed(spec),
    width: Math.max(120, Math.floor(plotWidth)),
    vegaTheme: theme.isDark ? "dark" : "vox",
    colors: {
      bg: theme.bg,
      text: theme.text,
      axis: theme.textSecondary,
      grid: theme.border,
      danger: theme.danger,
    },
  };
}
