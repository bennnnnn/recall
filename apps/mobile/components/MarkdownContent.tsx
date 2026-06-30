/** Markdown renderer — v2 (no nested Markdown / plainFence), theme-aware. */
import { ReactNode, useDeferredValue, useMemo } from "react";
import Markdown from "react-native-markdown-display";
import { Ionicons } from "@expo/vector-icons";
import { Image, Linking, Platform, StyleSheet, Text, View } from "react-native";

import { isGenericSearchUrl } from "@/lib/placesList";
import { openPlaceLink } from "@/lib/openPlaceLink";

import { LinkPreviewCard } from "@/components/LinkPreviewCard";
import { CodeBlock } from "@/components/CodeBlock";
import { WebPreviewCodeBlock } from "@/components/WebPreviewCodeBlock";
import { CopyBlock } from "@/components/CopyBlock";
import { CircularClockBlock } from "@/components/rich/CircularClockBlock";
import { MathBlock } from "@/components/rich/MathView";
import { MathText } from "@/components/rich/MathText";
import { GeometryBlock } from "@/components/rich/GeometryBlock";
import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";
import {
  fenceContentAsGeometry,
  fenceContentAsGraph,
  looksLikeLatexFence,
} from "@/lib/mathFenceRetag";
import {
  MarkdownTable,
  MarkdownTableCell,
  MarkdownTableHeaderCell,
  MarkdownTableRow,
} from "@/components/MarkdownTable";
import { QuoteBlock } from "@/components/rich/QuoteBlock";
import {
  renderCopyStyleBlock,
  renderRichFence,
} from "@/components/rich/RichFence";
import {
  copyBlockLabel,
  isExplicitCodeLang,
  shouldRenderAsCodeBlock,
  shouldRenderAsCopyBlock,
} from "@/lib/copyBlock";
import { parseFenceLang, shouldUseHtmlPreview } from "@/lib/codeHighlight";
import {
  assistantReplyIsTimeAnswer,
  extractClockTimezone,
  isClockFenceBody,
  isDigitalTimeOnly,
  isIanaTimezoneOnly,
} from "@/lib/timeQuestion";
import { markdownItInstance } from "@/lib/markdownIt";
import {
  extractBlockquoteMeta,
  looksLikeMarkdownListProse,
  preprocessMarkdown,
  splitInlineMath,
} from "@/lib/markdownPreprocess";
import { CODE_FONT } from "@/lib/fonts";
import { isStandaloneUrl } from "@/lib/richBlocks";
import { Theme, useTheme } from "@/lib/theme";

type AstNode = {
  key: string;
  type?: string;
  content?: string;
  attributes?: Record<string, string>;
  children?: AstNode[];
  sourceType?: string;
};

type AstParent = {
  type: string;
  attributes?: { start?: number; class?: string };
};

type StyleMap = Record<string, object>;
type TableStyles = ReturnType<typeof makeMdTable>;
type MathStyles = ReturnType<typeof makeMdMath>;
type ImgStyles = ReturnType<typeof makeMdImg>;

function parentHasType(parent: unknown, type: string): boolean {
  return Array.isArray(parent) && parent.some((node) => node?.type === type);
}

function inTableCell(parent: unknown): boolean {
  return parentHasType(parent, "td") || parentHasType(parent, "th");
}

function inTableHeader(parent: unknown): boolean {
  return parentHasType(parent, "th");
}

function astText(node: AstNode): string {
  if (node.content) return node.content;
  return (node.children ?? []).map(astText).join("");
}

function collectHtmlInline(nodes: AstNode[] | undefined): string[] {
  const out: string[] = [];
  for (const node of nodes ?? []) {
    if (node.sourceType === "html_inline" || node.type === "html_inline") {
      if (node.content) out.push(node.content);
    }
    out.push(...collectHtmlInline(node.children));
  }
  return out;
}

function isTaskCheckboxChecked(html: string): boolean {
  return /\bchecked(?:\s|=|>|\/)/i.test(html);
}

