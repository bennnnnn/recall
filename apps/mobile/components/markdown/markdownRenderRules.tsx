import { Fragment, ReactNode } from "react";
import { Image } from "expo-image";
import { Icon } from "@/ui/icons/Icon";
import { PixelRatio, Text, View, type StyleProp, type TextStyle, type ViewStyle } from "react-native";

import { LinkPreviewCard } from "@/components/LinkPreviewCard";
import { splitStreamCaret, StreamingCursor } from "@/components/StreamingCursor";
import { MathText } from "@/components/rich/MathText";
import { MathBlock } from "@/components/rich/MathView";
import {
  MarkdownTable,
  MarkdownTableCell,
  MarkdownTableHeaderCell,
  MarkdownTableRow,
} from "@/components/MarkdownTable";
import { renderBlockquote } from "@/components/markdown/blockquoteRender";
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
  immediateAncestorType,
  listItemDisplayNumber,
  listLargestNumber,
  numberColumnWidth,
  listItemHasNestedList,
  parentHasType,
  shouldNumberListItem,
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
import { isAllowedImageUri } from "@/lib/images/imageUriPolicy";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Italic, Type, Weight } from "@/lib/type";
import { markdownHasNestedMathView, splitInlineMath } from "@/lib/markdown/preprocess";
import { isHeavyInlineMath } from "@/lib/math/fenceRetag";
import { splitWorkoutNote, workoutHeading } from "@/lib/markdown/workoutSection";
import {
  latexHasNestedMathView,
  mathRunLineHeight,
} from "@/lib/math/text";
import type { Theme } from "@/lib/theme";
import { IconSize } from "@/ui/icons/sizes";

type StyleMap = Record<string, object>;

const CHECK_TICK_RE = /([✓✔✅])/u;
const TRAILING_CHECK_TICK_RE = /[ \t]*([✓✔✅])[ \t]*$/u;

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
        style={{ color: tickColor, ...Weight.bold }}
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

const LESSON_STEP_RE = /^(\d+)\.\s+(\S[\s\S]*)$/;

function unwrapSingle(node: AstNode): AstNode {
  let current = node;
  while ((current.children?.length ?? 0) === 1) {
    const only = current.children?.[0];
    if (!only || only.type === "text" || only.type === "strong") break;
    current = only;
  }
  return current;
}

/** A generated lesson heading, then each equation of that move on its own line. */
function lessonStepParts(
  node: AstNode,
): { n: string; label: string; reason: string | null; formulas: string[] } | null {
  const kids = unwrapSingle(node).children ?? [];
  const strong = openingStrong(kids[0]);
  if (!strong) return null;
  const match = LESSON_STEP_RE.exec(astText(strong).trim());
  if (!match) return null;

  const tail = kids
    .slice(1)
    .map((kid) => astTextWithBreaks(kid))
    .join("");
  if (!tail.trim()) {
    return { n: match[1], label: match[2], reason: null, formulas: [] };
  }

  // The API emits a soft break and one `$...$` per line (the both-sides
  // equation, then the simplified equation). Anything else inline after the
  // bold heading stays ordinary Markdown.
  const parsed = lessonStepTail(tail);
  return parsed
    ? { n: match[1], label: match[2], reason: parsed.reason, formulas: parsed.formulas }
    : null;
}

function lessonStepTail(tail: string): { reason: string | null; formulas: string[] } | null {
  let rest = tail;
  let reason: string | null = null;
  // A reason sits on the heading line. A formula on that same line is ordinary
  // markdown (`**1. Result** $x^2$`); the working puts each equation on the next line.
  const reasonMatch = /^[ \t]*—\s*([^\n]*)/.exec(rest);
  if (reasonMatch) {
    reason = reasonMatch[1].trim() || null;
    rest = rest.slice(reasonMatch[0].length);
  }
  if (!/^\s*\n/.test(rest)) return null;
  const lines = rest
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return null;
  const formulas: string[] = [];
  for (const line of lines) {
    const formula = /^\$([^$\n]+)\$$/.exec(line);
    if (!formula) return null;
    formulas.push(formula[1].trim());
  }
  return { reason, formulas };
}

