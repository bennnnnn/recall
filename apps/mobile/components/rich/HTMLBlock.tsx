/**
 * HTML block renderer — renders ```html fences inline via WebView so the
 * user can see the UI the model generated directly in chat.
 *
 * Actions: Copy source | Open in Browser | Expand / Collapse
 */
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { WebView } from "react-native-webview";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";
import { CODE_FONT } from "@/lib/fonts";

type Props = { content: string; title?: string };

const PREVIEW_HEIGHT = 320;

/** Wrap bare HTML into a full document for browser / WebView rendering. */
function wrapFullDocument(html: string): string {
  if (/^\s*<!DOCTYPE/i.test(html) || /^\s*<html/i.test(html)) {
    return html;
  }
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 16px; line-height: 1.5; color: #1a1a1a; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; }
  td, th { border: 1px solid #ddd; padding: 8px; }
  th { background: #f5f5f5; font-weight: 600; }
  pre { background: #f5f5f5; padding: 12px; border-radius: 8px; overflow-x: auto; }
  code { font-family: 'SF Mono', monospace; font-size: 14px; }
  img { max-width: 100%; }
</style>
</head>
<body>
${html}
</body>
</html>`;
}

export function HTMLBlock({ content, title }: Props) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showSource, setShowSource] = useState(false);

  const fullHtml = wrapFullDocument(content);

  const handleCopy = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [content]);

  const handleOpenInBrowser = useCallback(async () => {
    try {
      await WebBrowser.openBrowserAsync(
        `data:text/html;charset=utf-8,${encodeURIComponent(fullHtml)}`,
      );
    } catch {
      await Clipboard.setStringAsync(content);
    }
  }, [fullHtml, content]);

  return (
    <View style={s.wrap}>
      {/* Header */}
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Ionicons name="globe-outline" size={16} color={C.primary} />
          <Text style={s.headerLabel}>{title || "HTML Preview"}</Text>
        </View>
        <Text style={s.lineCount}>
          {content.trim().split("\n").length} lines
        </Text>
      </View>

      {/* Inline WebView preview */}
      <View style={[s.previewBox, expanded && s.previewBoxExpanded]}>
        <WebView
          originWhitelist={["*"]}
          source={{ html: fullHtml }}
          style={{ height: expanded ? PREVIEW_HEIGHT * 2 : PREVIEW_HEIGHT }}
          scrollEnabled
          javaScriptEnabled
          domStorageEnabled
        />
      </View>

      {/* Source toggle */}
      {showSource && (
        <View style={s.sourceBox}>
          <Text style={s.sourceText} selectable>
            {content.trim()}
          </Text>
        </View>
      )}

      {/* Action buttons */}
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

        <Pressable
          style={s.actionBtn}
          onPress={() => setShowSource((v) => !v)}
          hitSlop={8}
        >
          <Ionicons
            name={showSource ? "eye-off-outline" : "code-slash-outline"}
            size={18}
            color={showSource ? C.primary : C.textSecondary}
          />
          <Text
            style={[s.actionLabel, showSource && s.actionLabelActive]}
          >
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
            color={C.textSecondary}
          />
          <Text style={s.actionLabel}>
            {expanded ? "Collapse" : "Expand"}
          </Text>
        </Pressable>

        <Pressable
          style={s.openBtn}
          onPress={handleOpenInBrowser}
          hitSlop={8}
        >
          <Ionicons name="open-outline" size={18} color="#fff" />
          <Text style={s.openLabel}>Browser</Text>
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
  headerLabel: { fontSize: 14, fontWeight: "700", color: C.text },
  lineCount: { fontSize: 12, color: C.textTertiary },
  previewBox: {
    backgroundColor: "#fff",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  previewBoxExpanded: {},
  sourceBox: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: "#fafafa",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
    maxHeight: 200,
  },
  sourceText: {
    fontFamily: CODE_FONT,
    fontSize: 11,
    lineHeight: 17,
    color: C.textSecondary,
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
    backgroundColor: C.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
  },
  actionLabel: { fontSize: 14, fontWeight: "600", color: C.textSecondary },
  actionLabelActive: { color: C.primary },
  openBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
    backgroundColor: C.primary,
  },
  openLabel: { fontSize: 14, fontWeight: "700", color: "#fff" },
});
