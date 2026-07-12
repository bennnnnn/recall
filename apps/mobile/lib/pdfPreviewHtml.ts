import { injectPreviewCsp } from "@/lib/previewSandbox";
import type { Theme } from "@/lib/theme";

/** Sandboxed single-page PDF preview via pdf.js in a WebView. */
export function buildPdfPreviewHtml(base64: string, theme: Theme): string {
  const safeB64 = base64.replace(/\\/g, "\\\\").replace(/`/g, "\\`");
  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; padding: 8px; background: ${theme.bg}; color: ${theme.text}; font-family: -apple-system, sans-serif; }
  #err { color: ${theme.danger}; font-size: 12px; display: none; white-space: pre-wrap; padding: 8px; }
  canvas { display: block; margin: 0 auto; max-width: 100%; height: auto; }
</style>
</head>
<body>
<canvas id="page"></canvas>
<div id="err"></div>
<script>
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
  const raw = atob('${safeB64}');
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  pdfjsLib.getDocument({ data: bytes }).promise.then(function(pdf) {
    return pdf.getPage(1);
  }).then(function(page) {
    const scale = Math.min(2, (window.innerWidth - 16) / page.getViewport({ scale: 1 }).width);
    const viewport = page.getViewport({ scale: scale });
    const canvas = document.getElementById('page');
    const ctx = canvas.getContext('2d');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    return page.render({ canvasContext: ctx, viewport: viewport }).promise;
  }).catch(function(err) {
    document.getElementById('err').textContent = 'PDF preview: ' + (err && err.message ? err.message : String(err));
    document.getElementById('err').style.display = 'block';
  });
</script>
</body>
</html>`);
}
