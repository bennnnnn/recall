/**
 * A rich block's WebView on its kind's page file (lib/previewPageFile.ts):
 * waits for the page, then hands it this block's data. Every block of a kind
 * loads the same file, so a block never builds or sends a page of its own.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  previewPageConfigScript,
  type PreviewPage,
  type PreviewPageConfig,
} from "@/lib/previewPage";
import {
  forgetPreviewPageFile,
  previewPageFile,
  readyPreviewPageFile,
} from "@/lib/previewPageFile";
import type { VendorLibrary } from "@/lib/vendorAssets";
import { allowPreviewPageNavigation, PREVIEW_PAGE_ORIGIN_WHITELIST } from "@/lib/webView";

type PreviewPageState =
  | { status: "loading" | "failed" }
  | { status: "ready"; webViewKey: string; webViewProps: Record<string, unknown> };

/**
 * `config` is the block's data (memoize it). `active` is false when no preview
 * WebView can mount (the card shows its fallback), so no page is written for it.
 */
export function usePreviewPage<L extends VendorLibrary>(
  page: PreviewPage<L>,
  config: PreviewPageConfig,
  active: boolean,
): PreviewPageState {
  const [file, setFile] = useState(() => ({ uri: readyPreviewPageFile(page), failed: false }));

  useEffect(() => {
    if (!active || file.uri || file.failed) return;
    let live = true;
    previewPageFile(page).then(
      (uri) => {
        if (live) setFile({ uri, failed: false });
      },
      () => {
        if (live) setFile({ uri: null, failed: true });
      },
    );
    return () => {
      live = false;
    };
  }, [active, page, file.uri, file.failed]);

  const uri = file.uri;
  const script = useMemo(() => previewPageConfigScript(config), [config]);
  const onShouldStartLoadWithRequest = useCallback(
    (request?: unknown) => uri !== null && allowPreviewPageNavigation(uri, request),
    [uri],
  );
  const onError = useCallback(() => {
    // The file went missing (the system cleared the cache): write it again next time.
    forgetPreviewPageFile(page);
    setFile({ uri: null, failed: true });
  }, [page]);

  const webViewProps = useMemo(
    () => ({
      source: { uri },
      originWhitelist: PREVIEW_PAGE_ORIGIN_WHITELIST,
      onShouldStartLoadWithRequest,
      // Android loads a file:// page only with file access on. iOS reads just
      // the page itself: no allowingReadAccessToURL.
      allowFileAccess: true,
      injectedJavaScriptBeforeContentLoaded: script,
      injectedJavaScript: script,
      onError,
    }),
    [uri, onShouldStartLoadWithRequest, script, onError],
  );

  if (file.failed) return { status: "failed" };
  if (uri === null) return { status: "loading" };
  return { status: "ready", webViewKey: `${uri}\n${script}`, webViewProps };
}
