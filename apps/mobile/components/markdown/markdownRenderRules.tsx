import { Children, Fragment, ReactNode } from "react";
import { Icon } from "@/components/Icon";
import { Image, Text, View, type StyleProp, type TextStyle, type ViewStyle } from "react-native";

import { LinkPreviewCard } from "@/components/LinkPreviewCard";
import { MathText } from "@/components/rich/MathText";
import { MathBlock } from "@/components/rich/MathView";
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
  astTextWithBreaks,
  countTableColumns,
  detectStandaloneLink,
  inTableCell,
  inTableHeader,
  inHeading,
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
import { isAllowedImageUri } from "@/lib/imageUriPolicy";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { splitInlineMath } from "@/lib/markdown/markdownPreprocess";
import { parseQuoteAttribution } from "@/lib/richBlocks";
import { isHeavyInlineMath } from "@/lib/math/mathFenceRetag";
import {
  latexHasNestedMathView,
  mathRunLineHeight,
} from "@/lib/mathText";
import type { Theme } from "@/lib/theme";

type StyleMap = Record<string, object>;

const CHECK_TICK_RE = /([✓✔✅])/u;

function withGreenTicks(
  text: string,
  tickColor: string,
  keyPrefix: string,
): ReactNode {
  if (!text.includes("✓") && !text.includes("✔") && !text.includes("✅")) {
    return text;
  }
  return text.split(CHECK_TICK_RE).map((bit, i) =>
    bit === "✓" || bit === "✔" || bit === "✅" ? (
      <Text
        key={`${keyPrefix}-tick-${i}`}
        style={{ color: tickColor, fontWeight: "700" }}
      >
        {bit}
      </Text>
    ) : (
      bit
    ),
  );
}

function replaceHtmlBreaks(text: string): string {
  return text.replace(/<br\s*\/?>/gi, "\n");
}

/**
 * Stacked frac/sqrt is a sized View. A Text ancestor on iOS gives that View a
 * 0×0 text attachment, so the numerator paints over the line above. Use a
 * wrapping row instead; keep Text when the run is only prose/scripts.
 */
function wrapInlineChildren(
  node: AstNode,
  children: ReactNode,
  textStyle: StyleProp<TextStyle>,
  wrapStyle: StyleProp<ViewStyle>,
): React.ReactElement {
  if (latexHasNestedMathView(astText(node))) {
    return (
      <View key={node.key} testID="md-math-inline-wrap" style={wrapStyle}>
        {children}
      </View>
    );
  }
  return (
    <Text key={node.key} style={[textStyle, { flexShrink: 1 }]} selectable>
      {children}
    </Text>
  );
}

