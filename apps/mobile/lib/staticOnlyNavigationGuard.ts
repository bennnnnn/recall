export type StaticOnlyNavigationGuard = {
  /** Call from `onShouldStartLoadWithRequest`; true only for the first request since the last reset. */
  shouldAllow: () => boolean;
  /** Call when the WebView's source content legitimately changes, to re-arm the one allowed load. */
  reset: () => void;
};

/**
 * Preview WebViews only ever render self-contained model/user HTML — there is
 * no legitimate reason for one to navigate anywhere. Without a guard, a link
 * or `window.location` assignment inside that HTML can navigate the WebView
 * itself to an arbitrary origin, rendered inside the app's own chrome
 * (phishing). This allows exactly one navigation (the initial load of the
 * current content) and denies every request after that, until `reset()` is
 * called for new content.
 */
export function createStaticOnlyNavigationGuard(): StaticOnlyNavigationGuard {
  let allowedOnce = false;
  return {
    shouldAllow: () => {
      if (!allowedOnce) {
        allowedOnce = true;
        return true;
      }
      return false;
    },
    reset: () => {
      allowedOnce = false;
    },
  };
}
