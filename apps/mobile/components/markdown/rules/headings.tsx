import type { ReactNode } from "react";
import { StyleSheet, View, type TextStyle } from "react-native";

import { splitStreamCaret, StreamingCursor } from "@/components/StreamingCursor";
import { type AstNode, astText } from "@/components/markdown/markdownAstHelpers";
import { STEP_BADGE, type StyleMap } from "@/components/markdown/markdownContentStyles";
import { lessonLabelNodes } from "@/components/markdown/rules/lesson";
import { StepBadge } from "@/components/markdown/rules/stepBadge";
import type { Theme } from "@/lib/theme";

const LEVELS = [1, 2, 3, 4, 5, 6] as const;

/** "1. Divide every term by a", "2) …", "Step 3: …": a heading that numbers a step. */
const STEP_HEADING = /^(?:step\s+)?(\d{1,2})\s*[.:)]\s+(\S[\s\S]*)$/i;

const PLAIN = new Set(["text", "textgroup", "softbreak", "hardbreak"]);

function holdsLink(node: AstNode): boolean {
  return node.type === "link" || (node.children ?? []).some(holdsLink);
}

/** Words and `$maths$` only: emphasis, code or a link keep the library's heading. */
function plainHeading(node: AstNode): boolean {
  return (node.children ?? []).every(
    (kid) => PLAIN.has(kid.type ?? "") && plainHeading(kid),
  );
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
    const type = `heading${level}`;
    rules[type] = (node, children, _parent, styles) => {
      const marked = splitStreamCaret(astText(node).trim());
      const step = plainHeading(node) ? STEP_HEADING.exec(marked.text) : null;
      if (step) {
        const text = headingText(styles[type] ?? {});
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
              {lessonLabelNodes(step[2]!, `${node.key}-label`, text, String(text.color ?? t.text))}
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
