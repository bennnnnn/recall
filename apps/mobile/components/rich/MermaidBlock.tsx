/**
 * Mermaid diagram — inline SVG render via WebView (dev build), with source fallback.
 */
import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";
import { CODE_FONT } from "@/lib/fonts";
import { getPreviewWebView } from "@/lib/webView";

type Props = { content: string };

const PREVIEW_HEIGHT = 220;

function buildMermaidHtml(source: string): string {
  const safeSpec = source
    .trim()
    .replace(/\\/g, "\\\\")
    .replace(/`/g, "\\`")
    .replace(/\$/g, "\\$")
    .replace(/<\/script>/gi, "<\\/script>");
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body { margin: 0; padding: 8px; font-family: -apple-system, sans-serif; background: #fff; }
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
  mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict' });
  mermaid.run({ nodes: [el] }).catch(function(err) {
    document.getElementById('err').textContent = 'Diagram error: ' + err.message;
    document.getElementById('err').style.display = 'block';
  });
</script>
</body>
</html>`;
}

export function MermaidBlock({ content }: Props) {
  const [copied, setCopied] = useState(false);
  const [showSource, setShowSource] = useState(false);

  const mermaidHtml = useMemo(() => buildMermaidHtml(content.trim()), [content]);
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInline = previewWebView?.mode === "rnc";

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
        <View style={s.webWrap}>
          <WebView
            originWhitelist={["*"]}
            source={{ html: mermaidHtml }}
            scrollEnabled={false}
            style={s.webview}
            javaScriptEnabled
          />
        </View>
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
            color={copied ? C.primary : C.textSecondary}
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

const s = StyleSheet.create({
  wrap: {
    marginVertical: 8,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    overflow: "hidden",
    backgroundColor: "#fff",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: C.surface,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  headerLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  headerIcon: { fontSize: 16 },
  headerLabel: { fontSize: 14, fontWeight: "700", color: C.text },
  toggleSource: { fontSize: 13, fontWeight: "600", color: C.primary },
  webWrap: { height: PREVIEW_HEIGHT, backgroundColor: "#fff" },
  webview: { flex: 1, backgroundColor: "transparent" },
  previewBox: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: "#fafafa",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  previewText: { fontFamily: CODE_FONT, fontSize: 11, lineHeight: 17, color: C.textSecondary },
  fallbackHint: { fontSize: 12, color: C.textTertiary, marginTop: 8 },
  actions: { flexDirection: "row", gap: 10, paddingHorizontal: 14, paddingVertical: 10 },
  actionBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 10,
    backgroundColor: C.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
  },
  actionLabel: { fontSize: 14, fontWeight: "600", color: C.textSecondary },
  actionLabelActive: { color: C.primary },
  openBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: "#6C5CE7",
  },
  openLabel: { fontSize: 14, fontWeight: "700", color: "#fff" },
});
