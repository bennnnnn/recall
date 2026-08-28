/**
 * Minimal markdown when the rich renderer fails — still formats headers,
 * tables, bold, and code (no Prism / rich cards). Callout fences render as
 * styled prose instead of raw "callout-tip" code. Geometry/graph fences keep
 * their SVG renderers so densified point dumps never become a wall of JSON.
 * Sources, places, answers, and heavy visuals degrade to a short summary.
 */
import { useMemo } from "react";
import Markdown, { renderRules as defaultRules } from "react-native-markdown-display";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { inlineCodeTextStyle } from "@/components/markdown/markdownContentStyles";
import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";
import { GeometryBlock } from "@/components/rich/GeometryBlock";
import { CODE_FONT } from "@/lib/fonts";
import { markdownItInstance } from "@/lib/markdownIt";
import { preprocessMarkdown } from "@/lib/markdown/markdownPreprocess";
import { classifyFallbackFence } from "@/lib/fallbackFence";
import { fenceIdForLang } from "@/lib/fenceRegistry";
import { Theme, useTheme } from "@/lib/theme";

// react-native-markdown-display's AST exposes the fence's language tag as
// `sourceInfo`, not `info` — see markdownFenceRender.tsx's FenceNode.
type FenceNode = { key: string; content: string; sourceInfo?: string };

type Props = { content: string };

const CALLOUT_I18N_KEYS: Record<string, string> = {
  tip: "rich.callout_tip",
  note: "rich.callout_note",
  warning: "rich.callout_warning",
  info: "rich.callout_info",
  important: "rich.callout_important",
};

export function FallbackMarkdown({ content }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const mdStyles = useMemo(() => makeMdStyles(theme), [theme]);
  const fenceStyles = useMemo(() => makeFenceStyles(theme), [theme]);
  const calloutStyles = useMemo(() => makeCalloutStyles(theme), [theme]);
  const rules = useMemo(
    () => ({
      ...defaultRules,
      fence: (node: FenceNode) =>
        renderFallbackFence(node, fenceStyles, calloutStyles, t),
      code_block: (node: FenceNode) =>
        renderFallbackFence(node, fenceStyles, calloutStyles, t),
    }),
    [fenceStyles, calloutStyles, t],
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

function visualFallbackLabel(lang: string, t: (key: string) => string): string {
  const id = fenceIdForLang(lang);
  if (id === "chart") return t("rich.chart");
  if (id === "mermaid") return t("rich.mermaid_diagram");
  if (id === "chemistry" || id === "molecule" || id === "molecule3d") return t("rich.chemistry_structure");
  return t("rich.diagram");
}

function renderFallbackFence(
  node: FenceNode,
  fenceStyles: ReturnType<typeof makeFenceStyles>,
  calloutStyles: ReturnType<typeof makeCalloutStyles>,
  t: (key: string) => string,
) {
  const classified = classifyFallbackFence(node.sourceInfo, node.content);
  if (classified.kind === "callout") {
    if (!classified.body) return null;
    const i18nKey = CALLOUT_I18N_KEYS[classified.calloutKind] ?? "rich.callout_note";
    const label = t(i18nKey);
    return (
      <View key={node.key} style={calloutStyles.wrap}>
        <Text style={calloutStyles.label}>{label}</Text>
        <Text style={calloutStyles.body}>{classified.body}</Text>
      </View>
    );
  }
  if (classified.kind === "geometry") {
    return <GeometryBlock key={node.key} content={classified.body} />;
  }
  if (classified.kind === "graph") {
    return <FunctionGraphBlock key={node.key} content={classified.body} />;
  }
  if (classified.kind === "answer") {
    if (!classified.body) return null;
    return (
      <View key={node.key} style={calloutStyles.wrap}>
        <Text style={calloutStyles.body} selectable>
          {classified.body}
        </Text>
      </View>
    );
  }
  if (classified.kind === "sources" || classified.kind === "places") {
    if (classified.items.length === 0) return null;
    return (
      <View key={node.key} style={calloutStyles.wrap}>
        {classified.kind === "sources" ? (
          <Text style={calloutStyles.label}>{t("rich.source")}</Text>
        ) : null}
        {classified.items.map((item, index) => (
          <Text key={`${item.title}-${index}`} style={calloutStyles.body} selectable>
            {item.url ? `${item.title} (${item.url})` : item.title}
          </Text>
        ))}
      </View>
    );
  }
  if (classified.kind === "visual") {
    const label = visualFallbackLabel(classified.labelLang, t);
    return (
      <View key={node.key} style={calloutStyles.wrap}>
        <Text style={calloutStyles.label}>{label}</Text>
        {classified.snippet ? (
          <Text style={calloutStyles.body} selectable>
            {classified.snippet}
          </Text>
        ) : null}
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
    code_inline: inlineCodeTextStyle(t),
    heading1: { fontSize: 20, fontWeight: "700", marginVertical: 8 },
    heading2: { fontSize: 18, fontWeight: "700", marginVertical: 6 },
    heading3: { fontSize: 16, fontWeight: "600", marginVertical: 4 },
    heading4: { fontSize: 15, fontWeight: "600", marginVertical: 4, color: t.text },
    heading5: { fontSize: 14, fontWeight: "600", marginVertical: 2, color: t.text },
    heading6: { fontSize: 13, fontWeight: "600", marginVertical: 2, color: t.text },
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
