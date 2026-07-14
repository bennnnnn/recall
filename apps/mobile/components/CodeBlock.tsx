import { ReactNode, useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";

import { displayLang, groupTokensByLine, parseFenceLang, TOKEN_COLORS } from "@/lib/codeHighlight";
import type * as CodeTokenizeModule from "@/lib/codeTokenize";
import { Theme, useTheme } from "@/lib/theme";

import { CODE_FONT } from "@/lib/fonts";
const CODE_FONT_SIZE = 13;
const CODE_LINE_HEIGHT = 20;

// Prism (~47 grammars registered at module load) is only pulled in once a
// code fence actually needs tokenizing, not on every message render — see
// lib/codeTokenize.ts. Cached at module scope so only the very first
// CodeBlock in a session pays the async-import cost; every one after it
// gets the module synchronously on initial render.
let cachedTokenizer: typeof CodeTokenizeModule | null = null;

function useCodeTokenizer(): typeof CodeTokenizeModule | null {
  const [tokenizer, setTokenizer] = useState(cachedTokenizer);
  useEffect(() => {
    if (cachedTokenizer) return;
    let cancelled = false;
    void import("@/lib/codeTokenize").then((mod) => {
      cachedTokenizer = mod;
      if (!cancelled) setTokenizer(mod);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return tokenizer;
}

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

export function CodeBlock({
  code,
  lang,
  headerExtra,
  footerExtra,
  showCopy = true,
}: {
  code: string;
  lang: string;
  headerExtra?: ReactNode;
  footerExtra?: ReactNode;
  /** Math/diagram fences must not show a Copy affordance. */
  showCopy?: boolean;
}) {
  const t = useTheme();
  const s = useMemo(() => makeStyles(t), [t]);
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const fenceLang = parseFenceLang(lang);
  const tokenizer = useCodeTokenizer();
  const highlightLang = useMemo(
    () => (tokenizer ? tokenizer.resolveHighlightLang(fenceLang, code) : fenceLang),
    [tokenizer, fenceLang, code],
  );
  const tokens = useMemo(() => {
    if (!tokenizer) return [{ text: code, color: TOKEN_COLORS.plain }];
    try {
      return tokenizer.tokenize(code, fenceLang);
    } catch {
      return [{ text: code, color: TOKEN_COLORS.plain }];
    }
  }, [tokenizer, code, fenceLang]);
  const lines = useMemo(() => groupTokensByLine(tokens), [tokens]);
  const lineCount = code.split("\n").length;
  const collapsible = lineCount >= CODE_COLLAPSE_MIN_LINES;
  const collapsed = collapsible && !expanded;
  const badge = displayLang(fenceLang || highlightLang);

  // Syntax colors are saturated mid-tones that read on either background, but
  // the near-black "plain" color is invisible on a dark panel — remap it.
  const colorFor = (c: string) =>
    t.isDark && c === TOKEN_COLORS.plain ? t.codeText : c;

  const onCopy = async () => {
    await Clipboard.setStringAsync(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        {badge ? <Text style={s.lang}>{badge}</Text> : <View />}
        <View style={s.headerActions}>
          {headerExtra}
          {showCopy ? (
            <Pressable style={s.copyBtn} onPress={onCopy} hitSlop={6}>
              <Ionicons
                name={copied ? "checkmark-outline" : "copy-outline"}
                size={13}
                color={copied ? t.primary : t.textSecondary}
              />
              <Text style={[s.copyText, copied && s.copyTextDone]}>
                {copied ? " Copied" : " Copy"}
              </Text>
            </Pressable>
          ) : null}
        </View>
      </View>
      <View
        style={[
          s.codeBody,
          collapsed && {
            maxHeight: CODE_LINE_HEIGHT * CODE_COLLAPSED_LINES + 24,
          },
        ]}
      >
        <ScrollView horizontal showsHorizontalScrollIndicator={false} nestedScrollEnabled>
          <View style={s.codeLines}>
            {lines.map((lineTokens, lineIdx) => (
              <View key={lineIdx} style={s.codeLineRow}>
                {lineTokens.length > 0 ? (
                  lineTokens.map((tk, i) => (
                    <Text key={i} style={tokenStyle(colorFor(tk.color))} selectable>
                      {tk.text}
                    </Text>
                  ))
                ) : (
                  <Text style={tokenStyle(colorFor(TOKEN_COLORS.plain))}> </Text>
                )}
              </View>
            ))}
          </View>
        </ScrollView>
      </View>
      {collapsible && (
        <Pressable style={s.expandBtn} onPress={() => setExpanded((v) => !v)} hitSlop={6}>
          <Text style={s.expandText}>{expanded ? "Show less" : "Show more"}</Text>
        </Pressable>
      )}
      {footerExtra ? <View style={s.footer}>{footerExtra}</View> : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      width: "100%",
      maxWidth: "100%",
      backgroundColor: t.codeBg,
      borderRadius: 12,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
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
      borderBottomColor: t.border,
      backgroundColor: t.codeBg,
    },
    lang: {
      fontSize: 12,
      color: t.codeLang,
      fontWeight: "600",
      textTransform: "lowercase",
    },
    headerActions: { flexDirection: "row", alignItems: "center", gap: 6 },
    copyBtn: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 8,
      paddingVertical: 4,
      borderRadius: 8,
      backgroundColor: t.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    copyText: { fontSize: 12, fontWeight: "600", color: t.textSecondary },
    copyTextDone: { color: t.primary },
    codeBody: { overflow: "hidden", backgroundColor: t.codeBg },
    codeLines: { padding: 12 },
    codeLineRow: { flexDirection: "row", flexWrap: "nowrap", alignItems: "flex-start" },
    expandBtn: {
      alignItems: "center",
      paddingVertical: 8,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
      backgroundColor: t.codeBg,
    },
    expandText: { fontSize: 12, fontWeight: "600", color: t.textSecondary },
    footer: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
      gap: 4,
      paddingHorizontal: 8,
      paddingVertical: 6,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
      backgroundColor: t.surface,
    },
  });
}
