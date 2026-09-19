/**
 * MathJax-SVG formula rendering — headless via liteAdaptor (no DOM), replacing
 * the retired KaTeX/MathJax WebView path. mathjax-full is CJS and lazy-loaded
 * on the first display formula, so its ~1.5MB parser never touches cold start.
 * Results are LRU-cached by `latex|displayMode` so streaming re-renders of a
 * settled formula are free after first paint.
 *
 * The SVG is self-contained (`fontCache: "none"` inlines every glyph path —
 * no `<use>`/defs for react-native-svg to resolve) and uses `currentColor`;
 * the view substitutes the theme color at render time.
 */

/** Cap pathological model latex before MathJax can burn the JS thread. */
const MAX_LATEX_CHARS = 4000;
const CACHE_MAX = 200;

export type SvgMathResult = {
  /** Standalone `<svg …>…</svg>` string (mjx-container wrapper stripped). */
  svg: string;
  widthEx: number;
  heightEx: number;
};

/** Renders latex to the container HTML (`<mjx-container><svg…/></mjx-container>`). */
type SvgMathRenderer = (latex: string, display: boolean) => string;

const cache = new Map<string, SvgMathResult | null>();
let rendererImpl: SvgMathRenderer | null = null;
let rendererPromise: Promise<SvgMathRenderer> | null = null;

function cacheKey(latex: string, display: boolean): string {
  return `${display ? "d" : "i"}|${latex}`;
}

function cacheGet(key: string): SvgMathResult | null | undefined {
  if (!cache.has(key)) return undefined;
  const value = cache.get(key) ?? null;
  // LRU touch.
  cache.delete(key);
  cache.set(key, value);
  return value;
}

function cacheSet(key: string, value: SvgMathResult | null): void {
  cache.delete(key);
  cache.set(key, value);
  while (cache.size > CACHE_MAX) {
    const oldest = cache.keys().next().value;
    if (oldest === undefined) break;
    cache.delete(oldest);
  }
}

/** Extract the `<svg>…</svg>` from a MathJax mjx-container, dropping the
 * vertical-align style react-native-svg has no use for. */
export function extractSvgElement(containerHtml: string): string | null {
  const start = containerHtml.indexOf("<svg");
  const end = containerHtml.lastIndexOf("</svg>");
  if (start < 0 || end < start) return null;
  const svg = containerHtml.slice(start, end + "</svg>".length);
  const tagEnd = svg.indexOf(">");
  if (tagEnd < 0) return null;
  const openTag = svg
    .slice(0, tagEnd)
    .replace(/ style="[^"]*"/, "");
  return openTag + svg.slice(tagEnd);
}

/** Parse `width="20.765ex"` → 20.765. Linear scan, no regex backtracking. */
export function parseExDimension(svg: string, name: "width" | "height"): number | null {
  const attr = `${name}="`;
  const i = svg.indexOf(attr);
  if (i < 0) return null;
  const rest = svg.slice(i + attr.length);
  const end = rest.indexOf("ex");
  if (end <= 0) return null;
  const value = Number.parseFloat(rest.slice(0, end));
  return Number.isFinite(value) && value > 0 ? value : null;
}

async function loadRenderer(): Promise<SvgMathRenderer> {
  const [mathjaxModule, texModule, svgModule, adaptorModule, handlerModule, allPackages] =
    await Promise.all([
      import("mathjax-full/js/mathjax.js"),
      import("mathjax-full/js/input/tex.js"),
      import("mathjax-full/js/output/svg.js"),
      import("mathjax-full/js/adaptors/liteAdaptor.js"),
      import("mathjax-full/js/handlers/html.js"),
      import("mathjax-full/js/input/tex/AllPackages.js"),
    ]);
  const adaptor = adaptorModule.liteAdaptor();
  handlerModule.RegisterHTMLHandler(adaptor);
  const tex = new texModule.TeX({ packages: allPackages.AllPackages });
  const svgJax = new svgModule.SVG({ fontCache: "none" });
  const doc = mathjaxModule.mathjax.document("", {
    InputJax: tex,
    OutputJax: svgJax,
  });
  return (latex: string, display: boolean) => {
    const node = doc.convert(latex, { display }) as unknown;
    return adaptor.innerHTML(node as never);
  };
}

function getRenderer(): Promise<SvgMathRenderer> {
  if (rendererImpl) return Promise.resolve(rendererImpl);
  if (!rendererPromise) {
    rendererPromise = loadRenderer();
    // A failed import must not poison every later formula — allow a retry.
    rendererPromise.catch(() => {
      rendererPromise = null;
    });
  }
  return rendererPromise;
}

/** Cache lookup only: `undefined` = never attempted, `null` = known failure. */
export function peekSvgMath(latex: string, display: boolean): SvgMathResult | null | undefined {
  return cacheGet(cacheKey(latex.trim(), display));
}

/**
 * latex → SVG, or null when the input is empty/pathological or MathJax cannot
 * parse it (callers fall back to the readable native MathText path).
 */
export async function latexToSvgMath(
  latex: string,
  display: boolean,
): Promise<SvgMathResult | null> {
  const trimmed = latex.trim();
  const key = cacheKey(trimmed, display);
  const hit = cacheGet(key);
  if (hit !== undefined) return hit;

  let result: SvgMathResult | null = null;
  if (trimmed && trimmed.length <= MAX_LATEX_CHARS) {
    try {
      const render = await getRenderer();
      const containerHtml = render(trimmed, display);
      const svg = extractSvgElement(containerHtml);
      if (svg) {
        const widthEx = parseExDimension(svg, "width");
        const heightEx = parseExDimension(svg, "height");
        if (widthEx != null && heightEx != null) result = { svg, widthEx, heightEx };
      }
    } catch {
      result = null;
    }
  }
  cacheSet(key, result);
  return result;
}

/** Test hook: inject a fake renderer (and clear the cache) without mathjax. */
export function setSvgMathRendererForTest(renderer: SvgMathRenderer | null): void {
  rendererImpl = renderer;
  rendererPromise = null;
  cache.clear();
}
