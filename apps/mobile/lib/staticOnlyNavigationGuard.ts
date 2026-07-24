export type NavigationGuardRequest = {
  url?: string;
  isTopFrame?: boolean;
  /** iOS: click | formsubmit | backforward | reload | formresubmit | other */
  navigationType?: string;
};

export type StaticOnlyNavigationGuard = {
  /**
   * Call from `onShouldStartLoadWithRequest`.
   * Charts/math: deny all open-web http(s).
   * HTML Run: allow CDN loads; deny only user-driven top-level navigations.
   */
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

/**
 * react-native-webview's historical `baseUrl` for inline HTML on iOS.
 * Must stay allowlisted: denying it blanks the Run tab even when the HTML is
 * already in memory (security #415 tightened originWhitelist to about:blank
 * and the nav guard blocked https://localhost as "external").
 */
export const PREVIEW_INLINE_BASE_URL = "https://localhost/";

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

/** Inline-HTML document origin (`baseUrl`), not an open-web navigation. */
export function isPreviewInlineDocumentUrl(url: string): boolean {
  const u = url.trim().toLowerCase();
  if (!u) return false;
  try {
    const parsed = new URL(u);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
    return parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
  } catch {
    return (
      u === "https://localhost/" ||
      u === "https://localhost" ||
      u.startsWith("https://localhost/") ||
      u === "http://localhost/" ||
      u === "http://localhost" ||
      u.startsWith("http://localhost/")
    );
  }
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

/**
 * HTML Run tab: always allow loads.
 *
 * Returning false for http(s) (even "top-frame only") blanks CDN demos — iOS
 * often mis-labels script/style fetches as top-frame. Returning true for those
 * same mis-labeled requests can navigate the main frame away from the HTML.
 * So the native nav guard cannot safely filter CDN vs leave-document traffic.
 * Stay-on-document is enforced in-page (injected click/submit trap + CSP
 * form-action 'none'), not here.
 */
export function createHtmlRunNavigationGuard(): StaticOnlyNavigationGuard {
  return {
    shouldAllow: () => true,
    reset: () => {
      /* no state */
    },
  };
}
