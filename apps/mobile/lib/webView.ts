import { useCallback, useEffect, useRef } from "react";
import { NativeModules, TurboModuleRegistry } from "react-native";
import type { ComponentType } from "react";

import { HTML_RUN_CDN_HOSTS } from "@/lib/htmlRunCdn";
import {
  createStaticOnlyNavigationGuard,
  isPreviewInlineDocumentUrl,
  type StaticOnlyNavigationGuard,
} from "@/lib/staticOnlyNavigationGuard";

type PreviewWebViewMode = "rnc" | "expo-dom";

type PreviewWebViewResult = {
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

/**
 * HTML Run passes every navigation to {@link allowHtmlRunNavigation}.
 *
 * react-native-webview hands any URL that misses `originWhitelist` to
 * `Linking.openURL` — Safari, the dialer, Messages, or a deep link into
 * Recall — with no tap from the user. The Run tab executes model-written
 * JavaScript, so `location = "https://…"` in a reply opened a page outside
 * the app. Matching everything here leaves the decision to the guard, which
 * blocks without opening anything.
 */
export const HTML_RUN_ORIGIN_WHITELIST: string[] = ["*"];

const HTML_RUN_CDN_ORIGINS = new Set<string>(HTML_RUN_CDN_HOSTS);

/**
 * Loads the Run tab may make in its own frame: the inline document itself
 * and the CDN allowlist (the same set the old origin whitelist let through,
 * matched by exact origin instead of string prefix). Everything else is
 * refused in place.
 */
export function allowHtmlRunNavigation(request?: unknown): boolean {
  const url = navigationRequestUrl(request).trim();
  const lower = url.toLowerCase();
  if (lower.startsWith("about:") || lower.startsWith("applewebdata:")) return true;
  if (isPreviewInlineDocumentUrl(url)) return true;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && HTML_RUN_CDN_ORIGINS.has(parsed.origin);
  } catch {
    return false;
  }
}

/**
 * A preview page loaded from its file (lib/previewPageFile.ts). Every URL
 * reaches {@link allowPreviewPageNavigation}, so a link in a diagram or chart
 * is refused in place instead of handed to the OS.
 */
export const PREVIEW_PAGE_ORIGIN_WHITELIST: string[] = ["*"];

/** The page may load itself and nothing else: no other file, no web page. */
export function allowPreviewPageNavigation(pageUri: string, request?: unknown): boolean {
  const url = navigationRequestUrl(request).trim();
  if (url.toLowerCase() === "about:blank") return true;
  const page = previewPageFileKey(pageUri);
  return page !== null && previewPageFileKey(url) === page;
}

/** A file URL's folder and name, which iOS keeps when it reports /var/… as /private/var/…. */
function previewPageFileKey(url: string): string | null {
  if (!/^file:\/\//i.test(url)) return null;
  const path = url.split(/[?#]/, 1)[0] ?? "";
  return path.split("/").slice(-2).join("/");
}

/** Pull URL from RN WebView's nativeEvent (or a plain `{ url }` test stub). */
function navigationRequestUrl(request: unknown): string {
  if (request == null || typeof request !== "object") return "";
  const rec = request as { url?: unknown; nativeEvent?: { url?: unknown } };
  if (typeof rec.url === "string") return rec.url;
  if (typeof rec.nativeEvent?.url === "string") return rec.nativeEvent.url;
  return "";
}

/** Top-frame flag from RN WebView request (defaults true when unknown). */
function navigationRequestIsTopFrame(request: unknown): boolean {
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

function navigationRequestType(request: unknown): string {
  if (request == null || typeof request !== "object") return "other";
  const rec = request as {
    navigationType?: unknown;
    nativeEvent?: { navigationType?: unknown };
  };
  if (typeof rec.navigationType === "string") return rec.navigationType;
  if (typeof rec.nativeEvent?.navigationType === "string") {
    return rec.nativeEvent.navigationType;
  }
  return "other";
}

function guardRequestFromEvent(request?: unknown) {
  return {
    url: navigationRequestUrl(request),
    isTopFrame: navigationRequestIsTopFrame(request),
    navigationType: navigationRequestType(request),
  };
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
    (request?: unknown) => guard.shouldAllow(guardRequestFromEvent(request)),
    [guard],
  );
}
