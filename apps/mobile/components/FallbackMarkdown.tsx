/**
 * Minimal markdown when the rich renderer fails — still formats headers,
 * tables, bold, and code (no Prism / rich cards). Callout fences render as
 * styled prose instead of raw "callout-tip" code.
 */
import { useMemo } from "react";
import Markdown, { renderRules as defaultRules } from "react-native-markdown-display";
import { StyleSheet, Text, View } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import { markdownItInstance } from "@/lib/markdownIt";
import { preprocessMarkdown } from "@/lib/markdownPreprocess";
import { classifyFallbackFence } from "@/lib/fallbackFence";
import { Theme, useTheme } from "@/lib/theme";

type FenceNode = { key: string; content: string; info?: string };

type Props = { content: string };

const CALLOUT_LABELS: Record<string, string> = {
  tip: "Tip",
  note: "Note",
  warning: "Warning",
  info: "Info",
  important: "Important",
};

export function FallbackMarkdown({ content }: Props) {
  const theme = useTheme();
  const mdStyles = useMemo(() => makeMdStyles(theme), [theme]);
  const fenceStyles = useMemo(() => makeFenceStyles(theme), [theme]);
  const calloutStyles = useMemo(() => makeCalloutStyles(theme), [theme]);
  const rules = useMemo(
    () => ({
      ...defaultRules,
      fence: (node: FenceNode) => renderFallbackFence(node, fenceStyles, calloutStyles),
      code_block: (node: FenceNode) => renderFallbackFence(node, fenceStyles, calloutStyles),
    }),
    [fenceStyles, calloutStyles],
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

function renderFallbackFence(
  node: FenceNode,
  fenceStyles: ReturnType<typeof makeFenceStyles>,
  calloutStyles: ReturnType<typeof makeCalloutStyles>,
) {
  const classified = classifyFallbackFence(node.info, node.content);
  if (classified.kind === "callout") {
    if (!classified.body) return null;
    const label = CALLOUT_LABELS[classified.calloutKind] ?? "Note";
    return (
      <View key={node.key} style={calloutStyles.wrap}>
        <Text style={calloutStyles.label}>{label}</Text>
        <Text style={calloutStyles.body}>{classified.body}</Text>
      </View>
    );
  }
  if (!classified.code) return null;
  return (
    <View key={node.key} style={fenceStyles.codeWrap}>
      {classified.lang ? <Text style={fenceStyles.lang}>{classified.lang}</Text> : null}
      <Text style={fenceStyles.code} selectable>
        {classified.code}
      </Text>
    </View>
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

function makeCalloutStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      backgroundColor: t.contentSurface,
      borderLeftWidth: 3,
      borderLeftColor: t.primary,
      borderRadius: 8,
      paddingHorizontal: 12,
      paddingVertical: 10,
      marginVertical: 8,
    },
    label: {
      fontSize: 12,
      fontWeight: "700",
      color: t.primary,
      textTransform: "uppercase",
      letterSpacing: 0.5,
      marginBottom: 4,
    },
    body: { fontSize: 15, lineHeight: 21, color: t.text },
  });
}
