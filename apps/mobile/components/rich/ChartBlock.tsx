/**
 * Chart block — renders ```chart / ```vega / ```vega-lite / ```plot fences
 * inline via WebView + Vega-Embed so the user sees the actual chart, not raw JSON.
 */
import { useCallback, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Icon } from "@/components/Icon";

import { CopyButton } from "@/components/CopyButton";
import { VisualCard } from "@/components/rich/VisualCard";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { buildVegaHtml } from "@/lib/chartPreviewHtml";
import {
  CHART_HEIGHT_EPSILON_PX,
  CHART_MAX_EXPANDED,
  CHART_MAX_HEIGHT,
  CHART_PREVIEW_HEIGHT,
  chartPreviewIsClipped,
  chartTogglePreviewHeight,
  nextChartPreviewHeight,
} from "@/lib/chartPreviewHeight";
import { CODE_FONT } from "@/lib/fonts";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";

type Props = { content: string };

type ChartErrorMessage = { kind: "chart-error"; message?: string };
type ChartSizeMessage = { kind: "chart-size"; height?: number };

function isChartErrorMessage(data: unknown): data is ChartErrorMessage {
  return typeof data === "object" && data !== null && (data as { kind?: string }).kind === "chart-error";
}

function isChartSizeMessage(data: unknown): data is ChartSizeMessage {
  return typeof data === "object" && data !== null && (data as { kind?: string }).kind === "chart-size";
}

export function ChartBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [expanded, setExpanded] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [viewWidth, setViewWidth] = useState(0);
  const [previewHeight, setPreviewHeight] = useState(CHART_PREVIEW_HEIGHT);
  const [reportedHeight, setReportedHeight] = useState(0);
  const heightRef = useRef(CHART_PREVIEW_HEIGHT);
  const expandedRef = useRef(expanded);
  expandedRef.current = expanded;

  const plotWidth = viewWidth > 0 ? viewWidth - 16 : 320;
  const vegaHtml = useMemo(
    () => buildVegaHtml(content, theme, plotWidth),
    [content, theme, plotWidth],
  );
  const source = useMemo(() => ({ html: vegaHtml }), [vegaHtml]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInlineChart = previewWebView?.mode === "rnc";
  const { canMount, onLoaded } = useDeferredWebViewMount(
    Boolean(WebView) && canRenderInlineChart,
  );
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(vegaHtml);

  const maxHeight = expanded ? CHART_MAX_EXPANDED : CHART_MAX_HEIGHT;
  const height = Math.min(previewHeight, maxHeight);
  const clipped = chartPreviewIsClipped(reportedHeight, height);

  const handleWebViewMessage = useCallback((event: { nativeEvent: { data?: string } }) => {
    try {
      const data: unknown = JSON.parse(event.nativeEvent.data ?? "{}");
      if (isChartErrorMessage(data)) {
        setRenderError(data.message ?? t("rich.chart_error"));
        return;
      }
      if (isChartSizeMessage(data)) {
        const reported = Number(data.height);
        if (!Number.isFinite(reported) || reported <= 0) return;
        setReportedHeight(reported);
        const maxH = expandedRef.current ? CHART_MAX_EXPANDED : CHART_MAX_HEIGHT;
        const next = nextChartPreviewHeight(reported, heightRef.current, maxH);
        if (next == null) return;
        heightRef.current = next;
        setPreviewHeight(next);
      }
    } catch {
      setRenderError(t("rich.chart_error"));
    }
  }, [t]);

  const handleOpenVegaEditor = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://vega.github.io/editor/");
  }, [content]);

  const toggleExpanded = useCallback(() => {
    setExpanded((was) => {
      const next = !was;
      const clamped = chartTogglePreviewHeight(reportedHeight || heightRef.current, next);
      heightRef.current = clamped;
      setPreviewHeight(clamped);
      return next;
    });
  }, [reportedHeight]);

  return (
    <VisualCard
      label={t("rich.chart")}
      icon="bar-chart-outline"
      headerRight={
        <Text style={s.lineCount}>
          {t("rich.lines_count", { count: content.trim().split("\n").length })}
        </Text>
      }
      onLayout={(e) => {
        const w = Math.floor(e.nativeEvent.layout.width);
        if (w > 0 && Math.abs(w - viewWidth) > CHART_HEIGHT_EPSILON_PX) setViewWidth(w);
      }}
      actions={
        <>
          <CopyButton text={content} />
          <Pressable
            style={s.iconBtn}
            onPress={() => setShowSource((v) => !v)}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={t("rich.source")}
          >
            <Icon
              name={showSource ? "eye-off-outline" : "code-slash-outline"}
              size={20}
              color={showSource ? theme.primary : theme.textSecondary}
            />
          </Pressable>
          {clipped || expanded ? (
            <Pressable
              style={s.iconBtn}
              onPress={toggleExpanded}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel={expanded ? t("rich.collapse") : t("rich.expand")}
            >
              <Icon
                name={expanded ? "contract-outline" : "expand-outline"}
                size={20}
                color={theme.textSecondary}
              />
            </Pressable>
          ) : null}
          <Pressable
            style={s.iconBtn}
            onPress={handleOpenVegaEditor}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={t("rich.vega_editor")}
          >
            <Icon name="open-outline" size={20} color={theme.textSecondary} />
          </Pressable>
        </>
      }
    >
      <View style={[s.previewBox, { height }]}>
        {renderError ? (
          <View style={[s.previewPlaceholder, { height }]}>
            <Icon name="alert-circle-outline" size={20} color={theme.danger} />
            <Text style={[s.previewPlaceholderText, { color: theme.danger }]}>
              {renderError}
            </Text>
          </View>
        ) : WebView && canRenderInlineChart ? (
          canMount ? (
            <WebView
              originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
              source={source}
              style={{ height, width: viewWidth > 0 ? viewWidth : 320 }}
              scrollEnabled={clipped}
              nestedScrollEnabled={clipped}
              showsVerticalScrollIndicator={clipped}
              javaScriptEnabled
              domStorageEnabled={false}
              onLoadEnd={onLoaded}
              onMessage={handleWebViewMessage}
              onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
            />
          ) : (
            <View style={[s.previewPlaceholder, { height }]}>
              <ActivityIndicator color={theme.primary} />
            </View>
          )
        ) : (
          <View style={[s.previewPlaceholder, { height }]}>
            <Text style={s.previewPlaceholderText}>
              {t("rich.chart_dev_build")}
            </Text>
          </View>
        )}
      </View>

      {showSource && (
        <View style={s.sourceBox}>
          <Text style={s.sourceText} selectable>
            {content.trim()}
          </Text>
        </View>
      )}
    </VisualCard>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    lineCount: { ...Type.meta, color: t.textTertiary },
    previewBox: {
      backgroundColor: t.bg,
      overflow: "hidden",
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    previewPlaceholder: {
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 16,
    },
    previewPlaceholderText: {
      fontSize: 13,
      color: t.textSecondary,
      textAlign: "center",
    },
    sourceBox: {
      paddingHorizontal: 14,
      paddingVertical: 10,
      backgroundColor: t.contentSurface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      maxHeight: 200,
    },
    sourceText: {
      fontFamily: CODE_FONT,
      fontSize: 11,
      lineHeight: 17,
      color: t.textSecondary,
    },
    iconBtn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
