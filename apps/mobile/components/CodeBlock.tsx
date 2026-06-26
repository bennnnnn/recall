import { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";
import {
  displayLang,
  groupTokensByLine,
  parseFenceLang,
  resolveHighlightLang,
  TOKEN_COLORS,
  tokenize,
} from "@/lib/codeHighlight";

import { CODE_FONT } from "@/lib/fonts";
const CODE_FONT_SIZE = 13;
const CODE_LINE_HEIGHT = 20;

function tokenStyle(color: string) {
  return {
    fontFamily: CODE_FONT,
    fontSize: CODE_FONT_SIZE,
    lineHeight: CODE_LINE_HEIGHT,
    color,
  };
}

const CODE_COLLAPSED_LINES = 14;
/** Only fold code blocks with at least this many lines. */
const CODE_COLLAPSE_MIN_LINES = 18;

export function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const fenceLang = parseFenceLang(lang);
  const highlightLang = resolveHighlightLang(fenceLang, code);
  const tokens = useMemo(() => {
    try {
      return tokenize(code, fenceLang);
    } catch {
      return [{ text: code, color: TOKEN_COLORS.plain }];
    }
  }, [code, fenceLang]);
  const lines = useMemo(() => groupTokensByLine(tokens), [tokens]);
  const lineCount = code.split("\n").length;
  const collapsible = lineCount >= CODE_COLLAPSE_MIN_LINES;
  const collapsed = collapsible && !expanded;
  const badge = displayLang(fenceLang || highlightLang);

  const onCopy = async () => {
    await Clipboard.setStringAsync(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        {badge ? <Text style={s.lang}>{badge}</Text> : <View />}
        <Pressable style={s.copyBtn} onPress={onCopy} hitSlop={6}>
          <Ionicons
            name={copied ? "checkmark-outline" : "copy-outline"}
            size={13}
            color={copied ? C.primary : C.textSecondary}
          />
          <Text style={[s.copyText, copied && s.copyTextDone]}>
            {copied ? " Copied" : " Copy"}
          </Text>
        </Pressable>
      </View>
      <View
        style={[
          s.codeBody,
          collapsed && {
            maxHeight: CODE_LINE_HEIGHT * CODE_COLLAPSED_LINES + 24,
          },
        ]}
      >
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          nestedScrollEnabled
        >
          <View style={s.codeLines}>
            {lines.map((lineTokens, lineIdx) => (
              <View key={lineIdx} style={s.codeLineRow}>
                {lineTokens.length > 0 ? (
                  lineTokens.map((t, i) => (
                    <Text key={i} style={tokenStyle(t.color)} selectable>
                      {t.text}
                    </Text>
                  ))
                ) : (
                  <Text style={tokenStyle(TOKEN_COLORS.plain)}> </Text>
                )}
              </View>
            ))}
          </View>
        </ScrollView>
      </View>
      {collapsible && (
        <Pressable
          style={s.expandBtn}
          onPress={() => setExpanded((v) => !v)}
          hitSlop={6}
        >
          <Text style={s.expandText}>
            {expanded ? "Show less" : "Show more"}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: {
    alignSelf: "stretch",
    width: "100%",
    maxWidth: "100%",
    backgroundColor: C.codeBg,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
    overflow: "hidden",
    marginVertical: 6,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
    backgroundColor: C.codeBg,
  },
  lang: {
    fontSize: 12,
    color: C.codeLang,
    fontWeight: "600",
    textTransform: "lowercase",
  },
  copyBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    backgroundColor: C.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.border,
  },
  copyText: { fontSize: 12, fontWeight: "600", color: C.textSecondary },
  copyTextDone: { color: C.primary },
  codeBody: { overflow: "hidden", backgroundColor: C.codeBg },
  codeLines: { padding: 12 },
  codeLineRow: {
    flexDirection: "row",
    flexWrap: "nowrap",
    alignItems: "flex-start",
  },
  expandBtn: {
    alignItems: "center",
    paddingVertical: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.border,
    backgroundColor: C.codeBg,
  },
  expandText: { fontSize: 12, fontWeight: "600", color: C.textSecondary },
});
