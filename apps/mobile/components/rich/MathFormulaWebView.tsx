import { useCallback, useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import {
  buildMathWebHtml,
  pickMathEngine,
  type MathEngine,
} from "@/lib/mathHtml";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { CODE_FONT } from "@/lib/fonts";
import { getPreviewWebView, useStaticOnlyNavigation } from "@/lib/webView";
import { Theme, useTheme } from "@/lib/theme";

const MAX_HEIGHT = 320;

type Props = {
  latex: string;
  displayMode?: boolean;
  compact?: boolean;
  minHeight?: number;
  textColor?: string;
  bgColor?: string;
};

function parseHeightMessage(raw: string): number | null {
  try {
    const data = JSON.parse(raw) as { h?: number };
    if (typeof data.h === "number" && Number.isFinite(data.h) && data.h > 0) {
      return Math.ceil(data.h);
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function MathFormulaWebView({
  latex,
  displayMode = false,
  compact = false,
  minHeight,
  textColor,
  bgColor,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const engine = useMemo(() => pickMathEngine(latex), [latex]);
  const html = useMemo(
    () =>
      buildMathWebHtml(latex, {
        displayMode,
        engine,
        textColor: textColor ?? theme.text,
        bgColor: bgColor ?? theme.contentSurface,
        compact,
      }),
    [
      latex,
      displayMode,
      engine,
      textColor,
      bgColor,
      theme.text,
      theme.contentSurface,
      compact,
    ],
  );
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc";
  const { canMount, onLoaded } = useDeferredWebViewMount(Boolean(WebView) && canRenderInline);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(html);
  const defaultHeight = compact ? 28 : displayMode ? 48 : 32;
  const [height, setHeight] = useState(minHeight ?? defaultHeight);

  useEffect(() => {
    setHeight(minHeight ?? defaultHeight);
  }, [latex, minHeight, defaultHeight]);

  const onMessage = useCallback(
    (event: { nativeEvent: { data: string } }) => {
      const next = parseHeightMessage(event.nativeEvent.data);
      if (next != null) {
        setHeight(Math.min(MAX_HEIGHT, Math.max(minHeight ?? defaultHeight, next)));
      }
    },
    [defaultHeight, minHeight],
  );

  if (!WebView || !canRenderInline) {
    return <MathLatexFallback latex={latex} engine={engine} compact={compact} theme={theme} />;
  }

  if (!canMount) {
    return <MathLoadingPlaceholder latex={latex} compact={compact} theme={theme} />;
  }

  return (
    <View style={[s.wrap, compact ? s.wrapCompact : null, displayMode ? s.wrapBlock : null]}>
      <WebView
        originWhitelist={["*"]}
        source={{ html }}
        style={{ height, backgroundColor: "transparent" }}
        scrollEnabled={false}
        javaScriptEnabled
        domStorageEnabled
        onMessage={onMessage}
        showsHorizontalScrollIndicator={false}
        showsVerticalScrollIndicator={false}
        onLoadEnd={onLoaded}
        onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
      />
    </View>
  );
}

/**
 * Shown while a WebView slot is granted (see useDeferredWebViewMount) —
 * distinct from MathLatexFallback because the WebView *is* available here,
 * just deferred a beat, so it must not claim a dev build is required.
 */
function MathLoadingPlaceholder({
  latex,
  compact,
  theme,
}: {
  latex: string;
  compact?: boolean;
  theme: Theme;
}) {
  const s = makeStyles(theme);
  return (
    <View style={[s.fallback, compact ? s.fallbackCompact : null]}>
      <Text style={s.fallbackText} selectable>
        {latex.trim()}
      </Text>
    </View>
  );
}

function MathLatexFallback({
  latex,
  engine,
  compact,
  theme,
}: {
  latex: string;
  engine: MathEngine;
  compact?: boolean;
  theme: Theme;
}) {
  const s = makeStyles(theme);
  return (
    <View style={[s.fallback, compact ? s.fallbackCompact : null]}>
      {!compact ? (
        <Text style={s.fallbackBadge}>{engine === "mathjax" ? "MathJax" : "KaTeX"} preview</Text>
      ) : null}
      <Text style={s.fallbackText} selectable>
        {latex.trim()}
      </Text>
      {!compact ? (
        <Text style={s.fallbackHint}>Use a dev build for rendered math.</Text>
      ) : null}
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: {
      overflow: "hidden",
      borderRadius: 8,
      backgroundColor: "transparent",
    },
    wrapCompact: {
      borderRadius: 0,
      marginHorizontal: 1,
      alignSelf: "center",
      backgroundColor: "transparent",
    },
    wrapBlock: {
      borderRadius: 10,
      alignSelf: "stretch",
    },
    fallback: {
      backgroundColor: theme.contentSurface,
      borderRadius: 10,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      paddingHorizontal: 12,
      paddingVertical: 10,
      gap: 6,
    },
    fallbackCompact: {
      borderRadius: 6,
      paddingHorizontal: 8,
      paddingVertical: 4,
    },
    fallbackBadge: {
      fontSize: 11,
      fontWeight: "700",
      color: theme.primary,
      textTransform: "uppercase",
      letterSpacing: 0.4,
    },
    fallbackText: {
      fontFamily: CODE_FONT,
      fontSize: 14,
      lineHeight: 20,
      color: theme.text,
    },
    fallbackHint: {
      fontSize: 12,
      color: theme.textTertiary,
    },
  });
