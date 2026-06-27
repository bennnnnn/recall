/** Markdown renderer — v2 (no nested Markdown / plainFence). */
import { ReactNode, useMemo } from "react";
import Markdown from "react-native-markdown-display";
import { Ionicons } from "@expo/vector-icons";
import { Image, Platform, StyleSheet, Text, View } from "react-native";

import { LinkPreviewCard } from "@/components/LinkPreviewCard";
import { CodeBlock } from "@/components/CodeBlock";
import { WebPreviewCodeBlock } from "@/components/WebPreviewCodeBlock";
import { CopyBlock } from "@/components/CopyBlock";
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
import { C } from "@/constants/Colors";
import {
  copyBlockLabel,
  isExplicitCodeLang,
  shouldRenderAsCodeBlock,
  shouldRenderAsCopyBlock,
} from "@/lib/copyBlock";
import { parseFenceLang, shouldUseHtmlPreview } from "@/lib/codeHighlight";
import { markdownItInstance } from "@/lib/markdownIt";
import {
  extractBlockquoteMeta,
  preprocessMarkdown,
  splitInlineMath,
} from "@/lib/markdownPreprocess";
import { CODE_FONT } from "@/lib/fonts";
import { isStandaloneUrl } from "@/lib/richBlocks";

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

function taskChecked(node: AstNode): boolean | null {
  const cls = node.attributes?.class ?? "";
  if (!cls.includes("task-list-item")) return null;
  const html = node.children?.find((c) => c.sourceType === "html_inline");
  return Boolean(html?.content?.includes("checked"));
}

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
  styles: Record<string, object>,
  inheritedStyles: object = {},
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
          <Text key={`${node.key}-m-${i}`} style={mdMath.inline}>
            {part.value}
          </Text>
        ) : (
          part.value
        ),
      )}
    </Text>
  );
}