function taskChecked(node: AstNode): boolean | null {
  const cls = node.attributes?.class ?? "";
  if (!cls.includes("task-list-item")) return null;
  const checkbox = collectHtmlInline(node.children).find((html) =>
    html.includes("task-list-item-checkbox"),
  );
  if (!checkbox) return false;
  return isTaskCheckboxChecked(checkbox);
}

/** ChatGPT-style green verification tick for checked `- [x]` list items. */
const VERIFY_CHECK_COLOR = "#10A37F";

function VerifyCheckmark() {
  return (
    <View style={verifyCheckStyles.badge}>
      <Ionicons name="checkmark" size={13} color="#FFFFFF" />
    </View>
  );
}

const verifyCheckStyles = StyleSheet.create({
  badge: {
    width: 20,
    height: 20,
    borderRadius: 4,
    backgroundColor: VERIFY_CHECK_COLOR,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 8,
    marginTop: 2,
    flexShrink: 0,
  },
  verifyRow: {
    flex: 1,
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  verifyContent: {
    flex: 1,
    flexShrink: 1,
  },
});

function countTableColumns(node: AstNode): number {
  let max = 1;
  const walk = (n: AstNode) => {
    if (n.type === "tr") {
      const cells = (n.children ?? []).filter(
        (c) => c.type === "th" || c.type === "td",
      );
      if (cells.length > max) max = cells.length;
    }
    (n.children ?? []).forEach(walk);
  };
  walk(node);
  return max;
}

function detectStandaloneLink(node: AstNode): string | null {
  const kids = node.children ?? [];
  if (kids.length === 1 && kids[0].type === "link") {
    const href = kids[0].attributes?.href;
    return href && isStandaloneUrl(href) ? href : null;
  }
  if (kids.length === 1 && kids[0].type === "text") {
    return isStandaloneUrl(kids[0].content ?? "");
  }
  return null;
}

type FenceNode = { key: string; content: string; info?: string };

function renderTextWithMath(
  node: { key: string; content: string },
  parent: unknown,
  styles: StyleMap,
  inheritedStyles: object,
  mdTable: TableStyles,
  mdMath: MathStyles,
) {
  const parts = splitInlineMath(node.content);
  const base = [
    inheritedStyles,
    styles.text,
    inTableCell(parent) && mdTable.cellText,
    inTableHeader(parent) && mdTable.headerText,
  ];

  if (parts.length === 1 && parts[0].type === "text") {
    return (
      <Text key={node.key} style={base} selectable>
        {node.content}
      </Text>
    );
  }

  return (
    <Text key={node.key} style={base} selectable>
      {parts.map((part, i) =>
        part.type === "math" ? (
          <MathText key={`${node.key}-m-${i}`} latex={part.value} />
        ) : (
          part.value
        ),
      )}
    </Text>
  );
}

function makeSharedRules(
  t: Theme,
  mdTable: TableStyles,
  mdMath: MathStyles,
  mdImg: ImgStyles,
  streaming = false,
) {
  return {
    image: (node: { key: string; attributes: { src?: string; alt?: string } }) => {
      const src = node.attributes?.src;
      if (!src) return null;
      return (
        <Image
          key={node.key}
          source={{ uri: src }}
          style={mdImg.image}
          resizeMode="contain"
        />
      );
    },
    text: (
      node: { key: string; content: string },
      _children: unknown,
      parent: unknown,
      styles: StyleMap,
      inheritedStyles: object = {},
    ) => renderTextWithMath(node, parent, styles, inheritedStyles, mdTable, mdMath),
    textgroup: (
      node: { key: string },
      children: ReactNode,
      parent: unknown,
      styles: StyleMap,
    ) => (
      <Text
        key={node.key}
        style={[
          styles.textgroup,
          inTableCell(parent) && mdTable.cellText,
          inTableHeader(parent) && mdTable.headerText,
        ]}
        selectable
      >
        {children}
      </Text>
    ),
    link: (
      node: AstNode,
      children: ReactNode,
      _parent: unknown,
      styles: StyleMap,
    ) => {
      const href = node.attributes?.href ?? "";
      const label = astText(node);
      return (
        <Text
          key={node.key}
          style={styles.link}
          onPress={() => {
            if (isGenericSearchUrl(href)) {
              void openPlaceLink(href, label);
            } else {
              Linking.openURL(href).catch(() => {});
            }
          }}
          suppressHighlighting
        >
          {children}
        </Text>
      );
    },
    list_item: (
      node: AstNode & { index: number; markup?: string },
      children: ReactNode,
      parent: AstParent[],
      styles: StyleMap,
    ) => {
      const task = taskChecked(node);
      if (parentHasType(parent, "bullet_list")) {
        if (task !== null) {
          if (task) {
            return (
              <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
                <Text style={styles.bullet_list_icon as object} accessible={false}>
                  {Platform.select({
                    android: "\u2022",
                    ios: "\u00B7",
                    default: "\u2022",
                  })}
                </Text>
                <View style={verifyCheckStyles.verifyRow}>
                  <View style={verifyCheckStyles.verifyContent}>{children}</View>
                  <VerifyCheckmark />
                </View>
              </View>
            );
          }
          return (
            <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
              <Ionicons
                name="square-outline"
                size={18}
                color={t.textTertiary}
                style={{ marginTop: 2 }}
              />
              <View style={styles._VIEW_SAFE_bullet_list_content as object}>
                {children}
              </View>
            </View>
          );
        }
        return (
          <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
            <Text style={styles.bullet_list_icon as object} accessible={false}>
              {Platform.select({
                android: "\u2022",
                ios: "\u00B7",
                default: "\u2022",
              })}
            </Text>
            <View style={[styles._VIEW_SAFE_bullet_list_content as object, mdMath.listContent]}>
              {children}
            </View>
          </View>
        );
      }
      if (parentHasType(parent, "ordered_list")) {
        const orderedList = parent.find((el) => el.type === "ordered_list");
        const start = orderedList?.attributes?.start;
        const listItemNumber = start != null ? start + node.index : node.index + 1;
        return (
          <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
            <Text style={styles.ordered_list_icon as object}>
              {listItemNumber}
              {node.markup}
            </Text>
            <View style={[styles._VIEW_SAFE_ordered_list_content as object, mdMath.listContent]}>
              {children}
            </View>
          </View>
        );
      }
      return (
        <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
          {children}
        </View>
      );
    },
    blockquote: (node: AstNode) => {
      const meta = extractBlockquoteMeta(astText(node));
      return <QuoteBlock key={node.key} quote={meta.quote} author={meta.author} />;
    },
    paragraph: (
      node: AstNode,
      children: ReactNode,
      parent: unknown,
      styles: StyleMap,
    ) => {
      const url = detectStandaloneLink(node);
      if (url && !streaming) {
        return <LinkPreviewCard key={node.key} url={url} />;
      }
      if (inTableCell(parent)) {
        return (
          <Text
            key={node.key}
            style={[mdTable.cellText, inTableHeader(parent) && mdTable.headerText]}
            selectable
          >
            {children}
          </Text>
        );
      }
      return (
        <View key={node.key} style={styles._VIEW_SAFE_paragraph as object}>
          {children}
        </View>
      );
    },
    hardbreak: (node: { key: string }, _c: unknown, _p: unknown, styles: StyleMap) => (
      <Text key={node.key} style={styles.hardbreak} selectable>
        {"\n"}
      </Text>
    ),
    softbreak: (node: { key: string }, _c: unknown, _p: unknown, styles: StyleMap) => (
      <Text key={node.key} style={styles.softbreak} selectable>
        {"\n"}
      </Text>
    ),
    inline: (node: { key: string }, children: ReactNode, _p: unknown, styles: StyleMap) => (
      <Text key={node.key} style={styles.inline} selectable>
        {children}
      </Text>
    ),
    span: (node: { key: string }, children: ReactNode, _p: unknown, styles: StyleMap) => (
      <Text key={node.key} style={styles.span} selectable>
        {children}
      </Text>
    ),
    code_inline: (
      node: { key: string; content: string },
      _children: unknown,
      parent: unknown,
      styles: StyleMap,
    ) => (
      <Text
        key={node.key}
        style={[styles.code_inline, inTableCell(parent) && mdTable.cellCode]}
        selectable
      >
        {node.content}
      </Text>
    ),
    strong: (
      node: AstNode,
      children: ReactNode,
      parent: unknown,
      styles: StyleMap,
    ) => {
      const raw = astText(node);
      const parts = splitInlineMath(raw);
      const boldStyle = [styles.strong, inTableCell(parent) && mdTable.headerText];
      if (parts.some((part) => part.type === "math")) {
        return (
          <Text key={node.key} style={boldStyle} selectable>
            {parts.map((part, i) =>
              part.type === "math" ? (
                <MathText key={`${node.key}-m-${i}`} latex={part.value} />
              ) : (
                part.value
              ),
            )}
          </Text>
        );
      }
      return (
        <Text key={node.key} style={boldStyle} selectable>
          {children}
        </Text>
      );
    },
    em: (node: { key: string }, children: ReactNode, _p: unknown, styles: StyleMap) => (
      <Text key={node.key} style={styles.em} selectable>
        {children}
      </Text>
    ),
    table: (node: AstNode, children: ReactNode) => (
      <MarkdownTable key={node.key} nodeKey={node.key} columns={countTableColumns(node)}>
        {children}
      </MarkdownTable>
    ),
    thead: (node: { key: string }, children: ReactNode) => (
      <View key={node.key}>{children}</View>
    ),
    tbody: (node: { key: string }, children: ReactNode) => (
      <View key={node.key}>{children}</View>
    ),
    tr: (node: { key: string }, children: ReactNode) => (
      <MarkdownTableRow key={node.key} nodeKey={node.key}>
        {children}
      </MarkdownTableRow>
    ),
    th: (node: { key: string }, children: ReactNode) => (
      <MarkdownTableHeaderCell key={node.key} nodeKey={node.key}>
        {children}
      </MarkdownTableHeaderCell>
    ),
    td: (node: { key: string }, children: ReactNode) => (
      <MarkdownTableCell key={node.key} nodeKey={node.key}>
        {children}
      </MarkdownTableCell>
    ),
  };
}

// Fence rendering delegates to components that theme themselves (CodeBlock, rich
// fences), so it needs no theme parameter.
function renderFence(node: FenceNode) {
  const lang = parseFenceLang(node.info?.trim() || "");
  const content = node.content.replace(/\n$/, "").trim();
  if (!content) return null;

  try {
    return renderFenceInner(node.key, lang, content);
  } catch (error) {
    if (__DEV__) {
      console.warn("[MarkdownContent] fence render failed", error);
    }
    return <CodeBlock key={node.key} code={content} lang={lang} />;
  }
}

function renderFenceInner(key: string, lang: string, content: string) {
  if (shouldUseHtmlPreview(lang, content)) {
    return <WebPreviewCodeBlock key={key} code={content} lang={lang || "html"} />;
  }
  const l = lang.trim().toLowerCase();
  if (fenceContentAsGeometry(content)) {
    return <GeometryBlock key={key} content={content} />;
  }
  if (fenceContentAsGraph(content)) {
    return <FunctionGraphBlock key={key} content={content} />;
  }
  if (
    l === "math" &&
    (looksLikeMarkdownListProse(content) ||
      /^\$\)?/.test(content.trim()) ||
      /\*\*[^*]+\*\*/.test(content))
  ) {
    return null;
  }
  if (looksLikeLatexFence(content) && l !== "python" && l !== "javascript") {
    return <MathBlock key={key} latex={content} />;
  }
  if (
    l === "clock" ||
    l === "time" ||
    isDigitalTimeOnly(content) ||
    isIanaTimezoneOnly(content) ||
    (l === "" && isClockFenceBody(content))
  ) {
    return <CircularClockBlock key={key} content={content} />;
  }
  const rich = renderRichFence(lang, content, key);
  if (rich) return rich;
  const copyStyle = renderCopyStyleBlock(lang, content, key);
  if (copyStyle) return copyStyle;
  if (isExplicitCodeLang(lang) || shouldRenderAsCodeBlock(lang, content)) {
    return <CodeBlock key={key} code={content} lang={lang} />;
  }
  if (shouldRenderAsCopyBlock(lang, content)) {
    const styled = renderCopyStyleBlock("copy", content, key);
    if (styled) return styled;
    return <CopyBlock key={key} text={content} label={copyBlockLabel(lang)} />;
  }
  return <CodeBlock key={key} code={content} lang={lang} />;
}

