/**
 * MathSvgBridgeHost — mount ONCE (e.g., near the chat screen root) to own the
 * single hidden WebView that powers `requestMathSvg`. Renders nothing
 * visible. When `MATH_SVG_NATIVE_ENABLED` is false this is a no-op.
 */

import React, { useCallback, useEffect, useRef } from "react";
import { View } from "react-native";

import {
  buildMathSvgBridgeHtml,
  handleBridgeMessage,
  MATH_SVG_NATIVE_ENABLED,
  setBridgeTransport,
} from "@/lib/mathSvgBridge";
import { supportsInlineHtmlMathWebView } from "@/lib/mathWebViewSupport";
import { getPreviewWebView, STATIC_HTML_ORIGIN_WHITELIST, useStaticOnlyNavigation } from "@/lib/webView";

export function MathSvgBridgeHost() {
  const ref = useRef<{ injectJavaScript: (js: string) => void } | null>(null);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canUseWebView =
    MATH_SVG_NATIVE_ENABLED && Boolean(WebView) && supportsInlineHtmlMathWebView(previewWebView?.mode);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(canUseWebView ? "math-svg-bridge" : "");

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

  if (!canUseWebView || !WebView) return null;

  return (
    <View pointerEvents="none" style={{ position: "absolute", width: 1, height: 1, opacity: 0 }}>
      <WebView
        originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
        source={{ html: buildMathSvgBridgeHtml() }}
        style={{ width: 1, height: 1, backgroundColor: "transparent" }}
        javaScriptEnabled
        domStorageEnabled={false}
        onMessage={onMessage}
        onLoadEnd={() => {
          // ready is signalled by the page itself via postMessage({ready:true});
          // nothing to do here.
        }}
        onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
      />
    </View>
  );
}