function lessonLabelNodes(
  label: string,
  keyPrefix: string,
  textStyle: StyleProp<TextStyle>,
  textColor: string,
): ReactNode {
  const operand = stepOperand(label);
  if (operand && !label.includes("$")) {
    return (
      <Text key={keyPrefix} style={textStyle} selectable>
        {operand.prefix}
        <Text style={Weight.bold}>{operand.operand}</Text>
        {operand.suffix}
      </Text>
    );
  }
  return splitInlineMath(label).map((part, i) =>
    part.type === "math" ? (
      <MathText
        scrollOverflow
        key={`${keyPrefix}-m-${i}`}
        latex={part.value}
        textColor={textColor}
      />
    ) : (
      <Text key={`${keyPrefix}-t-${i}`} style={textStyle} selectable>
        {boldOperandText(part.value, operand)}
      </Text>
    ),
  );
}

function boldOperandText(
  value: string,
  operand: { prefix: string; operand: string; suffix: string } | null,
): ReactNode {
  if (!operand || operand.operand.includes("$") || !value.includes(operand.operand)) return value;
  const at = value.indexOf(operand.operand);
  return (
    <>
      {value.slice(0, at)}
      <Text style={Weight.bold}>{operand.operand}</Text>
      {value.slice(at + operand.operand.length)}
    </>
  );
}

/** The amount a both-sides move acts on, so "Subtract 4" can bold the 4. */
function stepOperand(label: string): { prefix: string; operand: string; suffix: string } | null {
  const subtract = /^(Subtract |Add )(.+?)( from both sides[\s\S]*| to both sides[\s\S]*)$/.exec(
    label,
  );
  if (subtract) return { prefix: subtract[1], operand: subtract[2], suffix: subtract[3] };
  const scale = /^(Divide both sides by |Multiply both sides by )(.+)$/.exec(label);
  if (scale) return { prefix: scale[1], operand: scale[2], suffix: "" };
  return null;
}

const WORKOUT_LINE_KIDS = new Set(["text", "softbreak", "hardbreak"]);

/** Plain text and line breaks only: emphasis, links, or code keep the markdown renderer. */
function plainInline(node: AstNode): boolean {
  if (WORKOUT_LINE_KIDS.has(node.type ?? "")) return true;
  return node.type === "textgroup" && (node.children ?? []).every(plainInline);
}

/** The bold heading that opens a paragraph, if the paragraph starts with one. */
function openingStrong(node: AstNode | undefined): AstNode | null {
  if (!node) return null;
  if (node.type === "strong") return node;
  const kids = node.children ?? [];
  return node.type === "textgroup" && kids.length === 1 ? openingStrong(kids[0]) : null;
}

/**
 * A workout section: a bold heading that ends its line, then one state per
 * line. The lines are rows of their own because a stacked fraction turns a
 * paragraph into a wrapping row, where a line break is lost.
 */
function workoutSectionParts(node: AstNode): { heading: string; lines: string[] } | null {
  const kids = unwrapSingle(node).children ?? [];
  const strong = openingStrong(kids[0]);
  if (!strong) return null;
  const heading = workoutHeading(astText(strong));
  if (!heading) return null;
  const rest = kids.slice(1);
  if (!rest.length || !rest.every(plainInline)) return null;
  const tail = rest.map((kid) => astTextWithBreaks(kid)).join("");
  if (!/^[ \t]*\n/.test(tail)) return null;
  const lines = tail
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.length ? { heading, lines } : null;
}

