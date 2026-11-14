import type { ReactNode } from "react";
import { StyleSheet, View, type TextStyle } from "react-native";

import { splitStreamCaret, StreamingCursor } from "@/components/StreamingCursor";
import { InlineCode } from "@/components/markdown/InlineCode";
import type { AstNode } from "@/components/markdown/markdownAstHelpers";
import {
  inlineCodeTextStyle,
  STEP_BADGE,
  type StyleMap,
} from "@/components/markdown/markdownContentStyles";
import { headingCodeFontSize } from "@/components/markdown/rules/code";
import { lessonLabelNodes } from "@/components/markdown/rules/lesson";
import { StepBadge } from "@/components/markdown/rules/stepBadge";
import { readInlineCodeSpan } from "@/lib/markdown/inlineCode";
import type { Theme } from "@/lib/theme";

const LEVELS = [1, 2, 3, 4, 5, 6] as const;

/** "1. Divide every term by a", "2) …", "Step 3: …": a heading that numbers a step. */
const STEP_HEADING = /^(?:step\s+)?(\d{1,2})\s*[.:)]\s+(\S[\s\S]*)$/i;

const PLAIN = new Set(["text", "textgroup", "softbreak", "hardbreak", "code_inline"]);

function holdsLink(node: AstNode): boolean {
  return node.type === "link" || (node.children ?? []).some(holdsLink);
}

/** Words, `$maths$` and `code` only: emphasis or a link keep the library's heading. */
function plainHeading(node: AstNode): boolean {
  return (node.children ?? []).every(
    (kid) => PLAIN.has(kid.type ?? "") && plainHeading(kid),
  );
}

/** The heading as written: a code span keeps its backticks, so its label draws the chip
 * ("### 3. Filtering with `if`" lost its number when it held code). */
function headingSource(node: AstNode): string {
  if (node.type === "code_inline") {
    const code = node.content ?? "";
    // One tick more than the code's longest run of them, as CommonMark fences a span.
    const longest = Math.max(0, ...Array.from(code.matchAll(/`+/g), (run) => run[0].length));
    const ticks = "`".repeat(longest + 1);
    return longest ? `${ticks} ${code} ${ticks}` : `${ticks}${code}${ticks}`;
  }
  if (node.content) return node.content;
  return (node.children ?? []).map(headingSource).join("");
}

/** The heading's text style without the row layout the library gives its container. */
function headingText(style: object): TextStyle {
  const {
    marginTop: _top,
    marginBottom: _bottom,
    flexDirection: _direction,
    flexWrap: _wrap,
    alignItems: _align,
    ...text
  } = (StyleSheet.flatten(style) ?? {}) as TextStyle;
  return text;
}

/** A step heading's words: its maths typeset as a lesson step's label is, its code a chip. */
function stepLabel(
  label: string,
  key: string,
  text: TextStyle,
  code: TextStyle,
  color: string,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let from = 0;
  for (let at = label.indexOf("`"); at >= 0; at = label.indexOf("`", at + 1)) {
    const end = readInlineCodeSpan(label, at);
    if (end == null) continue;
    if (at > from) nodes.push(lessonLabelNodes(label.slice(from, at), `${key}-${from}`, text, color));
    const ticks = /^`+/.exec(label.slice(at))![0].length;
    nodes.push(
      <InlineCode key={`${key}-code-${at}`} style={code}>
        {label.slice(at + ticks, end - ticks).trim()}
      </InlineCode>,
    );
    from = end;
    at = end - 1;
  }
  if (from < label.length) nodes.push(lessonLabelNodes(label.slice(from), `${key}-${from}`, text, color));
  return nodes;
}

/**
 * A reply's `#` headings, drawn as the library draws them, are headings to a
 * screen reader too, so VoiceOver's rotor and TalkBack's heading navigation
 * jump between the sections of a long answer. The heading is read as one
 * element; one that holds a link stays open, so its link can still be focused.
 * A heading that numbers a step ("### 1. Divide every term by a") puts its number
 * in the badge a server-written step has, its words where that step's label starts.
 */
export function headingRules(t: Theme) {
  const rules: Record<string, (node: AstNode, children: ReactNode, parent: unknown, styles: StyleMap) => ReactNode> = {};
  for (const level of LEVELS) {
    const type = `heading${level}` as const;
    rules[type] = (node, children, _parent, styles) => {
      const marked = splitStreamCaret(headingSource(node).trim());
      const step = plainHeading(node) ? STEP_HEADING.exec(marked.text) : null;
      if (step) {
        const text = headingText(styles[type] ?? {});
        const code = { ...inlineCodeTextStyle(t), fontSize: headingCodeFontSize(type) };
        return (
          <View
            key={node.key}
            testID="step-heading"
            style={[
              styles[`_VIEW_SAFE_${type}`],
              { flexDirection: "row", alignItems: "flex-start", gap: STEP_BADGE.gap },
            ]}
            accessible
            accessibilityRole="header"
          >
            <StepBadge n={step[1]!} t={t} lineHeight={text.lineHeight} />
            <View style={{ flex: 1, flexDirection: "row", flexWrap: "wrap", alignItems: "baseline" }}>
              {stepLabel(step[2]!, `${node.key}-label`, text, code, String(text.color ?? t.text))}
              {marked.caret ? <StreamingCursor inline /> : null}
            </View>
          </View>
        );
      }
      return (
        <View
          key={node.key}
          style={styles[`_VIEW_SAFE_${type}`]}
          accessible={!holdsLink(node)}
          accessibilityRole="header"
        >
          {children}
        </View>
      );
    };
  }
  return rules;
}
