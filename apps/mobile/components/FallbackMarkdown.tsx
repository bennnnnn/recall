/**
 * Minimal markdown when the rich renderer fails — still formats headers,
 * tables, bold, and code (no Prism / rich cards).
 */
import { useMemo } from "react";
import Markdown, { renderRules as defaultRules } from "react-native-markdown-display";
import { StyleSheet, Text, View } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import { markdownItInstance } from "@/lib/markdownIt";
import { preprocessMarkdown } from "@/lib/markdownPreprocess";
import { Theme, useTheme } from "@/lib/theme";

type FenceNode = { key: string; content: string; info?: string };

type Props = { content: string };

export function FallbackMarkdown({ content }: Props) {
  const theme = useTheme();
  const mdStyles = useMemo(() => makeMdStyles(theme), [theme]);
  const fenceStyles = useMemo(() => makeFenceStyles(theme), [theme]);
  const rules = useMemo(
    () => ({
      ...defaultRules,
      fence: (node: FenceNode) => {
        const code = node.content.replace(/\n$/, "").trim();
        if (!code) return null;
        const lang = node.info?.trim().toLowerCase();
        return (
          <View key={node.key} style={fenceStyles.codeWrap}>
            {lang ? <Text style={fenceStyles.lang}>{lang}</Text> : null}
            <Text style={fenceStyles.code} selectable>
              {code}
            </Text>
          </View>
        );
      },
      code_block: (node: FenceNode) => {
        const code = node.content.replace(/\n$/, "").trim();
        if (!code) return null;
        const lang = node.info?.trim().toLowerCase();
        return (
          <View key={node.key} style={fenceStyles.codeWrap}>
            {lang ? <Text style={fenceStyles.lang}>{lang}</Text> : null}
            <Text style={fenceStyles.code} selectable>
              {code}
            </Text>
          </View>
        );
      },
    }),
    [fenceStyles],
  );
  const prepared = useMemo(() => preprocessMarkdown(content), [content]);

  return (
    <Markdown
      style={mdStyles}
      rules={rules as never}
      markdownit={markdownItInstance}
    >
      {prepared}
    </Markdown>
  );
}

function makeMdStyles(t: Theme) {
  return StyleSheet.create({
    body: { color: t.assistantText, fontSize: 16, lineHeight: 24 },
    code_inline: {
      fontFamily: CODE_FONT,
      backgroundColor: t.contentSurface,
      borderRadius: 4,
      paddingHorizontal: 4,
      fontSize: 14,
    },
    heading1: { fontSize: 20, fontWeight: "700", marginVertical: 8 },
    heading2: { fontSize: 18, fontWeight: "700", marginVertical: 6 },
    heading3: { fontSize: 16, fontWeight: "600", marginVertical: 4 },
    strong: { fontWeight: "700" },
    blockquote: {
      borderLeftWidth: 3,
      borderLeftColor: t.primary,
      paddingLeft: 12,
      marginVertical: 8,
    },
    table: { marginVertical: 8 },
    link: { color: t.primary },
  });
}

function makeFenceStyles(t: Theme) {
  return StyleSheet.create({
    codeWrap: {
      backgroundColor: t.codeBg,
      borderRadius: 10,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      marginVertical: 8,
      overflow: "hidden",
    },
    lang: {
      fontSize: 11,
      fontWeight: "600",
      color: t.codeLang,
      textTransform: "lowercase",
      paddingHorizontal: 12,
      paddingTop: 8,
    },
    code: {
      fontFamily: CODE_FONT,
      fontSize: 13,
      lineHeight: 20,
      color: t.text,
      padding: 12,
    },
  });
}
