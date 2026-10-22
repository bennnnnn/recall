import {
  buildPdfPreviewHtml,
  buildPdfViewerHtml,
  PDF_FILE_PREVIEW_CSP,
  PDF_VIEWER_PAGE,
  pdfPreviewConfigScript,
} from "@/lib/pdfPreviewHtml";
import { PDF_PREVIEW_CSP, PREVIEW_VIEWPORT } from "@/lib/previewSandbox";
import type { Theme } from "@/lib/theme";

const theme = { bg: "#FFFFFF", text: "#111113", danger: "#D92D20" } as Theme;
const SOURCES = { pdf: "/*pdf.js*/", pdfWorker: "/*pdf.js worker*/" };

describe("buildPdfPreviewHtml", () => {
  it("uses the shared zoomable viewport", () => {
    const html = buildPdfPreviewHtml("AAAA", theme, false, SOURCES);
    expect(html).toContain(`content="${PREVIEW_VIEWPORT}"`);
    expect(html).not.toContain("maximum-scale");
  });

  it("carries the PDF and page mode inline and keeps network reads closed", () => {
    const html = buildPdfPreviewHtml("QUJD", theme, true, SOURCES);
    expect(html).toContain('"data":"QUJD"');
    expect(html).toContain('"allPages":true');
    expect(html).toContain(PDF_PREVIEW_CSP);
  });
});

describe("buildPdfViewerHtml", () => {
  it("is one shared page with no PDF in it, allowed to read only local files", () => {
    const html = buildPdfViewerHtml(SOURCES);
    expect(PDF_VIEWER_PAGE.build(SOURCES)).toBe(html);
    expect(PDF_VIEWER_PAGE.libraries).toEqual(["pdf", "pdfWorker"]);
    expect(html).not.toContain("RECALL_PDF = {");
    expect(PDF_FILE_PREVIEW_CSP).toContain("connect-src file:");
    expect(PDF_FILE_PREVIEW_CSP).not.toContain("connect-src 'none'");
    expect(html).toContain(PDF_FILE_PREVIEW_CSP);
  });

  it("runs pdf.js and keeps its worker inert until the page spawns it from a Blob", () => {
    const html = buildPdfViewerHtml(SOURCES);
    expect(html).toContain(`<script>${SOURCES.pdf}</script>`);
    expect(html).toContain(`<script type="text/pdf-worker" id="pdf-worker-src">${SOURCES.pdfWorker}</script>`);
  });

  it("draws every page lazily for the viewer and page 1 for the card", () => {
    const html = buildPdfViewerHtml(SOURCES);
    expect(html).toContain("IntersectionObserver");
    expect(html).toContain("cfg.allPages");
  });

  it.each([
    ["viewer", buildPdfViewerHtml(SOURCES)],
    ["inline", buildPdfPreviewHtml("QUJD", theme, false, SOURCES)],
  ])("loads the %s PDF with eval-compiled fonts off", (_name, html) => {
    expect(html).toContain("getDocument({ data: bytes, isEvalSupported: false })");
  });

  it("ships a page script that parses", () => {
    const html = buildPdfViewerHtml(SOURCES);
    const start = html.lastIndexOf("<script>") + "<script>".length;
    const body = html.slice(start, html.indexOf("</script>", start));
    expect(() => new Function(body)).not.toThrow();
  });

  it("hands each WebView its file and colors before the page script runs", () => {
    const script = pdfPreviewConfigScript({
      src: "file:///cache/att-1-2-doc.pdf",
      allPages: false,
      colors: { bg: "#000", text: "#fff", danger: "#f00" },
    });
    expect(script).toBe(
      'window.RECALL_PDF = {"src":"file:///cache/att-1-2-doc.pdf","allPages":false,"colors":{"bg":"#000","text":"#fff","danger":"#f00"}}; true;',
    );
  });
});
