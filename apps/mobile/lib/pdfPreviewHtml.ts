import type { PreviewPage } from "@/lib/previewPage";
import { injectPreviewCsp, PDF_PREVIEW_CSP, PREVIEW_VIEWPORT, inlineScript } from "@/lib/previewSandbox";
import type { Theme } from "@/lib/theme";

/** pdf.js and its worker, which the page inlines. */
type PdfLibrary = "pdf" | "pdfWorker";
export type PdfSources = Readonly<Record<PdfLibrary, string>>;

/** What one preview shows; the page reads it as `window.RECALL_PDF`. */
type PdfPreviewConfig = {
  /** A local file:// PDF the page reads itself (the file-backed page). */
  src?: string;
  /** The PDF as base64 (the inline fallback, where the WebView cannot read files). */
  data?: string;
  /** Every page, drawn as it scrolls near; otherwise page 1 only. */
  allPages: boolean;
  colors: { bg: string; text: string; danger: string };
};

/** The page posts this when it could not show the PDF. */
export const PDF_PREVIEW_ERROR = "pdf-error";

/** The file-backed page reads its PDF from disk; nothing else may be fetched. */
export const PDF_FILE_PREVIEW_CSP = PDF_PREVIEW_CSP.replace("connect-src 'none'", "connect-src file:");

export function pdfPreviewColors(theme: Theme): PdfPreviewConfig["colors"] {
  return { bg: theme.bg, text: theme.text, danger: theme.danger };
}

/** Sets the config before the page script runs (`injectedJavaScriptBeforeContentLoaded`). */
export function pdfPreviewConfigScript(config: PdfPreviewConfig): string {
  return `window.RECALL_PDF = ${JSON.stringify(config)}; true;`;
}

// Runs inside the WebView. Pages are drawn when they come near the viewport and
// cleared when they move far away, so a long PDF never holds every page's pixels.
const PAGE_SCRIPT = `(function () {
  var cfg = window.RECALL_PDF || {};
  var colors = cfg.colors || {};
  var style = document.documentElement.style;
  if (colors.bg) style.setProperty('--bg', colors.bg);
  if (colors.text) style.setProperty('--text', colors.text);
  if (colors.danger) style.setProperty('--danger', colors.danger);
  var errBox = document.getElementById('err');
  var pages = document.getElementById('pages');
  function post(type) {
    if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify({ type: type }));
  }
  function fail(err) {
    errBox.textContent = 'PDF preview: ' + (err && err.message ? err.message : String(err));
    errBox.style.display = 'block';
    post('${PDF_PREVIEW_ERROR}');
  }
  // The worker source sits in a non-executable tag; a Blob URL spawns it with no fetch.
  var workerText = document.getElementById('pdf-worker-src').textContent;
  pdfjsLib.GlobalWorkerOptions.workerSrc = URL.createObjectURL(new Blob([workerText], { type: 'application/javascript' }));
  function loadBytes() {
    if (cfg.data) {
      var raw = atob(cfg.data);
      var bytes = new Uint8Array(raw.length);
      for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      return Promise.resolve(bytes);
    }
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open('GET', cfg.src);
      xhr.responseType = 'arraybuffer';
      xhr.onload = function () {
        if ((xhr.status === 0 || xhr.status === 200) && xhr.response) resolve(new Uint8Array(xhr.response));
        else reject(new Error('Could not read the file'));
      };
      xhr.onerror = function () { reject(new Error('Could not read the file')); };
      xhr.send();
    });
  }
  var ratio = Math.min(2, window.devicePixelRatio || 1);
  function fit(page) { return (window.innerWidth - 16) / page.getViewport({ scale: 1 }).width; }
  function slot(page) {
    var canvas = document.createElement('canvas');
    var size = page.getViewport({ scale: fit(page) });
    canvas.style.width = size.width + 'px';
    canvas.style.height = size.height + 'px';
    pages.appendChild(canvas);
    return canvas;
  }
  function draw(page, canvas) {
    var css = page.getViewport({ scale: fit(page) });
    var viewport = page.getViewport({ scale: fit(page) * ratio });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = css.width + 'px';
    canvas.style.height = css.height + 'px';
    return page.render({ canvasContext: canvas.getContext('2d'), viewport: viewport });
  }
  function lazyPages(pdf, first) {
    var turns = {};
    var tasks = {};
    function show(n, canvas) {
      if (turns[n]) return;
      var turn = turns[n] = {};
      pdf.getPage(n).then(function (page) {
        if (turns[n] !== turn) return;
        tasks[n] = draw(page, canvas);
        return tasks[n].promise;
      }).catch(function (err) {
        if (!err || err.name !== 'RenderingCancelledException') fail(err);
      });
    }
    function hide(n, canvas) {
      if (!turns[n]) return;
      turns[n] = null;
      if (tasks[n]) tasks[n].cancel();
      tasks[n] = null;
      canvas.width = 0;
      canvas.height = 0;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var n = Number(entry.target.getAttribute('data-page'));
        if (entry.isIntersecting) show(n, entry.target);
        else hide(n, entry.target);
      });
    }, { rootMargin: '150% 0px' });
    for (var n = 1; n <= pdf.numPages; n++) {
      // Page 1's size stands in for the rest until each is drawn.
      var canvas = slot(first);
      canvas.setAttribute('data-page', String(n));
      observer.observe(canvas);
    }
  }
  loadBytes().then(function (bytes) {
    // No eval-compiled font paths: pdf.js 3.x runs a crafted font as script (CVE-2024-4367),
    // and this page can read files.
    return pdfjsLib.getDocument({ data: bytes, isEvalSupported: false }).promise;
  }).then(function (pdf) {
    return pdf.getPage(1).then(function (first) {
      if (cfg.allPages) return lazyPages(pdf, first);
      return draw(first, slot(first)).promise;
    });
  }).catch(fail);
})();`;

