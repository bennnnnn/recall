/**
 * MathSvgBridge — shared hidden WebView that runs the vendored MathJax
 * `tex2svg` and returns an SVG string, which the UI renders with
 * `react-native-svg`'s `<SvgXml>`. Goal: cut N visible math WebViews
 * (one per block, no pooling today) down to 1 hidden shared one, and
 * display the result natively (no on-screen flash / async height dance).
 *
 * SPIKE — default OFF (`MATH_SVG_NATIVE_ENABLED = false`). Flip on-device
 * to A/B against the current visible-WebView path in `MathFormulaWebView`.
 * The host (`MathSvgBridgeHost`) must be mounted once for the bridge to
 * resolve; until then `requestMathSvg` rejects so callers fall back.
 */

import { injectPreviewCsp, MATH_PREVIEW_CSP, inlineScript } from "@/lib/previewSandbox";

/** Flip on-device to test the SVG-native path. Off by default. */
export const MATH_SVG_NATIVE_ENABLED = false;

/** Max in-flight renders before we reject new ones (backpressure). */
const MAX_PENDING = 16;
/** Hard cap cached SVGs (LRU-ish; we just delete oldest on overflow). */
const MAX_CACHE = 256;

type Pending = {
  resolve: (svg: string) => void;
  reject: (err: Error) => void;
  latex: string;
};

let nextId = 1;
const pending = new Map<number, Pending>();
const cache = new Map<string, string>();
let postFn: ((js: string) => void) | null = null;
let ready = false;

function cacheKey(latex: string): string {
  return latex.trim();
}

function evictIfNeeded(): void {
  if (cache.size > MAX_CACHE) {
    const oldest = cache.keys().next().value;
    if (oldest != null) cache.delete(oldest);
  }
}

/** The host calls this with the WebView's `injectJavaScript` fn + readiness. */
export function setBridgeTransport(post: ((js: string) => void) | null, isReady: boolean): void {
  postFn = post;
  ready = isReady && post != null;
  if (!ready) {
    // Reject anything still pending so callers fall back immediately.
    for (const p of pending.values()) p.reject(new Error("math-svg-bridge-not-ready"));
    pending.clear();
  }
}

/** Resolve a render returned from the WebView. */
export function handleBridgeMessage(raw: string): void {
  let parsed: { id?: number; svg?: string; error?: string };
  try {
    parsed = JSON.parse(raw);
  } catch {
    return;
  }
  const id = parsed.id;
  const p = id != null ? pending.get(id) : undefined;
  if (p == null || id == null) return;
  pending.delete(id);
  if (parsed.error) {
    p.reject(new Error(parsed.error));
    return;
  }
  if (typeof parsed.svg === "string" && parsed.svg.length > 0) {
    cache.set(cacheKey(p.latex), parsed.svg);
    evictIfNeeded();
    p.resolve(parsed.svg);
    return;
  }
  p.reject(new Error("math-svg-empty"));
}

/**
 * Request an SVG for `latex`. Resolves from cache instantly when available,
 * otherwise posts to the hidden WebView and awaits its reply. Rejects if the
 * bridge isn't ready or the queue is full — callers must fall back.
 */
export function requestMathSvg(latex: string): Promise<string> {
  const key = cacheKey(latex);
  const hit = cache.get(key);
  if (hit != null) return Promise.resolve(hit);
  if (!ready || postFn == null) return Promise.reject(new Error("math-svg-bridge-not-ready"));
  if (pending.size >= MAX_PENDING) return Promise.reject(new Error("math-svg-bridge-busy"));
  const id = nextId++;
  return new Promise<string>((resolve, reject) => {
    pending.set(id, { resolve, reject, latex });
    const safeLatex = JSON.stringify(latex);
    // window.__renderSvg is defined by buildMathSvgBridgeHtml. postFn is
    // non-null here (we checked `ready` above, which requires postFn != null).
    postFn?.(`window.__renderSvg(${id}, ${safeLatex});`);
  });
}

export function isMathSvgBridgeReady(): boolean {
  return ready;
}

/** Build the HTML for the single hidden host WebView. Lazy-loads the
 *  ~2MB MathJax vendor only when actually called (flag on + bridge mounting),
 * so it stays OUT of the main bundle's cold path. */
export async function buildMathSvgBridgeHtml(): Promise<string> {
  const { MATHJAX_TEX_SVG_JS } = await import("@/lib/vendor/mathjaxTexSvgJs");
  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>html,body{margin:0;padding:0;background:transparent;}#h{position:absolute;left:-9999px;top:-9999px;width:1px;height:1px;overflow:hidden;}</style>
</head>
<body>
<div id="h"></div>
<script>
  var MathJax = {
    loader: { load: ["[tex]/ams", "[tex]/noerrors", "[tex]/noundefined"] },
    tex: {
      packages: { "[+]": ["ams", "noerrors", "noundefined"] },
      inlineMath: [], displayMath: []
    },
    startup: { typeset: false }
  };
  window.__renderSvg = function(id, latex) {
    try {
      MathJax.tex2svgPromise(latex, { display: true }).then(function(node) {
        var svg = node && node.querySelector ? node.querySelector("svg") : null;
        var outer = svg ? svg.outerHTML : "";
        window.ReactNativeWebView.postMessage(JSON.stringify({ id: id, svg: outer }));
      }).catch(function(err) {
        window.ReactNativeWebView.postMessage(JSON.stringify({
          id: id, error: (err && err.message) ? err.message : String(err)
        }));
      });
    } catch (e) {
      window.ReactNativeWebView.postMessage(JSON.stringify({
        id: id, error: (e && e.message) ? e.message : String(e)
      }));
    }
  };
  window.__markReady = function() {
    window.ReactNativeWebView.postMessage(JSON.stringify({ ready: true }));
  };
  MathJax.startup.promise.then(function() { window.__markReady(); });
</script>
<script>${inlineScript(MATHJAX_TEX_SVG_JS)}</script>
</body>
</html>`, MATH_PREVIEW_CSP);
}
