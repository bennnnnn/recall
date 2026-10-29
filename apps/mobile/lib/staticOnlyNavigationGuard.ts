type NavigationGuardRequest = {
  url?: string;
  isTopFrame?: boolean;
  /** iOS: click | formsubmit | backforward | reload | formresubmit | other */
  navigationType?: string;
};

type StaticOnlyNavigationGuard = {
  shouldAllow: (request?: NavigationGuardRequest | string) => boolean;
  /** Call when the WebView's source content legitimately changes. */
  reset: () => void;
};

function normalizeGuardRequest(
  request?: NavigationGuardRequest | string,
): NavigationGuardRequest {
  if (typeof request === "string") return { url: request, isTopFrame: true };
  return request ?? {};
}

/** Loads that are part of rendering self-contained preview HTML, not navigation. */
export function isPreviewFrameworkUrl(url: string): boolean {
  const u = url.trim().toLowerCase();
  if (!u) return true;
  if (u === "about:blank" || u.startsWith("about:")) return true;
  if (u.startsWith("data:")) return true;
  // expo-dom / written preview files
  if (u.startsWith("file:")) return true;
  // WKWebView sometimes reports this for string-loaded documents
  if (u.startsWith("applewebdata:")) return true;
  return false;
}

/**
 * The document URL react-native-webview gives inline `source={{ html }}`
 * when no `baseUrl` is passed, and no preview passes one. iOS
 * (RNCWebViewImpl.m `visitSource`) falls back to about:blank; Android
 * (RNCWebViewManagerImpl.kt) hands "" to loadDataWithBaseURL, which WebView
 * reads as about:blank.
 */
export const PREVIEW_INLINE_BASE_URL = "about:blank";

/**
 * The inline-HTML document itself, not a navigation. Only its exact URL:
 * a preview must never reach a server on the phone (`localhost`,
 * `127.0.0.1`: a dev server, another app's local server), in any build.
 * Development needs no more: the dev-only @expo/dom-webview never asks the
 * guards, and vendored libraries reach a page inlined, not from Metro.
 */
export function isPreviewInlineDocumentUrl(url: string): boolean {
  return url.trim().toLowerCase() === PREVIEW_INLINE_BASE_URL;
}

export function isExternalHttpUrl(url: string): boolean {
  const u = url.trim().toLowerCase();
  return u.startsWith("http://") || u.startsWith("https://");
}

/**
 * Preview WebViews only ever render self-contained model/user HTML — there is
 * no legitimate reason for one to navigate to the open web. WKWebView often
 * fires `about:blank` (or similar) before the real document; a naive "allow
 * exactly one request" guard then blocks the HTML itself and leaves a blank
 * screen. Allow framework + inline-document URLs always; deny other `http(s):`;
 * keep a one-shot fallback for unknown schemes.
 */
export function createStaticOnlyNavigationGuard(): StaticOnlyNavigationGuard {
  let allowedUnknownOnce = false;
  return {
    shouldAllow: (request) => {
      const { url = "" } = normalizeGuardRequest(request);
      if (isPreviewFrameworkUrl(url)) return true;
      if (isPreviewInlineDocumentUrl(url)) return true;
      if (isExternalHttpUrl(url)) return false;
      if (!allowedUnknownOnce) {
        allowedUnknownOnce = true;
        return true;
      }
      return false;
    },
    reset: () => {
      allowedUnknownOnce = false;
    },
  };
}
