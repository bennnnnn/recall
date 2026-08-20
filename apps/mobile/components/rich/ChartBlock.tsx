/**
 * Chart block — renders ```chart / ```vega / ```vega-lite / ```plot fences
 * inline via WebView + Vega-Embed so the user sees the actual chart, not raw JSON.
 */
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Icon } from "@/components/Icon";

import { CopyButton } from "@/components/CopyButton";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { CODE_FONT } from "@/lib/fonts";
import { escapeForInlineJsTemplate, injectPreviewCsp, inlineScript } from "@/lib/previewSandbox";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";
import { VEGA_MIN_JS } from "@/lib/vendor/vegaMinJs";
import { VEGA_LITE_MIN_JS } from "@/lib/vendor/vegaLiteMinJs";
import { VEGA_EMBED_MIN_JS } from "@/lib/vendor/vegaEmbedMinJs";

type Props = { content: string };

const PREVIEW_HEIGHT = 350;
const CHART_WEBVIEW_WIDTH = 720;

type ChartErrorMessage = { kind: "chart-error"; message?: string };

function isChartErrorMessage(data: unknown): data is ChartErrorMessage {
  return typeof data === "object" && data !== null && (data as { kind?: string }).kind === "chart-error";
}

/** Build a self-contained HTML page that renders a Vega / Vega-Lite spec via vendored, inlined Vega-Embed. */
function buildVegaHtml(spec: string, theme: Theme): string {
  const safeSpec = escapeForInlineJsTemplate(spec);
  const vegaTheme = theme.isDark ? "dark" : "vox";
  const axisColor = theme.isDark ? theme.border : "#888";
  const textColor = theme.isDark ? theme.text : "#333";
  const gridColor = theme.isDark ? theme.border : "#eee";
  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>${inlineScript(VEGA_MIN_JS)}</script>
<script>${inlineScript(VEGA_LITE_MIN_JS)}</script>
<script>${inlineScript(VEGA_EMBED_MIN_JS)}</script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { display: flex; justify-content: center; align-items: center; min-height: 100vh; font-family: -apple-system, sans-serif; background: ${theme.bg}; }
  #chart { width: 100%; max-width: 100%; padding: 8px; }
  #error { color: ${theme.danger}; padding: 16px; font-size: 13px; display: none; white-space: pre-wrap; word-break: break-word; }
</style>
</head>
<body>
<div id="chart"></div>
<div id="error"></div>
<script>
  const spec = \`${safeSpec}\`;
  function reportError(msg) {
    try { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify({ kind: 'chart-error', message: msg })); } catch (e) {}
    var el = document.getElementById('error');
    el.textContent = 'Chart error: ' + msg;
    el.style.display = 'block';
  }
  try {
    const parsed = JSON.parse(spec);
    const themedConfig = {
      background: ${JSON.stringify(theme.bg)},
      axis: { domainColor: ${JSON.stringify(axisColor)}, labelColor: ${JSON.stringify(textColor)}, titleColor: ${JSON.stringify(textColor)}, tickColor: ${JSON.stringify(axisColor)}, gridColor: ${JSON.stringify(gridColor)} },
      legend: { labelColor: ${JSON.stringify(textColor)}, titleColor: ${JSON.stringify(textColor)} },
      title: { color: ${JSON.stringify(textColor)} },
      view: { stroke: ${JSON.stringify(axisColor)} },
    };
    parsed.config = Object.assign({}, themedConfig, parsed.config || {});
    vegaEmbed('#chart', parsed, {
      actions: false,
      renderer: 'svg',
      width: ${CHART_WEBVIEW_WIDTH - 16},
      height: ${PREVIEW_HEIGHT - 24},
      theme: ${JSON.stringify(vegaTheme)},
      config: themedConfig,
    }).catch(function(err) { reportError(err && err.message ? err.message : String(err)); });
  } catch (e) {
    reportError(e && e.message ? e.message : String(e));
  }
</script>
</body>
</html>`);
}

