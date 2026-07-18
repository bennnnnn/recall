import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import {
  buildMathWebHtml,
  pickMathEngine,
  type MathEngine,
  type MathHtmlOptions,
} from "@/lib/mathHtml";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { CODE_FONT } from "@/lib/fonts";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";
import { Theme, useTheme } from "@/lib/theme";
import {
  clampMathWebViewHeight,
  MAX_HEIGHT,
} from "@/lib/mathWebViewHeight";

type Props = {
  latex: string;
  displayMode?: boolean;
  compact?: boolean;
  minHeight?: number;
  textColor?: string;
  bgColor?: string;
};

function katexHtml(latex: string, options: MathHtmlOptions): string {
  return buildMathWebHtml(latex, { ...options, engine: "katex" });
}

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

function estimateInitialHeight(
  latex: string,
  displayMode: boolean,
  compact: boolean,
  minHeight: number | undefined,
): number {
  if (minHeight != null) return minHeight;
  if (compact) return 28;
  const lines = Math.max(1, latex.trim().split("\n").length);
  if (displayMode) {
    // Fractions / matrices need more vertical room; prefer overestimate so we
    // grow less often (growth causes list shake; shrink almost never helps).
    if (/\\frac|\\begin\{|\\sqrt/.test(latex)) return Math.min(MAX_HEIGHT, 72 + lines * 12);
    return Math.min(MAX_HEIGHT, 52 + lines * 10);
  }
  return 32;
}

export const MathFormulaWebView = React.memo(function MathFormulaWebView({
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
  const htmlOptions = useMemo(
    (): MathHtmlOptions => ({
      displayMode,
      engine,
      textColor: textColor ?? theme.text,
      bgColor: bgColor ?? theme.contentSurface,
      errorColor: theme.danger,
      compact,
    }),
    [
      displayMode,
      engine,
      textColor,
      bgColor,
      theme.text,
      theme.contentSurface,
      theme.danger,
      compact,
    ],
  );
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc";
  const canUseWebView = Boolean(WebView) && canRenderInline;

  // KaTeX is sync (common path). MathJax lives in an async Metro chunk so the
  // ~2MB vendor is not evaluated on every chat that touches MathFormulaWebView.
  const [html, setHtml] = useState<string | null>(() =>
    engine === "katex" ? katexHtml(latex, htmlOptions) : null,
  );

  useEffect(() => {
    if (engine === "katex") {
      setHtml(katexHtml(latex, htmlOptions));
      return;
    }
    // Static fallback (Expo Go / tests) only needs the engine badge — skip
    // pulling the MathJax chunk when we cannot mount a WebView anyway.
    if (!canUseWebView) {
      setHtml(null);
      return;
    }
    let cancelled = false;
    setHtml(null);
    void import("@/lib/mathHtmlMathjax").then(({ buildMathjaxWebHtml }) => {
      if (cancelled) return;
      setHtml(buildMathjaxWebHtml(latex, htmlOptions));
    });
    return () => {
      cancelled = true;
    };
  }, [engine, latex, htmlOptions, canUseWebView]);

  // Stable identity — a fresh `{ html }` object every render reloads the
  // native WebView (full flicker) even when the HTML string is unchanged.
  const source = useMemo(() => (html != null ? { html } : { html: "" }), [html]);
  const { canMount, onLoaded } = useDeferredWebViewMount(canUseWebView);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(html ?? "");
  const initialHeight = estimateInitialHeight(latex, displayMode, compact, minHeight);
  const [height, setHeight] = useState(initialHeight);
  const heightRef = useRef(initialHeight);

  useEffect(() => {
    heightRef.current = initialHeight;
    setHeight(initialHeight);
  }, [latex, initialHeight]);

  const onMessage = useCallback(
    (event: { nativeEvent: { data: string } }) => {
      const reported = parseHeightMessage(event.nativeEvent.data);
      if (reported == null) return;
      const next = clampMathWebViewHeight(reported, heightRef.current, {
        compact,
        minHeight,
        initialHeight,
      });
      if (next == null) return;
      heightRef.current = next;
      setHeight(next);
    },
    [compact, initialHeight, minHeight],
  );

  if (!canUseWebView || !WebView) {
    return <MathLatexFallback latex={latex} engine={engine} compact={compact} theme={theme} />;
  }

  if (!canMount || html == null) {
    // Reserve space — never flash raw LaTeX here (that reads as flicker).
    // Also covers the brief MathJax async-chunk load.
    return (
      <View
        style={[
          s.wrap,
          compact ? s.wrapCompact : null,
          displayMode ? s.wrapBlock : null,
          { height: initialHeight, backgroundColor: bgColor ?? theme.contentSurface },
        ]}
      />
    );
  }

  return (
    <View style={[s.wrap, compact ? s.wrapCompact : null, displayMode ? s.wrapBlock : null]}>
      <WebView
        originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
        source={source}
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
});

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
  const { t } = useTranslation();
  const s = makeStyles(theme);
  const engineName = engine === "mathjax" ? "MathJax" : "KaTeX";
  return (
    <View style={[s.fallback, compact ? s.fallbackCompact : null]}>
      {!compact ? (
        <Text style={s.fallbackBadge}>{t("rich.math_preview", { engine: engineName })}</Text>
      ) : null}
      <Text style={s.fallbackText} selectable>
        {latex.trim()}
      </Text>
      {!compact ? (
        <Text style={s.fallbackHint}>{t("rich.math_dev_build")}</Text>
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