function makeRenderRules(t: Theme, streaming = false) {
  const mdMath = makeMdMath(t);
  const mdTable = makeMdTable(t);
  const mdImg = makeMdImg(t);
  const mdStyles = makeMdStyles(t);
  const rules = {
    ...makeSharedRules(t, mdTable, mdMath, mdImg, streaming),
    fence: renderFence,
    code_block: renderFence,
  };
  return { rules, mdStyles };
}

type Props = { content: string; streaming?: boolean };

export function MarkdownContent({ content, streaming = false }: Props) {
  const t = useTheme();
  const { rules, mdStyles } = useMemo(() => makeRenderRules(t, streaming), [t, streaming]);
  const deferredContent = useDeferredValue(content);
  const renderContent = streaming ? deferredContent : content;
  const prepared = useMemo(() => {
    try {
      return preprocessMarkdown(renderContent);
    } catch {
      return renderContent;
    }
  }, [renderContent]);
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

function makeMdMath(_t: Theme) {
  return StyleSheet.create({
    listContent: {
      flex: 1,
      flexShrink: 1,
    },
  });
}

function makeMdTable(t: Theme) {
  return StyleSheet.create({
    cellText: { fontSize: 15, lineHeight: 22, color: t.text, flexShrink: 1 },
    headerText: { fontWeight: "600", color: t.text },
    cellCode: {
      backgroundColor: t.contentSurface,
      color: t.text,
      fontFamily: CODE_FONT,
      fontSize: 13,
      lineHeight: 18,
      paddingHorizontal: 3,
      paddingVertical: 0,
      borderRadius: 3,
    },
  });
}

function makeMdImg(t: Theme) {
  return StyleSheet.create({
    image: {
      width: "100%",
      height: 200,
      borderRadius: 8,
      marginVertical: 6,
      backgroundColor: t.contentSurface,
    },
  });
}

function makeMdStyles(t: Theme) {
  return StyleSheet.create({
    body: { color: t.assistantText, fontSize: 16, lineHeight: 25 },
    code_inline: {
      backgroundColor: t.contentSurface,
      color: t.text,
      borderRadius: 4,
      paddingHorizontal: 4,
      fontFamily: CODE_FONT,
      fontSize: 14,
    },
    // Custom fence renderer handles code blocks / HTML preview inline.
    fence: { marginVertical: 0, padding: 0 },
    paragraph: { marginVertical: 0 },
    bullet_list: { marginVertical: 4 },
    ordered_list: { marginVertical: 4 },
    heading1: { fontSize: 20, fontWeight: "700", marginBottom: 8, color: t.text },
    heading2: { fontSize: 18, fontWeight: "700", marginBottom: 6, color: t.text },
    heading3: { fontSize: 16, fontWeight: "600", marginBottom: 4, color: t.text },
    strong: { fontWeight: "700", color: t.text },
    em: { fontStyle: "italic" },
    blockquote: { marginVertical: 0, padding: 0, borderWidth: 0 },
    hr: { backgroundColor: t.border, height: 1, marginVertical: 12 },
    link: { color: t.primary },
  });
}