function renderTextWithMath(
  node: { key: string; content: string },
  parent: unknown,
  styles: StyleMap,
  inheritedStyles: object,
  mdTable: MdTableStyles,
  _mdMath: MdMathStyles,
  tickColor: string,
) {
  // Strip standalone ":" lines — the model puts a colon on its own line as a
  // "leads to the next line" marker. It strands as a lone "two dots" between
  // a label and the formula on the next line. Drop it for all content, not
  // just nested-math paragraphs.
  const content = replaceHtmlBreaks(node.content)
    .split("\n")
    .filter((line) => line.trim() !== ":")
    .join("\n");
  const parts = splitInlineMath(content);
  const runHeight = parts.reduce<number | undefined>((acc, p) => {
    if (p.type !== "math") return acc;
    const h = mathRunLineHeight(p.value);
    if (h == null) return acc;
    return acc == null ? h : Math.max(acc, h);
  }, undefined);
  const base = [
    styles.body,
    inheritedStyles,
    styles.text,
    inTableCell(parent) && mdTable.cellText,
    inTableHeader(parent) && mdTable.headerText,
    runHeight != null && { lineHeight: runHeight },
  ];

  if (parts.length === 1 && parts[0].type === "text") {
    return (
      <Text key={node.key} style={base} selectable>
        {withGreenTicks(content, tickColor, node.key)}
      </Text>
    );
  }

  const hasHeavy = parts.some(
    (p) => p.type === "math" && isHeavyInlineMath(p.value),
  );
  if (hasHeavy) {
    return (
      <View key={node.key}>
        {parts.map((part, i) => {
          const key = `${node.key}-m-${i}`;
          if (part.type === "math" && isHeavyInlineMath(part.value)) {
            return <MathBlock key={key} latex={part.value} />;
          }
          if (part.type === "math") {
            return (
              <Text key={key} style={base} selectable>
                <MathText latex={part.value} />
              </Text>
            );
          }
          return (
            <Text key={key} style={base} selectable>
              {withGreenTicks(part.value, tickColor, key)}
            </Text>
          );
        })}
      </View>
    );
  }

  // Nested math Views (frac / sqrt) must be direct children of the paragraph
  // Text. Wrapping this run in another Text is what made neighboring
  // sentences paint on top of each other.
  if (parts.some((p) => p.type === "math" && latexHasNestedMathView(p.value))) {
    // A trailing text part that is only a colon (e.g. "Use the product rule
    // $\sqrt{ab}=\sqrt{a}\sqrt{b}$:") strands onto its own line here: the math
    // is a nested View, so the ":" after it can't share its line box and
    // renders as a random lone "two dots" between the rule and the next
    // line. The colon is a "leads to the next line" marker that's redundant
    // once the next line follows — drop it so it doesn't strand.
    const trimmed = parts.filter((p, i) => {
      if (p.type !== "text") return true;
      // Only drop a trailing lone colon (the last part, possibly after a math View).
      if (i !== parts.length - 1) return true;
      return p.value.trim() !== ":";
    });
    return (
      <Fragment key={node.key}>
        {trimmed.map((part, i) =>
          part.type === "math" ? (
            <MathText key={`${node.key}-m-${i}`} latex={part.value} />
          ) : (
            <Text key={`${node.key}-t-${i}`} style={base} selectable>
              {withGreenTicks(part.value, tickColor, `${node.key}-t-${i}`)}
            </Text>
          ),
        )}
      </Fragment>
    );
  }

  return (
    <Text key={node.key} style={base} selectable>
      {parts.map((part, i) =>
        part.type === "math" ? (
          <MathText key={`${node.key}-m-${i}`} latex={part.value} />
        ) : (
          withGreenTicks(part.value, tickColor, `${node.key}-t-${i}`)
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
  mdCodeInline: object,
  streaming = false,
) {
  return {
    image: (node: { key: string; attributes: { src?: string; alt?: string } }) => {
      const src = node.attributes?.src;
      // Block insecure-scheme / local-file image URIs (tracking pixels, file:
      // exfil, content:). Only https/data/blob render; everything else is
      // dropped silently so a malicious or misformed URL can't auto-load.
      if (!isAllowedImageUri(src)) return null;
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
    ) =>
      renderTextWithMath(
        node,
        parent,
        styles,
        inheritedStyles,
        mdTable,
        mdMath,
        t.success,
      ),
    textgroup: (
      node: AstNode,
      children: ReactNode,
      parent: unknown,
      styles: StyleMap,
      inheritedStyles: object = {},
    ) => {
      // Tight lists (and GFM table cells / mixed headings) omit a wrapping
      // paragraph. Without one enclosing Text, Fragment-flattened children
      // (plain + **bold** / `code`) land as siblings of a column View and
      // each takes its own line — or, in a row heading, overflow off-screen.
      if (
        parentHasType(parent, "list_item") ||
        inTableCell(parent) ||
        inHeading(parent)
      ) {
        const runHeight = mathRunLineHeight(astText(node));
        return wrapInlineChildren(
          node,
          children,
          [
            styles.body,
            inheritedStyles,
            styles.text,
            inTableCell(parent) && mdTable.cellText,
            inTableHeader(parent) && mdTable.headerText,
            runHeight != null && { lineHeight: runHeight },
            { flexShrink: 1 },
          ],
          mdMath.inlineWrap,
        );
      }
      return <Fragment key={node.key}>{children}</Fragment>;
    },
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
            // Reject javascript:/data:/file:/etc. before handing to the OS link
            // handler — model-emitted markdown can include arbitrary URLs and
            // Linking.openURL executes the payload on some platforms.
            if (isGenericSearchUrl(href)) {
              void openPlaceLink(href, label);
            } else {
              void openAllowedUrl(href);
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
                <View style={mdMath.listBullet} accessible={false} />
                <View style={verifyCheckStyles.verifyRow}>
                  <View style={verifyCheckStyles.verifyContent}>{children}</View>
                  <VerifyCheckmark />
                </View>
              </View>
            );
          }
          return (
            <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
              <Icon
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
            <View style={mdMath.listBullet} accessible={false} />
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
    blockquote: (node: AstNode, children: ReactNode) => {
      const last = node.children?.[node.children.length - 1];
      const lastMeta = last ? parseQuoteAttribution(astTextWithBreaks(last)) : undefined;
      const lastIsOnlyAttr = Boolean(lastMeta?.author && !lastMeta.quote);
      const body = lastIsOnlyAttr ? Children.toArray(children).slice(0, -1) : children;
      return (
        <QuoteBlock key={node.key} author={lastIsOnlyAttr ? lastMeta?.author : undefined}>
          {body}
        </QuoteBlock>
      );
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
        // Table cell paragraphs need the same mathRunLineHeight treatment as
        // body paragraphs — without it, a stacked \frac / \sqrt View inside
        // the cell's Text gets clipped to the cell's default lineHeight.
        const cellRaw = astText(node);
        const cellRunHeight = mathRunLineHeight(cellRaw);
        return wrapInlineChildren(
          node,
          children,
          [
            mdTable.cellText,
            inTableHeader(parent) && mdTable.headerText,
            cellRunHeight != null && { lineHeight: cellRunHeight },
          ],
          mdMath.inlineWrap,
        );
      }
      // Prose-only paragraphs stay a single Text so "An **open circle**"
      // wraps as one run. Stacked frac/sqrt must leave that Text — iOS
      // sizes a View-in-Text as 0×0 and paints the numerator over the
      // previous line. Do not use `styles.paragraph` — mergeStyle copies
      // the library's flexDirection/flexWrap/width onto that key.
      const raw = astText(node);
      const runHeight = mathRunLineHeight(raw);
      return wrapInlineChildren(
        node,
        children,
        [
          styles.body,
          styles.text,
          styles.paragraphRun,
          runHeight != null && { lineHeight: runHeight },
        ],
        [mdMath.inlineWrap, styles.paragraphRun],
      );
    },
    hardbreak: (node: { key: string }, _c: unknown, _p: unknown, styles: StyleMap) => (
      <Text key={node.key} style={styles.hardbreak} selectable>
        {"\n"}
      </Text>
    ),
    softbreak: (node: { key: string }) => (
      // CommonMark softbreak is a newline in source. HTML treats it as a
      // space; RN Text treats "\n" as a hard line break — that's why list
      // items like "It's a\n**linear equation**\nin slope-intercept form"
      // stacked every phrase. Render a space so the paragraph wraps naturally.
      <Text key={node.key}> </Text>
    ),
    inline: (node: { key: string }, children: ReactNode) => (
      // Extra Text here is Text > Text > View for stacked frac (0×0 on iOS).
      // List items get their run wrapper from `textgroup`; body paragraphs
      // from `paragraph`.
      <Fragment key={node.key}>{children}</Fragment>
    ),
    span: (node: { key: string }, children: ReactNode, _p: unknown, styles: StyleMap) => (
      <Text key={node.key} style={styles.span} selectable>
        {children}
      </Text>
    ),
    html_inline: (node: { key: string; content?: string }) => {
      const html = (node.content ?? "").trim();
      if (/^<br\s*\/?>$/i.test(html)) {
        return (
          <Text key={node.key} selectable>
            {"\n"}
          </Text>
        );
      }
      return null;
    },
    code_inline: (
      node: { key: string; content: string },
      _children: unknown,
      parent: unknown,
    ) => (
      <Text
        key={node.key}
        style={[mdCodeInline, inTableCell(parent) && mdTable.cellCode]}
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
    ) => (
      <Text
        key={node.key}
        style={[
          styles.body,
          styles.strong,
          inTableHeader(parent) && mdTable.headerText,
        ]}
        selectable
      >
        {children}
      </Text>
    ),
    em: (node: { key: string }, children: ReactNode, _p: unknown, styles: StyleMap) => (
      <Text key={node.key} style={[styles.body, styles.em]} selectable>
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
    ...makeSharedRules(t, mdTable, mdMath, mdImg, mdStyles.code_inline, streaming),
    fence: renderFence,
    code_block: renderFence,
  };
  return { rules, mdStyles };
}