/**
 * Stacked frac/sqrt and raised scripts are sized Views. A Text ancestor on
 * iOS gives that View a 0×0 text attachment, and it also drops translateY
 * on a nested Text, so an exponent sits on the baseline. Use a wrapping
 * row instead; keep Text when the run is only prose.
 */
function wrapInlineChildren(
  node: AstNode,
  children: ReactNode,
  textStyle: StyleProp<TextStyle>,
  wrapStyle: StyleProp<ViewStyle>,
): React.ReactElement {
  if (markdownHasNestedMathView(astText(node)) || isHeavyInlineMath(astText(node))) {
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
  const marked = splitStreamCaret(node.content);
  let content = replaceHtmlBreaks(marked.text)
    .split("\n")
    .filter((line) => line.trim() !== ":")
    .join("\n");
  // A stacked fraction/root is a native View rather than a text glyph. When
  // a verification tick follows it, iOS can wrap that tiny final Text onto a
  // detached line (or the far edge of the bubble). Put the status first for
  // tall math so it stays visibly attached while the equation may scroll.
  const trailingTick = TRAILING_CHECK_TICK_RE.exec(content);
  if (trailingTick) {
    const withoutTick = content.slice(0, trailingTick.index).trimEnd();
    if (markdownHasNestedMathView(withoutTick)) {
      content = `${trailingTick[1]} ${withoutTick}`;
    }
  }
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
    inTableCell(parent) && mdTable.cellInline,
    inTableHeader(parent) && mdTable.headerText,
    // Ancestor styles stack in order, so strong's Bold would hide em's Italic.
    parentHasType(parent, "em") && parentHasType(parent, "strong") && Italic.bold,
    runHeight != null && { lineHeight: runHeight },
  ];
  let caretLeft = marked.caret;
  const takeCaret = (inText = false): ReactNode => {
    if (!caretLeft) return null;
    caretLeft = false;
    return <StreamingCursor key={`${node.key}-caret`} inline={inText} />;
  };

  if (!content && marked.caret) {
    return (
      <Text key={node.key} style={base} selectable>
        {takeCaret(true)}
      </Text>
    );
  }

  if (parts.length === 1 && parts[0].type === "text") {
    return (
      <Text key={node.key} style={base} selectable>
        {withGreenTicks(content, tickColor, node.key)}
        {takeCaret(true)}
      </Text>
    );
  }

  const hasHeavy = parts.some(
    (p) => p.type === "math" && isHeavyInlineMath(p.value),
  );
  if (hasHeavy) {
    const runs: ReactNode[] = [];
    let inline: typeof parts = [];
    const flushInline = (final = false) => {
      if (!inline.length) return;
      const key = `${node.key}-inline-${runs.length}`;
      const inText = !inline.some(
        (part) => part.type === "math" && latexHasNestedMathView(part.value),
      );
      const caret = final ? takeCaret(inText) : null;
      const children = inline.map((part, i) => part.type === "math"
        ? <MathText scrollOverflow key={`${key}-${i}`} latex={part.value} />
        : <Text key={`${key}-${i}`} style={base} selectable>{withGreenTicks(part.value, tickColor, key)}</Text>);
      runs.push(inline.some((part) => part.type === "math" && latexHasNestedMathView(part.value))
        ? <View key={key} style={_mdMath.inlineWrap}>{children}{caret}</View>
        : <Text key={key} style={base} selectable>{children}{caret}</Text>);
      inline = [];
    };
    for (let i = 0; i < parts.length; i += 1) {
      const part = parts[i];
      if (part.type !== "math" || !isHeavyInlineMath(part.value)) {
        inline.push(part);
        continue;
      }
      flushInline();
      const next = parts[i + 1];
      const punctuationMatch = next?.type === "text"
        ? /^[ \t]*([,.;:!?]+)/.exec(next.value) : null;
      const punctuation = punctuationMatch?.[1] ?? "";
      runs.push(<MathBlock key={`${node.key}-m-${i}`} latex={
        part.value + (punctuation ? `\\text{${punctuation}}` : "")
      } />);
      if (punctuationMatch && next?.type === "text") {
        // Keep punctuation with the display formula even when the same text
        // token continues with prose (", then compare"), retaining that prose.
        const remainder = next.value.slice(punctuationMatch[0].length).trimStart();
        if (remainder) inline.push({ type: "text", value: remainder });
        i += 1;
      }
    }
    flushInline(true);
    if (caretLeft) runs.push(takeCaret());
    return (
      <View key={node.key} testID="md-heavy-math-run" style={{ width: "100%" }}>
        {runs}
      </View>
    );
  }

  // Keep each nested math View outside Text, while prose and simple math
  // share a Text run so native line wrapping can break between words.
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
    const runs: ReactNode[] = [];
    let inline: typeof parts = [];
    const flushInline = (final = false) => {
      if (!inline.length) return;
      const key = `${node.key}-inline-${runs.length}`;
      runs.push(
        <Text key={key} style={base} selectable>
          {inline.map((part, i) => part.type === "math"
            ? <MathText scrollOverflow key={`${key}-${i}`} latex={part.value} />
            : withGreenTicks(part.value, tickColor, `${key}-${i}`))}
          {final ? takeCaret(true) : null}
        </Text>,
      );
      inline = [];
    };
    for (let i = 0; i < trimmed.length; i += 1) {
      const part = trimmed[i];
      if (part.type !== "math" || !latexHasNestedMathView(part.value)) {
        inline.push(part);
        continue;
      }
      flushInline();
      const next = trimmed[i + 1];
      const punctuationMatch = next?.type === "text"
        ? /^[ \t]*([,.;:!?]+)/.exec(next.value) : null;
      const punctuation = punctuationMatch?.[1] ?? "";
      runs.push(<MathText scrollOverflow key={`${node.key}-m-${i}`} latex={
        part.value + (punctuation ? `\\text{${punctuation}}` : "")
      } />);
      if (punctuationMatch && next?.type === "text") {
        const remainder = next.value.slice(punctuationMatch[0].length);
        if (remainder) inline.push({ type: "text", value: remainder });
        i += 1;
      }
    }
    flushInline(true);
    if (caretLeft) runs.push(takeCaret());
    return <Fragment key={node.key}>{runs}</Fragment>;
  }

  return (
    <Text key={node.key} style={base} selectable>
      {parts.map((part, i) =>
        part.type === "math" ? (
          <MathText scrollOverflow key={`${node.key}-m-${i}`} latex={part.value} />
        ) : (
          withGreenTicks(part.value, tickColor, `${node.key}-t-${i}`)
        ),
      )}
      {takeCaret(true)}
    </Text>
  );
}

