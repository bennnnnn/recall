/**
 * Chart block — renders ```chart / ```vega / ```vega-lite / ```plot fences
 * inline via WebView + Vega-Embed so the user sees the actual chart, not raw JSON.
 */
import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Ionicons } from "@expo/vector-icons";

import { CODE_FONT } from "@/lib/fonts";
import { Theme, useTheme } from "@/lib/theme";
import { getPreviewWebView } from "@/lib/webView";

type Props = { content: string };

const PREVIEW_HEIGHT = 350;

/** Build a self-contained HTML page that renders a Vega / Vega-Lite spec via CDN. */
function buildVegaHtml(spec: string, isDark: boolean): string {
  const safeSpec = spec
    .replace(/`/g, "\\`")
    .replace(/\${/g, "\\${")
    .replace(/<\/script>/gi, "<\\/script>");
  const bg = isDark ? "#212121" : "#ffffff";
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { display: flex; justify-content: center; align-items: center; min-height: 100vh; font-family: -apple-system, sans-serif; background: ${bg}; }
  #chart { width: 100%; max-width: 100%; padding: 8px; }
  #error { color: #dc2626; padding: 16px; font-size: 13px; display: none; white-space: pre-wrap; word-break: break-word; }
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
</html>`;
}

export function ChartBlock({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showSource, setShowSource] = useState(false);

  const vegaHtml = useMemo(
    () => buildVegaHtml(content, theme.isDark),
    [content, theme.isDark],
  );
  const previewWebView = getPreviewWebView();
  const WebView = previewWebView?.Component;
  const canRenderInlineChart = previewWebView?.mode === "rnc";

  const handleCopy = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [content]);

  const handleOpenVegaEditor = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://vega.github.io/editor/");
  }, [content]);

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Text style={s.headerIcon}>📈</Text>
          <Text style={s.headerLabel}>Chart</Text>
        </View>
        <Text style={s.lineCount}>
          {content.trim().split("\n").length} lines
        </Text>
      </View>

      <View style={[s.previewBox, expanded && s.previewBoxExpanded]}>
        {WebView && canRenderInlineChart ? (
          <WebView
            originWhitelist={["*"]}
            source={{ html: vegaHtml }}
            style={{
              height: expanded ? PREVIEW_HEIGHT * 2 : PREVIEW_HEIGHT,
            }}
            scrollEnabled={false}
            javaScriptEnabled
            domStorageEnabled
          />
        ) : (
          <View style={s.previewPlaceholder}>
            <Text style={s.previewPlaceholderText}>
              Chart preview requires a dev build
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
            Source
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
            {expanded ? "Collapse" : "Expand"}
          </Text>
        </Pressable>

        <Pressable style={s.openBtn} onPress={handleOpenVegaEditor} hitSlop={8}>
          <Ionicons name="open-outline" size={18} color="#fff" />
          <Text style={s.openLabel}>Vega Editor</Text>
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
    openLabel: { fontSize: 14, fontWeight: "700", color: "#fff" },
  });
}
