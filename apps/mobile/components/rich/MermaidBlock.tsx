/**
 * Mermaid diagram — inline SVG render via WebView (dev build), with source fallback.
 */
import { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Ionicons } from "@expo/vector-icons";

import { useDeferredWebViewMount } from "@/hooks/useDeferredWebViewMount";
import { CODE_FONT } from "@/lib/fonts";
import { injectPreviewCsp } from "@/lib/previewSandbox";
import { Theme, useTheme } from "@/lib/theme";
import { getPreviewWebView, useStaticOnlyNavigation } from "@/lib/webView";

type Props = { content: string };

const PREVIEW_HEIGHT = 220;

function buildMermaidHtml(source: string, isDark: boolean): string {
  const safeSpec = source
    .trim()
    .replace(/\\/g, "\\\\")
    .replace(/`/g, "\\`")
    .replace(/\$/g, "\\$")
    .replace(/<\/script>/gi, "<\\/script>");
  const bg = isDark ? "#212121" : "#ffffff";
  const theme = isDark ? "dark" : "neutral";
  return injectPreviewCsp(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body { margin: 0; padding: 8px; font-family: -apple-system, sans-serif; background: ${bg}; }
  #err { color: #dc2626; font-size: 12px; display: none; white-space: pre-wrap; padding: 8px; }
  .mermaid { display: flex; justify-content: center; }
</style>
</head>
<body>
<pre class="mermaid" id="diagram"></pre>
<div id="err"></div>
<script>
  const src = \`${safeSpec}\`;
  const el = document.getElementById('diagram');
  el.textContent = src;
  mermaid.initialize({ startOnLoad: false, theme: '${theme}', securityLevel: 'strict' });
  mermaid.run({ nodes: [el] }).catch(function(err) {
    document.getElementById('err').textContent = 'Diagram error: ' + err.message;
    document.getElementById('err').style.display = 'block';
  });
</script>
</body>
</html>`);
}

export function MermaidBlock({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [copied, setCopied] = useState(false);
  const [showSource, setShowSource] = useState(false);

  const mermaidHtml = useMemo(
    () => buildMermaidHtml(content.trim(), theme.isDark),
    [content, theme.isDark],
  );
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc";
  const { canMount, onLoaded } = useDeferredWebViewMount(Boolean(WebView) && canRenderInline);
  const onShouldStartLoadWithRequest = useStaticOnlyNavigation(mermaidHtml);

  const handleCopy = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [content]);

  const handleOpenLiveEditor = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://mermaid.live/edit");
  }, [content]);

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Text style={s.headerIcon}>📊</Text>
          <Text style={s.headerLabel}>Mermaid Diagram</Text>
        </View>
        <Pressable onPress={() => setShowSource((v) => !v)} hitSlop={8}>
          <Text style={s.toggleSource}>{showSource ? "Diagram" : "Source"}</Text>
        </Pressable>
      </View>

      {showSource ? (
        <View style={s.previewBox}>
          <Text style={s.previewText}>{content.trim()}</Text>
        </View>
      ) : canRenderInline && WebView ? (
        canMount ? (
          <View style={s.webWrap}>
            <WebView
              originWhitelist={["*"]}
              source={{ html: mermaidHtml }}
              scrollEnabled={false}
              style={s.webview}
              javaScriptEnabled
              onLoadEnd={onLoaded}
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
          <Text style={s.fallbackHint}>Build the app to preview diagrams inline.</Text>
        </View>
      )}

      <View style={s.actions}>
        <Pressable style={s.actionBtn} onPress={handleCopy} hitSlop={8}>
          <Ionicons
            name={copied ? "checkmark-circle" : "copy-outline"}
            size={18}
            color={copied ? theme.primary : theme.textSecondary}
          />
          <Text style={[s.actionLabel, copied && s.actionLabelActive]}>
            {copied ? "Copied" : "Copy"}
          </Text>
        </Pressable>
        <Pressable style={s.openBtn} onPress={handleOpenLiveEditor} hitSlop={8}>
          <Ionicons name="open-outline" size={18} color="#fff" />
          <Text style={s.openLabel}>Mermaid Live</Text>
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
    toggleSource: { fontSize: 13, fontWeight: "600", color: t.primary },
    webWrap: { height: PREVIEW_HEIGHT, backgroundColor: t.bg },
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
    actions: { flexDirection: "row", gap: 10, paddingHorizontal: 14, paddingVertical: 10 },
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
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 6,
      paddingVertical: 10,
      borderRadius: 10,
      backgroundColor: t.primary,
    },
    openLabel: { fontSize: 14, fontWeight: "700", color: t.onPrimary },
  });
}