const HEADING_SIZES = {
  heading1: Type.h1.fontSize,
  heading2: Type.h2.fontSize,
  heading3: Type.h3.fontSize,
  heading4: Type.h4.fontSize,
  heading5: Type.h5.fontSize,
  heading6: Type.h6.fontSize,
} as const;

/** Inline code in a heading: the heading's size in the body's 14:16 ratio, not a fixed 14. */
function headingCodeSize(parent: unknown): { fontSize: number } | null {
  for (const [type, size] of Object.entries(HEADING_SIZES)) {
    if (parentHasType(parent, type)) {
      return { fontSize: Math.round((size * Type.secondary.fontSize) / Type.body.fontSize) };
    }
  }
  return null;
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
      const alt = node.attributes?.alt?.trim() ?? "";
      return (
        <Image
          key={node.key}
          source={{ uri: src }}
          style={mdImg.image}
          contentFit="contain"
          cachePolicy="memory-disk"
          accessibilityRole="image"
          accessibilityLabel={alt || undefined}
          accessible={alt.length > 0}
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
            inTableCell(parent) && mdTable.cellInline,
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
          accessibilityRole="link"
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
      if (parentHasType(parent, "bullet_list") && task !== null) {
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
              name="square"
              size={IconSize.sm}
              color={t.textTertiary}
              style={{ marginTop: 2, marginRight: Space.xs }}
            />
            <View style={styles._VIEW_SAFE_bullet_list_content as object}>
              {children}
            </View>
          </View>
        );
      }
      if (shouldNumberListItem(parent)) {
        const markup =
          immediateAncestorType(parent) === "ordered_list" ? (node.markup ?? ".") : ".";
        return (
          <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
            <Text
              style={[
                styles.ordered_list_icon as object,
                { minWidth: numberColumnWidth(listLargestNumber(parent), PixelRatio.getFontScale()) },
              ]}
            >
              {listItemDisplayNumber(parent, node.index)}
              {markup}
            </Text>
            <View style={[styles._VIEW_SAFE_ordered_list_content as object, mdMath.listContent]}>
              {children}
            </View>
          </View>
        );
      }
      if (immediateAncestorType(parent) === "bullet_list") {
        return (
          <View key={node.key} style={styles._VIEW_SAFE_list_item as object}>
            {listItemHasNestedList(node) ? (
              // No disc on a parent topic, but keep its column: the label lines
              // up with its siblings' text and the sub-bullets indent under it.
              <View
                style={[mdMath.listBullet, mdMath.listBulletSpacer]}
                accessible={false}
                testID="md-list-bullet-spacer"
              />
            ) : (
              <View
                style={mdMath.listBullet}
                accessible={false}
                testID="md-list-bullet"
              />
            )}
            <View style={[styles._VIEW_SAFE_bullet_list_content as object, mdMath.listContent]}>
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
    blockquote: (node: AstNode, children: ReactNode) => renderBlockquote(node, children),
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
      const section = workoutSectionParts(node);
      if (section) {
        const inline = (text: string, keyPrefix: string, color: string) =>
          splitInlineMath(text).map((part, i) =>
            part.type === "math" ? (
              <MathText
                scrollOverflow
                key={`${keyPrefix}-m-${i}`}
                latex={part.value}
                textColor={color}
              />
            ) : (
              <Text
                key={`${keyPrefix}-t-${i}`}
                style={[styles.body, styles.text, { color }]}
                selectable
              >
                {withGreenTicks(part.value, t.success, `${keyPrefix}-${i}`)}
              </Text>
            ),
          );
        return (
          <View key={node.key} testID="workout-section" style={[styles.paragraphRun, { gap: Space.xxs }]}>
            <Text
              testID="workout-heading"
              style={[styles.body, styles.text, { ...Weight.semibold, color: t.assistantText }]}
            >
              {section.heading}
            </Text>
            {section.lines.map((line, index) => {
              const { state, note } = splitWorkoutNote(line);
              const key = `${node.key}-line-${index}`;
              return (
                <View
                  key={key}
                  testID="workout-line"
                  style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center" }}
                >
                  {inline(state, `${key}-state`, t.assistantText)}
                  {note ? (
                    <View
                      testID="workout-note"
                      style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center" }}
                    >
                      <Text style={[styles.body, styles.text, { color: t.textSecondary }]}>
                        {"  — "}
                      </Text>
                      {inline(note, `${key}-note`, t.textSecondary)}
                    </View>
                  ) : null}
                </View>
              );
            })}
          </View>
        );
      }
      const step = lessonStepParts(node);
      if (step) {
        return (
          <View key={node.key} testID="lesson-step" style={styles.paragraphRun}>
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                gap: Space.xs,
              }}
            >
              <View
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: Radius.full,
                  backgroundColor: t.surfaceAlt,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Text
                  style={{
                    ...Weight.bold,
                    fontSize: Type.caption.fontSize,
                    color: t.text,
                  }}
                >
                  {step.n}
                </Text>
              </View>
              <View
                testID="lesson-step-label"
                style={{
                  flex: 1,
                  flexDirection: "row",
                  flexWrap: "wrap",
                  alignItems: "center",
                }}
              >
                {lessonLabelNodes(
                  step.label,
                  `${node.key}-label`,
                  [styles.body, styles.text, { color: t.assistantText }],
                  t.assistantText,
                )}
              </View>
            </View>
            {step.reason || step.formulas.length ? (
              <View testID="lesson-step-formula" style={{ paddingLeft: Space.xl, gap: Space.xs }}>
                {step.reason ? (
                  <View
                    testID="lesson-step-reason"
                    style={{
                      flexDirection: "row",
                      flexWrap: "wrap",
                      alignItems: "center",
                    }}
                  >
                    {splitInlineMath(step.reason).map((part, i) =>
                      part.type === "math" ? (
                        <MathText
                          scrollOverflow
                          key={`${node.key}-reason-m-${i}`}
                          latex={part.value}
                          textColor={t.textSecondary}
                        />
                      ) : (
                        <Text
                          key={`${node.key}-reason-t-${i}`}
                          style={[styles.body, styles.text, { color: t.textSecondary }]}
                          selectable
                        >
                          {part.value}
                        </Text>
                      ),
                    )}
                  </View>
                ) : null}
                {step.formulas.map((formula, i) => (
                  <MathText
                    scrollOverflow
                    key={`${node.key}-formula-${i}`}
                    latex={formula}
                  />
                ))}
              </View>
            ) : null}
          </View>
        );
      }
      // Prose-only paragraphs stay a single Text so "An **open circle**"
      // wraps as one run. Stacked frac/sqrt must leave that Text — iOS
      // sizes a View-in-Text as 0×0 and paints the numerator over the
      // previous line. Do not use `styles.paragraph` — mergeStyle copies
      // the library's flexDirection/flexWrap/width onto that key.
      const raw = astText(node);
      const runHeight = mathRunLineHeight(raw);
      // A loose list's paragraph: the item gap separates items, not a block gap.
      const inListItem = parentHasType(parent, "list_item");
      return wrapInlineChildren(
        node,
        children,
        [
          styles.body,
          styles.text,
          styles.paragraphRun,
          inListItem && styles.listParagraph,
          runHeight != null && { lineHeight: runHeight },
        ],
        [mdMath.inlineWrap, styles.paragraphRun, inListItem && styles.listParagraph],
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
        style={[mdCodeInline, inTableCell(parent) && mdTable.cellCode, headingCodeSize(parent)]}
        selectable
      >
        {node.content}
      </Text>
    ),
    bullet_list: (node: AstNode, children: ReactNode, parent: unknown, styles: StyleMap) => (
      <View
        key={node.key}
        style={[
          styles._VIEW_SAFE_bullet_list as object,
          parentHasType(parent, "list_item") && (styles.nestedList as object),
        ]}
      >
        {children}
      </View>
    ),
    ordered_list: (node: AstNode, children: ReactNode, parent: unknown, styles: StyleMap) => (
      <View
        key={node.key}
        style={[
          styles._VIEW_SAFE_ordered_list as object,
          parentHasType(parent, "list_item") && (styles.nestedList as object),
        ]}
      >
        {children}
      </View>
    ),
    strong: (
      node: AstNode,
      children: ReactNode,
      parent: unknown,
      styles: StyleMap,
    ) => wrapInlineChildren(
      node,
      children,
      [
          styles.body,
          styles.strong,
          inTableHeader(parent) && mdTable.headerText,
          // ***both***: the bold italic file, not bold drawn upright.
          parentHasType(parent, "em") && Italic.bold,
      ],
      mdMath.inlineWrap,
    ),
    em: (node: { key: string }, children: ReactNode, parent: unknown, styles: StyleMap) => (
      <Text
        key={node.key}
        style={[styles.body, styles.em, parentHasType(parent, "strong") && Italic.bold]}
        selectable
      >
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