const sharedRenderRules = {
  image: (node: {
    key: string;
    attributes: { src?: string; alt?: string };
  }) => {
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
    styles: Record<string, object>,
    inheritedStyles: object = {},
  ) => renderTextWithMath(node, parent, styles, inheritedStyles),
  textgroup: (
    node: { key: string },
    children: ReactNode,
    parent: unknown,
    styles: Record<string, object>,
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
  list_item: (
    node: AstNode & { index: number; markup?: string },
    children: ReactNode,
    parent: AstParent[],
    styles: Record<string, object>,
  ) => {
    const task = taskChecked(node);
    if (parentHasType(parent, "bullet_list")) {
      if (task !== null) {
        return (
          <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
            <Ionicons
              name={task ? "checkbox" : "square-outline"}
              size={18}
              color={task ? C.primary : C.textTertiary}
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
          <View style={styles._VIEW_SAFE_bullet_list_content as object}>
            {children}
          </View>
        </View>
      );
    }
    if (parentHasType(parent, "ordered_list")) {
      const orderedList = parent.find((el) => el.type === "ordered_list");
      const start = orderedList?.attributes?.start;
      const listItemNumber =
        start != null ? start + node.index : node.index + 1;
      return (
        <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
          <Text style={styles.ordered_list_icon as object}>
            {listItemNumber}
            {node.markup}
          </Text>
          <View style={styles._VIEW_SAFE_ordered_list_content as object}>
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
    return (
      <QuoteBlock key={node.key} quote={meta.quote} author={meta.author} />
    );
  },
  paragraph: (
    node: AstNode,
    children: ReactNode,
    parent: unknown,
    styles: Record<string, object>,
  ) => {
    const url = detectStandaloneLink(node);
    if (url) {
      return <LinkPreviewCard key={node.key} url={url} />;
    }
    if (inTableCell(parent)) {
      return (
        <Text
          key={node.key}
          style={[
            mdTable.cellText,
            inTableHeader(parent) && mdTable.headerText,
          ]}
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
  hardbreak: (
    node: { key: string },
    _c: unknown,
    _p: unknown,
    styles: Record<string, object>,
  ) => (
    <Text key={node.key} style={styles.hardbreak} selectable>
      {"\n"}
    </Text>
  ),
  softbreak: (
    node: { key: string },
    _c: unknown,
    _p: unknown,
    styles: Record<string, object>,
  ) => (
    <Text key={node.key} style={styles.softbreak} selectable>
      {"\n"}
    </Text>
  ),
  inline: (
    node: { key: string },
    children: ReactNode,
    _p: unknown,
    styles: Record<string, object>,
  ) => (
    <Text key={node.key} style={styles.inline} selectable>
      {children}
    </Text>
  ),
  span: (
    node: { key: string },
    children: ReactNode,
    _p: unknown,
    styles: Record<string, object>,
  ) => (
    <Text key={node.key} style={styles.span} selectable>
      {children}
    </Text>
  ),
  code_inline: (
    node: { key: string; content: string },
    _children: unknown,
    parent: unknown,
    styles: Record<string, object>,
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
    node: { key: string },
    children: ReactNode,
    parent: unknown,
    styles: Record<string, object>,
  ) => (
    <Text
      key={node.key}
      style={[styles.strong, inTableCell(parent) && mdTable.headerText]}
      selectable
    >
      {children}
    </Text>
  ),
  em: (
    node: { key: string },
    children: ReactNode,
    _p: unknown,
    styles: Record<string, object>,
  ) => (
    <Text key={node.key} style={styles.em} selectable>
      {children}
    </Text>
  ),
  table: (node: AstNode, children: ReactNode) => (
    <MarkdownTable
      key={node.key}
      nodeKey={node.key}
      columns={countTableColumns(node)}
    >
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
    return (
      <WebPreviewCodeBlock key={key} code={content} lang={lang || "html"} />
    );
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
    return (
      <CopyBlock key={key} text={content} label={copyBlockLabel(lang)} />
    );
  }
  return <CodeBlock key={key} code={content} lang={lang} />;
}

const renderRules = {
  ...sharedRenderRules,
  fence: renderFence,
  code_block: renderFence,
};

type Props = { content: string };

export function MarkdownContent({ content }: Props) {
  const prepared = useMemo(() => {
    try {
      return preprocessMarkdown(content);
    } catch {
      return content;
    }
  }, [content]);
  return (
    <Markdown
      style={mdStyles}
      rules={renderRules as never}
      markdownit={markdownItInstance}
    >
      {prepared}
    </Markdown>
  );
}

const mdMath = StyleSheet.create({
  inline: {
    fontFamily: CODE_FONT,
    fontSize: 14,
    color: C.primaryDark,
    backgroundColor: C.contentSurface,
  },
});

const mdTable = StyleSheet.create({
  cellText: {
    fontSize: 15,
    lineHeight: 22,
    color: C.text,
    flexShrink: 1,
  },
  headerText: { fontWeight: "600", color: C.text },
  cellCode: {
    backgroundColor: C.contentSurface,
    color: C.text,
    fontFamily: CODE_FONT,
    fontSize: 13,
    lineHeight: 18,
    paddingHorizontal: 3,
    paddingVertical: 0,
    borderRadius: 3,
  },
});

const mdImg = StyleSheet.create({
  image: {
    width: "100%",
    height: 200,
    borderRadius: 8,
    marginVertical: 6,
    backgroundColor: C.contentSurface,
  },
});

const mdStyles = StyleSheet.create({
  body: { color: C.assistantText, fontSize: 16, lineHeight: 24 },
  code_inline: {
    backgroundColor: C.contentSurface,
    color: C.text,
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
  heading1: { fontSize: 20, fontWeight: "700", marginBottom: 8 },
  heading2: { fontSize: 18, fontWeight: "700", marginBottom: 6 },
  heading3: { fontSize: 16, fontWeight: "600", marginBottom: 4 },
  strong: { fontWeight: "700" },
  em: { fontStyle: "italic" },
  blockquote: { marginVertical: 0, padding: 0, borderWidth: 0 },
  hr: { backgroundColor: C.border, height: 1, marginVertical: 12 },
  link: { color: C.primary },
});