export function ChartBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [expanded, setExpanded] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);

  const vegaHtml = useMemo(() => buildVegaHtml(content, theme), [content, theme]);
  const source = useMemo(() => ({ html: vegaHtml }), [vegaHtml]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInlineChart = previewWebView?.mode === "rnc";
  const { canMount, onLoaded } = useDeferredWebViewMount(
    Boolean(WebView) && canRenderInlineChart,
  );
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(vegaHtml);

  const handleWebViewMessage = useCallback((event: { nativeEvent: { data?: string } }) => {
    try {
      const data = JSON.parse(event.nativeEvent.data ?? "{}");
      if (isChartErrorMessage(data)) setRenderError(data.message ?? t("rich.chart_error"));
    } catch {
      setRenderError(t("rich.chart_error"));
    }
  }, [t]);

  const handleOpenVegaEditor = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://vega.github.io/editor/");
  }, [content]);

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Icon name="bar-chart-outline" size={16} color={theme.primary} />
          <Text style={s.headerLabel}>{t("rich.chart")}</Text>
        </View>
        <Text style={s.lineCount}>
          {t("rich.lines_count", { count: content.trim().split("\n").length })}
        </Text>
      </View>

      <View style={[s.previewBox, expanded && s.previewBoxExpanded]}>
        {renderError ? (
          <View style={s.previewPlaceholder}>
            <Icon name="alert-circle-outline" size={20} color={theme.danger} />
            <Text style={[s.previewPlaceholderText, { color: theme.danger }]}>
              {renderError}
            </Text>
          </View>
        ) : WebView && canRenderInlineChart ? (
          canMount ? (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator
              contentContainerStyle={s.chartScrollContent}
              style={s.chartScroll}
            >
              <WebView
                originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
                source={source}
                style={{
                  height: expanded ? PREVIEW_HEIGHT * 2 : PREVIEW_HEIGHT,
                  width: CHART_WEBVIEW_WIDTH,
                }}
                scrollEnabled={false}
                javaScriptEnabled
                domStorageEnabled={false}
                onLoadEnd={onLoaded}
                onMessage={handleWebViewMessage}
                onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
              />
            </ScrollView>
          ) : (
            <View style={s.previewPlaceholder}>
              <ActivityIndicator color={theme.primary} />
            </View>
          )
        ) : (
          <View style={s.previewPlaceholder}>
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

      <View style={s.actions}>
        <CopyButton text={content} variant="action" />

        <Pressable
          style={s.actionBtn}
          onPress={() => setShowSource((v) => !v)}
          hitSlop={8}
        >
          <Icon
            name={showSource ? "eye-off-outline" : "code-slash-outline"}
            size={18}
            color={showSource ? theme.primary : theme.textSecondary}
          />
          <Text style={[s.actionLabel, showSource && s.actionLabelActive]}>
            {t("rich.source")}
          </Text>
        </Pressable>

        <Pressable
          style={s.actionBtn}
          onPress={() => setExpanded((v) => !v)}
          hitSlop={8}
        >
          <Icon
            name={expanded ? "contract-outline" : "expand-outline"}
            size={18}
            color={theme.textSecondary}
          />
          <Text style={s.actionLabel}>
            {expanded ? t("rich.collapse") : t("rich.expand")}
          </Text>
        </Pressable>

        <Pressable style={s.openBtn} onPress={handleOpenVegaEditor} hitSlop={8}>
          <Icon name="open-outline" size={18} color={theme.onPrimary} />
          <Text style={s.openLabel}>{t("rich.vega_editor")}</Text>
        </Pressable>
      </View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      marginVertical: 8,
      borderRadius: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      overflow: "hidden",
      backgroundColor: t.bg,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 14,
      paddingVertical: 10,
      backgroundColor: t.surface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    headerLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
    headerLabel: { fontSize: 14, fontWeight: "700", color: t.text },
    lineCount: { ...Type.meta, color: t.textTertiary },
    previewBox: {
      backgroundColor: t.bg,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    previewBoxExpanded: {},
    chartScroll: { backgroundColor: t.bg },
    chartScrollContent: { flexGrow: 1, alignItems: "center" },
    previewPlaceholder: {
      height: PREVIEW_HEIGHT,
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
    actions: {
      flexDirection: "row",
      gap: 8,
      paddingHorizontal: 14,
      paddingVertical: 10,
      flexWrap: "wrap",
    },
    actionBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      paddingVertical: 8,
      paddingHorizontal: 14,
      borderRadius: 10,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    actionLabel: { fontSize: 14, fontWeight: "600", color: t.textSecondary },
    actionLabelActive: { color: t.primary },
    openBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 6,
      paddingVertical: 10,
      paddingHorizontal: 16,
      borderRadius: 10,
      backgroundColor: t.primary,
    },
    openLabel: { fontSize: 14, fontWeight: "700", color: t.onPrimary },
  });
}
