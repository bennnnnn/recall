export type StaticOnlyNavigationGuard = {
  /**
   * Call from `onShouldStartLoadWithRequest`. Pass the request URL when
   * available — framework loads (`about:blank`, `data:`, `file:`) are always
   * allowed; `http(s):` navigations are always denied (phishing).
   */
  shouldAllow: (url?: string) => boolean;
  /** Call when the WebView's source content legitimately changes. */
  reset: () => void;
};

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
    shouldAllow: (url = "") => {
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
