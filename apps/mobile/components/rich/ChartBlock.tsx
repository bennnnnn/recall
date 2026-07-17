/**
 * Chart block — renders ```chart / ```vega / ```vega-lite / ```plot fences
 * inline via WebView + Vega-Embed so the user sees the actual chart, not raw JSON.
 */
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Ionicons } from "@expo/vector-icons";

import { CopyButton } from "@/components/CopyButton";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { CODE_FONT } from "@/lib/fonts";
import { escapeForInlineJsTemplate, injectPreviewCsp, inlineScript } from "@/lib/previewSandbox";
import { Theme, useTheme } from "@/lib/theme";
import { getPreviewWebView, useStaticOnlyNavigation } from "@/lib/webView";
import { VEGA_MIN_JS } from "@/lib/vendor/vegaMinJs";
import { VEGA_LITE_MIN_JS } from "@/lib/vendor/vegaLiteMinJs";
import { VEGA_EMBED_MIN_JS } from "@/lib/vendor/vegaEmbedMinJs";

type Props = { content: string };

const PREVIEW_HEIGHT = 350;

/** Build a self-contained HTML page that renders a Vega / Vega-Lite spec via vendored, inlined Vega-Embed. */
function buildVegaHtml(spec: string, theme: Theme): string {
  const safeSpec = escapeForInlineJsTemplate(spec);
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
  try {
    const parsed = JSON.parse(spec);
    vegaEmbed('#chart', parsed, {
      actions: false,
      renderer: 'svg',
      width: 'container',
      height: ${PREVIEW_HEIGHT - 24},
    }).catch(function(err) {
      document.getElementById('error').textContent = 'Chart error: ' + err.message;
      document.getElementById('error').style.display = 'block';
    });
  } catch (e) {
    document.getElementById('error').textContent = 'Invalid spec: ' + e.message;
    document.getElementById('error').style.display = 'block';
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

  const vegaHtml = useMemo(() => buildVegaHtml(content, theme), [content, theme]);
  const source = useMemo(() => ({ html: vegaHtml }), [vegaHtml]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInlineChart = previewWebView?.mode === "rnc";
  const { canMount, onLoaded } = useDeferredWebViewMount(
    Boolean(WebView) && canRenderInlineChart,
  );
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(vegaHtml);

  const handleOpenVegaEditor = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://vega.github.io/editor/");
  }, [content]);

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Text style={s.headerIcon}>📈</Text>
          <Text style={s.headerLabel}>{t("rich.chart")}</Text>
        </View>
        <Text style={s.lineCount}>
          {t("rich.lines_count", { count: content.trim().split("\n").length })}
        </Text>
      </View>

      <View style={[s.previewBox, expanded && s.previewBoxExpanded]}>
        {WebView && canRenderInlineChart ? (
          canMount ? (
            <WebView
              originWhitelist={["*"]}
              source={source}
              style={{
                height: expanded ? PREVIEW_HEIGHT * 2 : PREVIEW_HEIGHT,
              }}
              scrollEnabled={false}
              javaScriptEnabled
              domStorageEnabled={false}
              onLoadEnd={onLoaded}
              onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
            />
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
          <Ionicons
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
          <Ionicons
            name={expanded ? "contract-outline" : "expand-outline"}
            size={18}
            color={theme.textSecondary}
          />
          <Text style={s.actionLabel}>
            {expanded ? t("rich.collapse") : t("rich.expand")}
          </Text>
        </Pressable>

        <Pressable style={s.openBtn} onPress={handleOpenVegaEditor} hitSlop={8}>
          <Ionicons name="open-outline" size={18} color={theme.onPrimary} />
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
    headerIcon: { fontSize: 16 },
    headerLabel: { fontSize: 14, fontWeight: "700", color: t.text },
    lineCount: { fontSize: 12, color: t.textTertiary },
    previewBox: {
      backgroundColor: t.bg,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    previewBoxExpanded: {},
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
