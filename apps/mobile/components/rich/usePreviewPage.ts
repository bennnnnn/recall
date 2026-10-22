/**
 * A rich block's WebView on its kind's page file (lib/previewPageFile.ts):
 * waits for the page, then hands it this block's data. Every block of a kind
 * loads the same file, so a block never builds or sends a page of its own.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import {
  previewPageConfigScript,
  previewPageLink,
  type PreviewPage,
  type PreviewPageConfig,
} from "@/lib/previewPage";
import {
  forgetPreviewPageFile,
  previewPageFile,
  readyPreviewPageFile,
} from "@/lib/previewPageFile";
import type { VendorLibrary } from "@/lib/vendorAssets";
import {
  allowPreviewPageNavigation,
  PREVIEW_PAGE_ORIGIN_WHITELIST,
  previewPageLinkToOpen,
} from "@/lib/webView";

/** A load that fails (the system cleared the cache) writes the page and loads it once more. */
const LOAD_RETRIES = 1;

type WebViewMessage = { nativeEvent: { data?: string } };

type PreviewPageState =
  | { status: "loading" | "failed" }
  | { status: "ready"; webViewKey: string; webViewProps: Record<string, unknown> };

type PageFileState = { uri: string | null; attempt: number; failed: boolean };

/**
 * `config` is the block's data (memoize it). `active` is false when no preview
 * WebView can mount (the card shows its fallback), so no page is written for it.
 * `onMessage` gets what the page posts, except the links it hands to the app.
 */
export function usePreviewPage<L extends VendorLibrary>(
  page: PreviewPage<L>,
  config: PreviewPageConfig,
  { active, onMessage }: { active: boolean; onMessage: (event: WebViewMessage) => void },
): PreviewPageState {
  const [file, setFile] = useState<PageFileState>(() => ({
    uri: readyPreviewPageFile(page),
    attempt: 0,
    failed: false,
  }));

  useEffect(() => {
    if (!active || file.uri || file.failed) return;
    let live = true;
    previewPageFile(page).then(
      (uri) => {
        if (live) setFile((current) => ({ ...current, uri }));
      },
      () => {
        if (live) setFile((current) => ({ ...current, failed: true }));
      },
    );
    return () => {
      live = false;
    };
  }, [active, page, file.uri, file.failed]);

  const { uri, attempt } = file;
  const script = useMemo(() => previewPageConfigScript(config), [config]);

  const onShouldStartLoadWithRequest = useCallback(
    (request?: unknown) => {
      if (uri !== null && allowPreviewPageNavigation(uri, request)) return true;
      // Not in the card: a link the user tapped opens as a chat link would.
      const link = previewPageLinkToOpen(request);
      if (link) void openAllowedUrl(link);
      return false;
    },
    [uri],
  );

  const handleMessage = useCallback(
    (event: WebViewMessage) => {
      const link = previewPageLink(event.nativeEvent.data);
      if (link === null) onMessage(event);
      else void openAllowedUrl(link);
    },
    [onMessage],
  );

  const onError = useCallback(() => {
    // The file went missing: write it again and load it once more, then give up.
    if (uri !== null) forgetPreviewPageFile(page, uri);
    setFile((current) =>
      current.attempt < LOAD_RETRIES
        ? { uri: null, attempt: current.attempt + 1, failed: false }
        : { ...current, uri: null, failed: true },
    );
  }, [page, uri]);

  const webViewProps = useMemo(
    () => ({
      source: { uri },
      originWhitelist: PREVIEW_PAGE_ORIGIN_WHITELIST,
      onShouldStartLoadWithRequest,
      // Android loads a file:// page only with file access on. iOS reads just
      // the page itself: no allowingReadAccessToURL.
      allowFileAccess: true,
      // Android: a target="_blank" link would open a window the guard never sees.
      setSupportMultipleWindows: false,
      // iOS: a long press would preview, so load, the link.
      allowsLinkPreview: false,
      injectedJavaScriptBeforeContentLoaded: script,
      injectedJavaScript: script,
      onMessage: handleMessage,
      onError,
    }),
    [uri, onShouldStartLoadWithRequest, script, handleMessage, onError],
  );

  if (file.failed) return { status: "failed" };
  if (uri === null) return { status: "loading" };
  return { status: "ready", webViewKey: `${attempt}\n${uri}\n${script}`, webViewProps };
}
