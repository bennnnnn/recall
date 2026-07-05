import { useCallback, useEffect, useRef } from "react";
import { NativeModules, TurboModuleRegistry } from "react-native";
import type { ComponentType } from "react";

import {
  createStaticOnlyNavigationGuard,
  type StaticOnlyNavigationGuard,
} from "@/lib/staticOnlyNavigationGuard";

export { createStaticOnlyNavigationGuard };
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
 * React wiring for {@link createStaticOnlyNavigationGuard}: pass the HTML
 * string (or other value identifying "new content") as `sourceKey` so a
 * legitimate content change still gets its one allowed load.
 */
export function useStaticOnlyNavigation(sourceKey: unknown): () => boolean {
  const guardRef = useRef<StaticOnlyNavigationGuard | null>(null);
  if (guardRef.current == null) {
    guardRef.current = createStaticOnlyNavigationGuard();
  }
  const guard = guardRef.current;

  useEffect(() => {
    guard.reset();
  }, [sourceKey, guard]);

  return useCallback(() => guard.shouldAllow(), [guard]);
}
