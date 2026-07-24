import { useCallback, useEffect, useRef } from "react";
import { NativeModules, TurboModuleRegistry } from "react-native";
import type { ComponentType } from "react";

import {
  createHtmlRunNavigationGuard,
  createStaticOnlyNavigationGuard,
  PREVIEW_INLINE_BASE_URL,
  type StaticOnlyNavigationGuard,
} from "@/lib/staticOnlyNavigationGuard";

export {
  createHtmlRunNavigationGuard,
  createStaticOnlyNavigationGuard,
  PREVIEW_INLINE_BASE_URL,
};
export type { StaticOnlyNavigationGuard };

export type PreviewWebViewMode = "rnc" | "expo-dom";

export type PreviewWebViewResult = {
  Component: ComponentType<Record<string, unknown>>;
  mode: PreviewWebViewMode;
};

let cachedPreviewWebView: PreviewWebViewResult | null | undefined;

function isRncWebViewLinked(): boolean {
  try {
    if (TurboModuleRegistry.get("RNCWebViewModule") != null) {
      return true;
    }
  } catch {
    /* ignore */
  }
  return Boolean(
    NativeModules.RNCWebViewModule ??
      (NativeModules as Record<string, unknown>).RNCWebView,
  );
}

/** Prefer react-native-webview, then @expo/dom-webview. */
export function getPreviewWebView(): PreviewWebViewResult | null {
  if (cachedPreviewWebView !== undefined) return cachedPreviewWebView;

  if (isRncWebViewLinked()) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const Component = require("react-native-webview").WebView as ComponentType<
        Record<string, unknown>
      >;
      cachedPreviewWebView = { Component, mode: "rnc" };
      return cachedPreviewWebView;
    } catch {
      /* fall through */
    }
  }

  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Component = require("@expo/dom-webview").WebView as ComponentType<
      Record<string, unknown>
    >;
    if (Component) {
      cachedPreviewWebView = { Component, mode: "expo-dom" };
      return cachedPreviewWebView;
    }
  } catch {
    /* not available */
  }

  cachedPreviewWebView = null;
  return null;
}

export function getWebView(): ComponentType<Record<string, unknown>> | null {
  return getPreviewWebView()?.Component ?? null;
}

export function isWebViewAvailable(): boolean {
  return getPreviewWebView() != null;
}

/**
 * Inline `source={{ html }}` previews. Include the historical RNC `baseUrl`
 * (`https://localhost/`) plus `about:blank`; the nav guard still blocks real
 * open-web navigations after load.
 */
export const STATIC_HTML_ORIGIN_WHITELIST: string[] = [
  "about:blank",
  "http://localhost*",
  "https://localhost*",
  "http://127.0.0.1*",
  "https://127.0.0.1*",
];

/** Pull URL from RN WebView's nativeEvent (or a plain `{ url }` test stub). */
export function navigationRequestUrl(request: unknown): string {
  if (request == null || typeof request !== "object") return "";
  const rec = request as { url?: unknown; nativeEvent?: { url?: unknown } };
  if (typeof rec.url === "string") return rec.url;
  if (typeof rec.nativeEvent?.url === "string") return rec.nativeEvent.url;
  return "";
}

/** Top-frame flag from RN WebView request (defaults true when unknown). */
export function navigationRequestIsTopFrame(request: unknown): boolean {
  if (request == null || typeof request !== "object") return true;
  const rec = request as {
    isTopFrame?: unknown;
    nativeEvent?: { isTopFrame?: unknown };
  };
  if (typeof rec.isTopFrame === "boolean") return rec.isTopFrame;
  if (typeof rec.nativeEvent?.isTopFrame === "boolean") {
    return rec.nativeEvent.isTopFrame;
  }
  return true;
}

/**
 * React wiring for {@link createStaticOnlyNavigationGuard}: pass the HTML
 * string (or other value identifying "new content") as `sourceKey` so a
 * legitimate content change still gets its one allowed load.
 */
export function useStaticOnlyNavigation(
  sourceKey: unknown,
): (request?: unknown) => boolean {
  const guardRef = useRef<StaticOnlyNavigationGuard | null>(null);
  if (guardRef.current == null) {
    guardRef.current = createStaticOnlyNavigationGuard();
  }
  const guard = guardRef.current;

  useEffect(() => {
    guard.reset();
  }, [sourceKey, guard]);

  return useCallback(
    (request?: unknown) =>
      guard.shouldAllow(
        navigationRequestUrl(request),
        navigationRequestIsTopFrame(request),
      ),
    [guard],
  );
}

/** HTML Run tab: CDN subresources OK; block top-level open-web navigations. */
export function useHtmlRunNavigation(
  sourceKey: unknown,
): (request?: unknown) => boolean {
  const guardRef = useRef<StaticOnlyNavigationGuard | null>(null);
  if (guardRef.current == null) {
    guardRef.current = createHtmlRunNavigationGuard();
  }
  const guard = guardRef.current;

  useEffect(() => {
    guard.reset();
  }, [sourceKey, guard]);

  return useCallback(
    (request?: unknown) =>
      guard.shouldAllow(
        navigationRequestUrl(request),
        navigationRequestIsTopFrame(request),
      ),
    [guard],
  );
}
