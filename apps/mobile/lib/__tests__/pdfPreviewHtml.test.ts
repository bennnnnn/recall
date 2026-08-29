import { buildPdfPreviewHtml } from "@/lib/pdfPreviewHtml";
import { PREVIEW_VIEWPORT } from "@/lib/previewSandbox";
import type { Theme } from "@/lib/theme";

const theme = { bg: "#FFFFFF", text: "#111113", danger: "#D92D20" } as Theme;

describe("buildPdfPreviewHtml", () => {
  it("uses the shared zoomable viewport", () => {
    const html = buildPdfPreviewHtml("AAAA", theme);
    expect(html).toContain(`content="${PREVIEW_VIEWPORT}"`);
    expect(html).not.toContain("maximum-scale");
  });
});
