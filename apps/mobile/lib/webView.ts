import { useCallback, useEffect, useRef } from "react";
import { NativeModules, Platform, TurboModuleRegistry } from "react-native";
import type { ComponentType } from "react";

import { isAllowedLinkUrl } from "@/lib/linkSchemePolicy";
import {
  createStaticOnlyNavigationGuard,
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

/** Prefer react-native-webview, then (development builds only) @expo/dom-webview. */
export function getPreviewWebView(): PreviewWebViewResult | null {
  if (cachedPreviewWebView !== undefined) return cachedPreviewWebView;

  if (isRncWebViewLinked()) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports -- only once the native module is linked; Expo Go has none
      const Component = require("react-native-webview").WebView as ComponentType<
        Record<string, unknown>
      >;
      cachedPreviewWebView = { Component, mode: "rnc" };
      return cachedPreviewWebView;
    } catch {
      /* fall through */
    }
  }

  // Expo Go lacks react-native-webview; every build of the app links it, so a
  // production bundle leaves this fallback out (code-health audit DEAD-08). Plain
  // Node (the lib tests) has no __DEV__.
  if (typeof __DEV__ !== "undefined" && __DEV__) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports -- development only, so production bundles leave it out
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

/**
 * The Run tab's own documents (lib/htmlRunDocument.ts): the wrapper, which
 * `source={{ html }}` with no baseUrl loads at about:blank (RNCWebViewImpl.m
 * visitSource on iOS; Android loads it without asking), and the page's
 * sandboxed frame.
 */
const HTML_RUN_DOCUMENTS = new Set(["about:blank", "about:srcdoc"]);

/**
 * The Run tab may navigate only within its own documents (a `#` link
 * included). Everything else, CDN pages included (anyone can publish one), is
 * refused in place and opened nowhere.
 *
 * Which navigations come here differs by platform. iOS asks about every frame
 * (decidePolicyForNavigationAction). Android asks only about GET navigations,
 * and of a subframe's only those to other schemes than http, https and about
 * (AwContentBrowserClient::ShouldOverrideUrlLoading); the page frame's own
 * web navigations are stopped by the wrapper's frame-src instead
 * (lib/htmlRunDocument.ts). Neither platform asks about subresources: CDN
 * scripts, styles, images, fonts and fetches follow PREVIEW_CSP_LIVE alone.
 * The frame flag is not read: iOS derives isTopFrame by comparing the URL with
 * the main document's, and Android does not send it.
 */
export function allowHtmlRunNavigation(request?: unknown): boolean {
  const url = navigationRequestUrl(request).trim().toLowerCase();
  // WebKit's name for a page loaded from a string without a base URL.
  if (url.startsWith("applewebdata:")) return true;
  const hash = url.indexOf("#");
  return HTML_RUN_DOCUMENTS.has(hash === -1 ? url : url.slice(0, hash));
}

/**
 * A preview page loaded from its file (lib/previewPageFile.ts). Every URL
 * reaches {@link allowPreviewPageNavigation}, so react-native-webview never
 * hands one to the OS by itself; {@link previewPageLinkToOpen} decides that.
 */
export const PREVIEW_PAGE_ORIGIN_WHITELIST: string[] = ["*"];

/** The page may load itself and nothing else: no other file, no web page. */
export function allowPreviewPageNavigation(pageUri: string, request?: unknown): boolean {
  const url = navigationRequestUrl(request).trim();
  // A subframe's blank document, never the card itself.
  if (url.toLowerCase() === "about:blank") return !navigationRequestIsTopFrame(request);
  const page = filePath(pageUri);
  return page !== null && filePath(url) === page;
}

/**
 * A navigation the page may not make that should still open, as links in
 * these cards did before they were files: a top-frame link the chat would open
 * too (lib/linkSchemePolicy.ts). iOS reports what started a navigation, so
 * there only a tap on a link opens.
 */
export function previewPageLinkToOpen(request?: unknown): string | null {
  if (!navigationRequestIsTopFrame(request)) return null;
  if (Platform.OS === "ios" && navigationRequestType(request) !== "click") return null;
  const url = navigationRequestUrl(request).trim();
  return isAllowedLinkUrl(url) ? url : null;
}

/** A file URL's whole path, decoded, with iOS's /private/var spelled /var. */
function filePath(url: string): string | null {
  const match = /^file:\/\/(?:localhost)?(\/[^?#]*)/i.exec(url);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]).replace(/^\/private\/var\//, "/var/");
  } catch {
    return null;
  }
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
