/**
 * Mermaid diagram — inline SVG render via WebView (dev build), with source fallback.
 */
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Icon } from "@/components/Icon";

import { CopyButton } from "@/components/CopyButton";
import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { CODE_FONT } from "@/lib/fonts";
import { injectPreviewCsp, inlineScript } from "@/lib/previewSandbox";
import { Theme, useTheme } from "@/lib/theme";
import {
  getPreviewWebView,
  STATIC_HTML_ORIGIN_WHITELIST,
  useStaticOnlyNavigation,
} from "@/lib/webView";
import { MERMAID_MIN_JS } from "@/lib/vendor/mermaidMinJs";

type Props = { content: string };

const PREVIEW_HEIGHT = 220;

function buildMermaidHtml(source: string, theme: Theme): string {
  const safeSpec = source
    .trim()
    .replace(/\\/g, "\\\\")
    .replace(/`/g, "\\`")
    .replace(/\$/g, "\\$")
    .replace(/<\/script>/gi, "<\\/script>");
  const mermaidTheme = theme.isDark ? "dark" : "neutral";
  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>${inlineScript(MERMAID_MIN_JS)}</script>
<style>
  body { margin: 0; padding: 8px; font-family: -apple-system, sans-serif; background: ${theme.bg}; }
  #err { color: ${theme.danger}; font-size: 12px; display: none; white-space: pre-wrap; padding: 8px; }
  .mermaid { display: flex; justify-content: center; }
</style>
</head>
<body>
<pre class="mermaid" id="diagram"></pre>
<div id="err"></div>
<script>
  const src = \`${safeSpec}\`;
  function reportError(msg) {
    try { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify({ kind: 'mermaid-error', message: msg })); } catch (e) {}
    var el = document.getElementById('err');
    el.textContent = 'Diagram error: ' + msg;
    el.style.display = 'block';
  }
  const el = document.getElementById('diagram');
  el.textContent = src;
  mermaid.initialize({ startOnLoad: false, theme: '${mermaidTheme}', securityLevel: 'strict' });
  mermaid.run({ nodes: [el] }).catch(function(err) { reportError(err && err.message ? err.message : String(err)); });
</script>
</body>
</html>`);
}

export function MermaidBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [showSource, setShowSource] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);

  const mermaidHtml = useMemo(() => buildMermaidHtml(content.trim(), theme), [content, theme]);
  const source = useMemo(() => ({ html: mermaidHtml }), [mermaidHtml]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc";
  const { canMount, onLoaded } = useDeferredWebViewMount(Boolean(WebView) && canRenderInline);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(mermaidHtml);

  const handleWebViewMessage = useCallback((event: { nativeEvent: { data?: string } }) => {
    try {
      const data = JSON.parse(event.nativeEvent.data ?? "{}");
      if (data && data.kind === "mermaid-error") setRenderError(data.message ?? t("rich.mermaid_error"));
    } catch {
      setRenderError(t("rich.mermaid_error"));
    }
  }, [t]);

  const handleOpenLiveEditor = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://mermaid.live/edit");
  }, [content]);

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Icon name="git-network-outline" size={16} color={theme.primary} />
          <Text style={s.headerLabel}>{t("rich.mermaid_diagram")}</Text>
        </View>
        <Pressable
          onPress={() => setShowSource((v) => !v)}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={showSource ? t("rich.diagram") : t("rich.source")}
        >
          <Icon
            name={showSource ? "eye-off-outline" : "code-slash-outline"}
            size={20}
            color={theme.primary}
          />
        </Pressable>
      </View>

      {renderError ? (
        <View style={s.previewBox}>
          <Icon name="alert-circle-outline" size={20} color={theme.danger} />
          <Text style={[s.previewText, { color: theme.danger }]}>
            {renderError}
          </Text>
        </View>
      ) : showSource ? (
        <View style={s.previewBox}>
          <Text style={s.previewText}>{content.trim()}</Text>
        </View>
      ) : canRenderInline && WebView ? (
        canMount ? (
          <View style={[s.webWrap, expanded && s.webWrapExpanded]}>
            <WebView
              originWhitelist={STATIC_HTML_ORIGIN_WHITELIST}
              source={source}
              scrollEnabled={false}
              style={s.webview}
              javaScriptEnabled
              domStorageEnabled={false}
              onLoadEnd={onLoaded}
              onMessage={handleWebViewMessage}
              onShouldStartLoadWithRequest={onShouldStartLoadWithRequest}
            />
          </View>
        ) : (
          <View style={s.loadingWrap}>
            <ActivityIndicator color={theme.primary} />
          </View>
        )
      ) : (
        <View style={s.previewBox}>
          <Text style={s.previewText} numberOfLines={6}>
            {content.trim()}
          </Text>
          <Text style={s.fallbackHint}>{t("rich.mermaid_dev_build")}</Text>
        </View>
      )}

      <View style={s.actions}>
        <CopyButton text={content} />
        <Pressable
          style={s.iconBtn}
          onPress={() => setExpanded((v) => !v)}
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
        <Pressable style={s.openBtn} onPress={handleOpenLiveEditor} hitSlop={8}>
          <Icon name="open-outline" size={18} color={theme.onPrimary} />
          <Text style={s.openLabel}>{t("rich.mermaid_live")}</Text>
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
    webWrap: { height: PREVIEW_HEIGHT, backgroundColor: t.bg },
    webWrapExpanded: { height: PREVIEW_HEIGHT * 2 },
    webview: { flex: 1, backgroundColor: "transparent" },
    loadingWrap: {
      height: PREVIEW_HEIGHT,
      backgroundColor: t.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    previewBox: {
      paddingHorizontal: 14,
      paddingVertical: 10,
      backgroundColor: t.contentSurface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    previewText: { fontFamily: CODE_FONT, fontSize: 11, lineHeight: 17, color: t.textSecondary },
    fallbackHint: { fontSize: 12, color: t.textTertiary, marginTop: 8 },
    actions: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      paddingHorizontal: 10,
      paddingVertical: 6,
      flexWrap: "wrap",
    },
    iconBtn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
    },
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
