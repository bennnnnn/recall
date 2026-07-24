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

/** Loads that are part of rendering self-contained preview HTML, not navigation. */
export function isPreviewFrameworkUrl(url: string): boolean {
  const u = url.trim().toLowerCase();
  if (!u) return true;
  if (u === "about:blank" || u.startsWith("about:")) return true;
  if (u.startsWith("data:")) return true;
  // expo-dom / written preview files
  if (u.startsWith("file:")) return true;
  return false;
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
 * screen. Allow framework URLs always; deny `http(s):` always; keep a one-shot
 * fallback for unknown schemes.
 */
export function createStaticOnlyNavigationGuard(): StaticOnlyNavigationGuard {
  let allowedUnknownOnce = false;
  return {
    shouldAllow: (url = "") => {
      if (isPreviewFrameworkUrl(url)) return true;
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
