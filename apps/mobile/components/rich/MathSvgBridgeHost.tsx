/**
 * MathSvgBridgeHost — mount ONCE (e.g., near the chat screen root) to own the
 * single hidden WebView that powers `requestMathSvg`. Renders nothing
 * visible. When `MATH_SVG_NATIVE_ENABLED` is false this is a no-op.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { View } from "react-native";

import {
  handleBridgeMessage,
  MATH_SVG_NATIVE_ENABLED,
  setBridgeTransport,
} from "@/lib/mathSvgBridge";
import { supportsInlineHtmlMathWebView } from "@/lib/mathWebViewSupport";
import { getPreviewWebView, STATIC_HTML_ORIGIN_WHITELIST, useStaticOnlyNavigation } from "@/lib/webView";

export function MathSvgBridgeHost() {
  const ref = useRef<{ injectJavaScript: (js: string) => void } | null>(null);
  const [html, setHtml] = useState<string | null>(null);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canUseWebView =
    MATH_SVG_NATIVE_ENABLED && Boolean(WebView) && supportsInlineHtmlMathWebView(previewWebView?.mode);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(canUseWebView ? "math-svg-bridge" : "");

  // Load the bridge HTML (and the ~2MB MathJax vendor) only when the flag is
  // on and a WebView is available — keeps MathJax out of the main bundle when
  // the spike is off.
  useEffect(() => {
    if (!canUseWebView) {
      setHtml(null);
      return;
    }
    let cancelled = false;
    void import("@/lib/mathSvgBridge").then(({ buildMathSvgBridgeHtml }) =>
      buildMathSvgBridgeHtml().then((h) => {
        if (!cancelled) setHtml(h);
      }),
    );
    return () => {
      cancelled = true;
    };
  }, [canUseWebView]);

  const onMessage = useCallback((event: { nativeEvent: { data: string } }) => {
    const raw = event.nativeEvent.data;
    let parsed: { ready?: boolean };
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    if (parsed.ready) {
      setBridgeTransport((js) => ref.current?.injectJavaScript(js) ?? null, true);
      return;
    }
    handleBridgeMessage(raw);
  }, []);

  useEffect(() => {
    if (!canUseWebView) {
      setBridgeTransport(null, false);
      return;
    }
    return () => setBridgeTransport(null, false);
  }, [canUseWebView]);

  if (!canUseWebView || !WebView || html == null) return null;

  return (
    <View pointerEvents="none" style={{ position: "absolute", width: 1, height: 1, opacity: 0 }}>
      <WebView
        originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
        source={{ html }}
        style={{ width: 1, height: 1, backgroundColor: "transparent" }}
        javaScriptEnabled
        domStorageEnabled={false}
        onMessage={onMessage}
        onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
      />
    </View>
  );
}
