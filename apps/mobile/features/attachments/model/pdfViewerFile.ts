import { cacheDirectory, writeAsStringAsync } from "expo-file-system/legacy";

import { buildPdfViewerHtml } from "@/lib/pdfPreviewHtml";

let written: Promise<string> | null = null;

/**
 * The pdf.js page (~1.4 MB) on disk, written once per app run so every PDF
 * card and viewer loads the same file instead of carrying it in a string.
 * Rewritten each run, so an app update never pairs old pdf.js with new code.
 */
export function pdfViewerFile(): Promise<string> {
  written ??= (async () => {
    if (!cacheDirectory) throw new Error("Storage unavailable.");
    const path = `${cacheDirectory}pdf-viewer.html`;
    await writeAsStringAsync(path, buildPdfViewerHtml());
    return path;
  })().catch((error: unknown) => {
    written = null;
    throw error;
  });
  return written;
}
