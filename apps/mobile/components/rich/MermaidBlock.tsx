/**
 * Mermaid diagram block — shows ```mermaid fences with Copy + Open in Mermaid Live.
 */
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as WebBrowser from "expo-web-browser";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";
import { CODE_FONT } from "@/lib/fonts";

type Props = { content: string };

function previewLines(code: string, maxLines = 4): string {
  return code.trim().split("\n").slice(0, maxLines).join("\n");
}

export function MermaidBlock({ content }: Props) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const lines = content.trim().split("\n");
  const preview = previewLines(content);

  const handleCopy = useCallback(async () => {
    await Clipboard.setStringAsync(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [content]);

  const handleOpenLiveEditor = useCallback(async () => {
    // Copy first, then open the Mermaid Live Editor for pasting.
    await Clipboard.setStringAsync(content);
    await WebBrowser.openBrowserAsync("https://mermaid.live/edit");
  }, [content]);

  return (
    <View style={s.wrap}>
      {/* Header */}
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Text style={s.headerIcon}>📊</Text>
          <Text style={s.headerLabel}>Mermaid Diagram</Text>
        </View>
        <Text style={s.lineCount}>{lines.length} lines</Text>
      </View>

      {/* Source preview */}
      <Pressable style={s.previewBox} onPress={() => setExpanded(v => !v)}>
        <Text style={s.previewText} numberOfLines={expanded ? undefined : 4}>
          {expanded ? content.trim() : preview}
        </Text>
        {!expanded && lines.length > 4 && (
          <View style={s.showMore}>
            <Text style={s.showMoreText}>Show all</Text>
            <Ionicons name="chevron-down" size={12} color={C.primary} />
          </View>
        )}
        {expanded && lines.length > 4 && (
          <View style={s.showMore}>
            <Text style={s.showMoreText}>Show less</Text>
            <Ionicons name="chevron-up" size={12} color={C.primary} />
          </View>
        )}
      </Pressable>

      {/* Actions */}
      <View style={s.actions}>
        <Pressable style={s.actionBtn} onPress={handleCopy} hitSlop={8}>
          <Ionicons name={copied ? "checkmark-circle" : "copy-outline"} size={18} color={copied ? C.primary : C.textSecondary} />
          <Text style={[s.actionLabel, copied && s.actionLabelActive]}>{copied ? "Copied" : "Copy"}</Text>
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
  wrap: { marginVertical: 8, borderRadius: 14, borderWidth: StyleSheet.hairlineWidth, borderColor: C.border, overflow: "hidden", backgroundColor: "#fff" },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 14, paddingVertical: 10, backgroundColor: C.surface, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  headerLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  headerIcon: { fontSize: 16 },
  headerLabel: { fontSize: 14, fontWeight: "700", color: C.text },
  lineCount: { fontSize: 12, color: C.textTertiary },
  previewBox: { paddingHorizontal: 14, paddingVertical: 10, backgroundColor: "#fafafa", borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  previewText: { fontFamily: CODE_FONT, fontSize: 11, lineHeight: 17, color: C.textSecondary },
  showMore: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 8 },
  showMoreText: { fontSize: 12, fontWeight: "600", color: C.primary },
  actions: { flexDirection: "row", gap: 10, paddingHorizontal: 14, paddingVertical: 10 },
  actionBtn: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 8, paddingHorizontal: 14, borderRadius: 10, backgroundColor: C.surface, borderWidth: StyleSheet.hairlineWidth, borderColor: C.border },
  actionLabel: { fontSize: 14, fontWeight: "600", color: C.textSecondary },
  actionLabelActive: { color: C.primary },
  openBtn: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: 10, borderRadius: 10, backgroundColor: "#6C5CE7" },
  openLabel: { fontSize: 14, fontWeight: "700", color: "#fff" },
});
