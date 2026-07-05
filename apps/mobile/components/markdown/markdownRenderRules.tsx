import { ReactNode } from "react";
import { Ionicons } from "@expo/vector-icons";
import { Image, Linking, Platform, Text, View } from "react-native";

import { LinkPreviewCard } from "@/components/LinkPreviewCard";
import { MathText } from "@/components/rich/MathText";
import {
  MarkdownTable,
  MarkdownTableCell,
  MarkdownTableHeaderCell,
  MarkdownTableRow,
} from "@/components/MarkdownTable";
import { QuoteBlock } from "@/components/rich/QuoteBlock";
import {
  type AstNode,
  type AstParent,
  astText,
  countTableColumns,
  detectStandaloneLink,
  inTableCell,
  inTableHeader,
  parentHasType,
  taskChecked,
} from "@/components/markdown/markdownAstHelpers";
import {
  makeMdImg,
  makeMdMath,
  makeMdStyles,
  makeMdTable,
  verifyCheckStyles,
  type MdImgStyles,
  type MdMathStyles,
  type MdTableStyles,
} from "@/components/markdown/markdownContentStyles";
import { renderFence } from "@/components/markdown/markdownFenceRender";
import { VerifyCheckmark } from "@/components/markdown/VerifyCheckmark";
import { isGenericSearchUrl } from "@/lib/placesList";
import { openPlaceLink } from "@/lib/openPlaceLink";
import { extractBlockquoteMeta, splitInlineMath } from "@/lib/markdownPreprocess";
import type { Theme } from "@/lib/theme";

type StyleMap = Record<string, object>;

function renderTextWithMath(
  node: { key: string; content: string },
  parent: unknown,
  styles: StyleMap,
  inheritedStyles: object,
  mdTable: MdTableStyles,
  mdMath: MdMathStyles,
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
  mdTable: MdTableStyles,
  mdMath: MdMathStyles,
  mdImg: MdImgStyles,
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

export function makeRenderRules(t: Theme, streaming = false) {
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