function pdfPageHtml(csp: string, configScript: string, sources: PdfSources): string {
  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="${PREVIEW_VIEWPORT}">
${configScript}<script>${inlineScript(sources.pdf)}</script>
<script type="text/pdf-worker" id="pdf-worker-src">${inlineScript(sources.pdfWorker)}</script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; padding: 8px; background: var(--bg, #fff); color: var(--text, #111); font-family: -apple-system, sans-serif; }
  #err { color: var(--danger, #d92d20); font-size: 12px; display: none; white-space: pre-wrap; padding: 8px; }
  canvas { display: block; margin: 0 auto 8px; max-width: 100%; background: #fff; }
</style>
</head>
<body>
<div id="pages"></div>
<div id="err"></div>
<script>${PAGE_SCRIPT}</script>
</body>
</html>`, csp);
}

/**
 * The file-backed page: one document for every preview, written to disk once
 * per version (lib/previewPageFile.ts). Each WebView hands it its PDF path and
 * colors with `pdfPreviewConfigScript`.
 */
export function buildPdfViewerHtml(sources: PdfSources): string {
  return pdfPageHtml(PDF_FILE_PREVIEW_CSP, "", sources);
}

export const PDF_VIEWER_PAGE: PreviewPage<PdfLibrary> = {
  name: "pdf-viewer",
  libraries: ["pdf", "pdfWorker"],
  build: buildPdfViewerHtml,
  // Earlier versions rewrote one unversioned viewer page in the cache root each run.
  formerFile: "pdf-viewer.html",
};

/** Inline fallback for WebViews that cannot read local files: the PDF rides in the page. */
export function buildPdfPreviewHtml(
  base64: string,
  theme: Theme,
  allPages: boolean,
  sources: PdfSources,
): string {
  const config: PdfPreviewConfig = { data: base64, allPages, colors: pdfPreviewColors(theme) };
  return pdfPageHtml(
    PDF_PREVIEW_CSP,
    `<script>${inlineScript(`window.RECALL_PDF = ${JSON.stringify(config)};`)}</script>\n`,
    sources,
  );
}
