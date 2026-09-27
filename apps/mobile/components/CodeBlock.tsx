import { ReactNode, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { groupTokensByLine, parseFenceLang, resolveTokenColor, TOKEN_COLORS } from "@/lib/codeHighlight";
import type * as CodeTokenizeModule from "@/lib/codeTokenize";
import { Radius } from "@/lib/radius";
import { Theme, useTheme } from "@/lib/theme";

import { CopyButton } from "@/components/CopyButton";

import { CODE_FONT } from "@/lib/fonts";
import { Space } from "@/lib/space";
const CODE_FONT_SIZE = 13;
const CODE_LINE_HEIGHT = 20;

// Prism (~47 grammars registered at module load) is only pulled in once a
// code fence actually needs tokenizing, not on every message render — see
// lib/codeTokenize.ts. Cached at module scope so only the very first
// CodeBlock in a session pays the async-import cost; every one after it
// gets the module synchronously on initial render.
let cachedTokenizer: typeof CodeTokenizeModule | null = null;

function useCodeTokenizer(enabled: boolean): typeof CodeTokenizeModule | null {
  const [tokenizer, setTokenizer] = useState(enabled ? cachedTokenizer : null);
  useEffect(() => {
    if (!enabled) {
      setTokenizer(null);
      return;
    }
    if (cachedTokenizer) {
      setTokenizer(cachedTokenizer);
      return;
    }
    let cancelled = false;
    void import("@/lib/codeTokenize").then((mod) => {
      cachedTokenizer = mod;
      if (!cancelled) setTokenizer(mod);
    });
    return () => {
      cancelled = true;
    };
  }, [enabled]);
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
/** Room at the end of each line before the corner actions are measured: one copy button. */
const ACTIONS_GUTTER = 40;

export function CodeBlock({
  code,
  lang,
  headerExtra,
  footerExtra,
  showCopy = true,
  /** Open-fence stream: plain monospace, no Prism / copy / collapse. */
  streaming = false,
}: {
  code: string;
  lang: string;
  headerExtra?: ReactNode;
  footerExtra?: ReactNode;
  /** Math/diagram fences must not show a Copy affordance. */
  showCopy?: boolean;
  streaming?: boolean;
}) {
  const t = useTheme();
  const { t: tr } = useTranslation();
  const s = useMemo(() => makeStyles(t), [t]);
  const [expanded, setExpanded] = useState(false);
  // The corner holds copy plus any extras (HTML adds a 44 pt preview button),
  // so the line gutter follows the measured width, not one button's.
  const [actionsWidth, setActionsWidth] = useState(0);
  const fenceLang = parseFenceLang(lang);
  const tokenizer = useCodeTokenizer(!streaming);
  const tokens = useMemo(() => {
    // While the fence is still open, skip Prism — retokenizing a growing
    // body every ~48ms is the jank the open-fence stream path avoids.
    if (streaming || !tokenizer) return [{ text: code, color: TOKEN_COLORS.plain }];
    try {
      return tokenizer.tokenize(code, fenceLang);
    } catch {
      return [{ text: code, color: TOKEN_COLORS.plain }];
    }
  }, [streaming, tokenizer, code, fenceLang]);
  const lines = useMemo(() => groupTokensByLine(tokens), [tokens]);
  const lineCount = code.split("\n").length;
  const collapsible = !streaming && lineCount >= CODE_COLLAPSE_MIN_LINES;
  const collapsed = collapsible && !expanded;
  const copyEnabled = showCopy && !streaming;
  const hasActions = copyEnabled || Boolean(headerExtra);

  // Syntax colors are saturated mid-tones that read on either background, but
  // the near-black "plain" color is invisible on a dark panel — remap it.
  const colorFor = (c: string) => resolveTokenColor(c, t.isDark);

  return (
    // A clean card: code first, copy floating in the corner, no header bar
    // or language label (the code says what it is).
    <View style={s.wrap}>
      <View
        style={[
          s.codeBody,
          collapsed && {
            maxHeight: CODE_LINE_HEIGHT * CODE_COLLAPSED_LINES + 24,
          },
        ]}
      >
        <ScrollView
          testID="code-block-scroll"
          horizontal
          showsHorizontalScrollIndicator={false}
          nestedScrollEnabled
          directionalLockEnabled
          style={s.codeScroller}
          contentContainerStyle={s.codeScrollContent}
        >
          <View
            testID="code-block-lines"
            style={[
              s.codeLines,
              hasActions && { paddingRight: Space.md + (actionsWidth || ACTIONS_GUTTER) },
            ]}
          >
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
      {hasActions ? (
        <View
          style={s.actions}
          testID="code-block-actions"
          onLayout={(e) => setActionsWidth(Math.ceil(e.nativeEvent.layout.width))}
        >
          {headerExtra}
          {copyEnabled ? <CopyButton text={code} /> : null}
        </View>
      ) : null}
      {collapsible && (
        <Pressable
          style={s.expandBtn}
          onPress={() => setExpanded((v) => !v)}
          hitSlop={6}
          accessibilityRole="button"
          accessibilityLabel={expanded ? tr("common.show_less") : tr("common.show_more")}
        >
          <Text style={s.expandText}>{expanded ? tr("common.show_less") : tr("common.show_more")}</Text>
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
      borderRadius: Radius.card,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      overflow: "hidden",
      marginTop: 0,
      marginBottom: 10,
    },
    actions: {
      position: "absolute",
      top: Space.xs,
      right: Space.xs,
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      borderRadius: Radius.xs,
      // Masks a long first line that scrolls under the buttons.
      backgroundColor: t.codeBg,
    },
    codeBody: {
      overflow: "hidden",
      backgroundColor: t.codeBg,
      width: "100%",
      maxWidth: "100%",
      minWidth: 0,
    },
    codeScroller: { width: "100%", maxWidth: "100%", minWidth: 0 },
    codeScrollContent: { flexGrow: 0 },
    codeLines: {
      paddingVertical: Space.md,
      paddingHorizontal: Space.md,
      alignSelf: "flex-start",
    },
    codeLineRow: { flexDirection: "row", flexWrap: "nowrap", alignItems: "flex-start" },
    expandBtn: {
      alignItems: "center",
      paddingVertical: Space.xs,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
      backgroundColor: t.codeBg,
    },
    expandText: { fontSize: 12, fontWeight: "600", color: t.textSecondary },
    footer: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
      gap: Space.xxs,
      paddingHorizontal: Space.xs,
      paddingVertical: 6,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
      backgroundColor: t.surface,
    },
  });
}
