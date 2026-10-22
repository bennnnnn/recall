import { useCallback, useEffect, useMemo, useState } from "react";
import { cacheDirectory, EncodingType, readAsStringAsync } from "expo-file-system/legacy";

import { useAccountSession } from "@/contexts/accountSession";
import { ensureLocalAttachmentFile } from "@/features/attachments/model/downloadChatAttachment";
import {
  buildPdfPreviewHtml,
  PDF_PREVIEW_ERROR,
  PDF_VIEWER_PAGE,
  pdfPreviewColors,
  pdfPreviewConfigScript,
  type PdfSources,
} from "@/lib/pdfPreviewHtml";
import { forgetPreviewPageFile, previewPageFile } from "@/lib/previewPageFile";
import { useTheme } from "@/lib/theme";
import { readVendorLibraries } from "@/lib/vendorAssets";
import { getPreviewWebView, STATIC_HTML_ORIGIN_WHITELIST } from "@/lib/webView";

/** The file-backed page is a file:// document reading a file:// PDF. */
const FILE_ORIGIN_WHITELIST = [...STATIC_HTML_ORIGIN_WHITELIST, "file://*"];

/** A viewer page that will not load (the system cleared the cache) is written and loaded once more. */
const VIEWER_RETRIES = 1;

type Loaded =
  | { key: string; kind: "file"; viewer: string; pdf: string }
  | { key: string; kind: "html"; base64: string; sources: PdfSources };

type PdfPreview =
  | { status: "idle" | "loading" | "failed" }
  | { status: "ready"; webViewKey: string; webViewProps: Record<string, unknown> };

/**
 * One PDF preview for the card (page 1) and the viewer (every page). The PDF
 * is downloaded natively into the attachment cache, shared with Share and with
 * other previews of the same file, and the download stops when the preview
 * closes. react-native-webview reads both the pdf.js page and the PDF from
 * disk; other WebViews, or one that cannot read files, get the PDF inline.
 */
export function usePdfPreview(options: {
  uri: string | null;
  fileName: string;
  enabled: boolean;
  allPages: boolean;
}): PdfPreview {
  const { uri, fileName, enabled, allPages } = options;
  const { account, getToken } = useAccountSession();
  const theme = useTheme();
  const [fileUnreadable, setFileUnreadable] = useState(false);
  const [viewerRetries, setViewerRetries] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failedKey, setFailedKey] = useState<string | null>(null);
  const useFile = getPreviewWebView()?.mode === "rnc" && !fileUnreadable;
  const key = `${uri}|${useFile ? "file" : "html"}`;

  useEffect(() => {
    setFileUnreadable(false);
    setViewerRetries(0);
  }, [uri]);

  useEffect(() => {
    if (!enabled || !uri) return;
    const controller = new AbortController();
    setFailedKey(null);
    void (async () => {
      try {
        const pdf = await ensureLocalAttachmentFile({ uri, token: getToken(), fileName, signal: controller.signal });
        const next: Loaded = useFile
          ? { key, kind: "file", viewer: await previewPageFile(PDF_VIEWER_PAGE), pdf }
          : {
              key,
              kind: "html",
              base64: await readAsStringAsync(pdf, { encoding: EncodingType.Base64 }),
              sources: await readVendorLibraries(PDF_VIEWER_PAGE.libraries),
            };
        if (!controller.signal.aborted) setLoaded(next);
      } catch {
        if (!controller.signal.aborted) setFailedKey(key);
      }
    })();
    return () => controller.abort();
  }, [enabled, uri, account, getToken, fileName, useFile, key, viewerRetries]);

  const onMessage = useCallback((event: { nativeEvent?: { data?: unknown } }) => {
    const data = event.nativeEvent?.data;
    if (typeof data !== "string" || !data.includes(PDF_PREVIEW_ERROR)) return;
    // The WebView could not read the file (or run the page from disk): inline it once.
    if (useFile) setFileUnreadable(true);
  }, [useFile]);

  const current = loaded?.key === key ? loaded : null;
  const viewer = current?.kind === "file" ? current.viewer : null;

  const onViewerError = useCallback(() => {
    // The viewer page went missing: write it again and load it once more, then inline the PDF.
    if (viewer) forgetPreviewPageFile(PDF_VIEWER_PAGE, viewer);
    setLoaded(null);
    if (viewerRetries < VIEWER_RETRIES) setViewerRetries(viewerRetries + 1);
    else setFileUnreadable(true);
  }, [viewer, viewerRetries]);

  const colors = pdfPreviewColors(theme);
  const colorKey = `${colors.bg}|${colors.text}|${colors.danger}`;
  const html = useMemo(
    () => (current?.kind === "html" ? buildPdfPreviewHtml(current.base64, theme, allPages, current.sources) : null),
    [current, allPages, theme],
  );

  if (!enabled || !uri) return { status: "idle" };
  if (failedKey === key && !current) return { status: "failed" };
  if (!current) return { status: "loading" };
  if (current.kind === "html") {
    return {
      status: "ready",
      webViewKey: `${key}|${colorKey}`,
      webViewProps: { source: { html }, originWhitelist: STATIC_HTML_ORIGIN_WHITELIST, onMessage },
    };
  }
  return {
    status: "ready",
    webViewKey: `${key}|${colorKey}|${allPages}|${viewerRetries}`,
    webViewProps: {
      source: { uri: current.viewer },
      injectedJavaScriptBeforeContentLoaded: pdfPreviewConfigScript({ src: current.pdf, allPages, colors }),
      originWhitelist: FILE_ORIGIN_WHITELIST,
      allowFileAccess: true,
      allowFileAccessFromFileURLs: true,
      allowingReadAccessToURL: cacheDirectory ?? undefined,
      onMessage,
      onError: onViewerError,
    },
  };
}
