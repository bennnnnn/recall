import { type ReactNode, useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { MathSvgView } from "@/components/rich/MathSvgView";
import { MathText } from "@/components/rich/MathText";
import { splitAnswerNotation } from "@/lib/answerNotation";
import { splitAnswerBranches } from "@/lib/math/answerLayout";
import {
  isHeavyInlineMath,
  stripEmbeddedDollarWraps,
  stripRedundantDollarWrap,
} from "@/lib/math/fenceRetag";
import { rewriteSolutionSeparatorBars } from "@/lib/math/solutionBars";
import { splitInlineMath } from "@/lib/markdown/preprocess";
import { latexHasNestedMathView, readableLatexFallback } from "@/lib/math/text";
import { stripTrailingFenceCloser } from "@/lib/streamingOpenFence";
import { Theme, useTheme } from "@/lib/theme";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type, Weight } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";

type Props = {
  content: string;
  /** A settled reply. A streaming one must not show the success check yet. */
  settled?: boolean;
};

// Match standalone KaTeX and the answer text role, including nested native math.
const ANSWER_FONT_SIZE = 20;

function normalizeAnswerContent(raw: string): string {
  const text = stripTrailingFenceCloser(raw.trim());
  const boxed = text.match(/^\\boxed\{([\s\S]+)\}$/);
  if (boxed) return rewriteSolutionSeparatorBars(boxed[1].trim());
  return rewriteSolutionSeparatorBars(
    stripEmbeddedDollarWraps(stripRedundantDollarWrap(text)),
  );
}

function answerNeedsDisplayMath(text: string): boolean {
  if (isHeavyInlineMath(text)) return true;
  return splitInlineMath(text).some(
    (p) => p.type === "math" && isHeavyInlineMath(p.value),
  );
}

/**
 * The final answer, drawn like the worked layout's Answer section: the
 * "Answer" heading, a thin rule, and the value alone in an accent-tinted box.
 * Every ```answer fence lands here; the green check after the value is the
 * server's (a body that opens with `verified: true`, see lib/answerNotation.ts)
 * and needs the reply to have settled.
 *
 * Light answers stay on native `MathText`. Heavy LaTeX environments
 * (`\begin{cases|matrix|aligned|…}`) render as MathJax-SVG in a slot that
 * fills the box — never `compact` + centered zero-width wrap, which used to
 * collapse into a thin vertical sliver / tall pill inside this box.
 */
export function AnswerBlock({ content, settled = true }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const parsed = splitAnswerNotation(stripTrailingFenceCloser(content.trim()));
  const check =
    settled && parsed.verified ? (
      <Icon
        testID="answer-success-check"
        name="check-circle-filled"
        size={IconSize.md}
        color={theme.success}
        style={s.successCheck}
      />
    ) : null;
  const frame = (spoken: string, value: ReactNode) => (
    <View
      style={s.section}
      accessibilityRole="text"
      accessibilityLabel={t("rich.answer_a11y", { text: spoken })}
    >
      {parsed.labeled ? (
        <Text testID="answer-label" style={s.label}>
          {t("rich.answer_label")}
        </Text>
      ) : null}
      <View testID="answer-rule" style={s.rule}>
        <View testID="answer-box" style={s.box}>
          {value}
        </View>
      </View>
    </View>
  );
  if (parsed.notation === "chemistry" && parsed.body) {
    return frame(
      parsed.body,
      <>
        <Text testID="answer-literal" style={s.answer} selectable>
          {parsed.body}
        </Text>
        {check}
      </>,
    );
  }
  const text = normalizeAnswerContent(parsed.body);
  const parts = splitInlineMath(text);
  const hasInlineMath = parts.some((p) => p.type === "math");
  const useSvgMath = answerNeedsDisplayMath(text);
  // A nested math View (stacked frac / sqrt) must be a direct child of the box,
  // NOT wrapped in a Text. iOS clips a View nested inside a Text to the line
  // box — which cut the radicand's bottom (the digit under √ lost its baseline)
  // in this answer box. Mirrors markdownRenderRules' nested-View guard.
  const hasNestedView = hasInlineMath
    ? parts.some((p) => p.type === "math" && latexHasNestedMathView(p.value))
    : latexHasNestedMathView(text);
  const nativeLines = hasInlineMath ? [text] : splitAnswerBranches(text);

  // Drop a trailing lone ":" when nested math Views are present — the colon
  // can't share the math View's line box and strands as a lone "two dots".
  // Mirrors markdownRenderRules' trailing-colon drop (MO-020).
  const trimmedParts =
    hasNestedView && hasInlineMath
      ? parts.filter((p, i) => {
          if (p.type !== "text") return true;
          if (i !== parts.length - 1) return true;
          return p.value.trim() !== ":";
        })
      : parts;

  if (useSvgMath) {
    return frame(
      readableLatexFallback(text),
      <>
        <View style={s.fill}>
          <MathSvgView latex={text} textColor={theme.text} minHeight={48} />
        </View>
        {check}
      </>,
    );
  }
  if (hasNestedView) {
    // The check sits on the last line's row, so it scrolls with that line.
    return frame(
      readableLatexFallback(text),
      <View style={s.fill}>
        {nativeLines.map((line, lineIndex) => (
          <ScrollView
            key={lineIndex}
            testID={`answer-line-scroll-${lineIndex}`}
            horizontal
            nestedScrollEnabled
            showsHorizontalScrollIndicator
            bounces={false}
            style={s.lineViewport}
            contentContainerStyle={s.lineScroll}
          >
            <View
              style={s.answerRow}
              testID={lineIndex === 0 ? "answer-row" : `answer-row-${lineIndex}`}
            >
              {hasInlineMath ? (
                trimmedParts.map((part, i) =>
                  part.type === "math" ? (
                    <MathText
                      key={i}
                      latex={part.value}
                      textColor={theme.text}
                      fontSize={ANSWER_FONT_SIZE}
                    />
                  ) : (
                    <Text key={i} style={s.answer} selectable>
                      {part.value}
                    </Text>
                  ),
                )
              ) : (
                <MathText latex={line} textColor={theme.text} fontSize={ANSWER_FONT_SIZE} />
              )}
              {lineIndex === nativeLines.length - 1 ? check : null}
            </View>
          </ScrollView>
        ))}
      </View>,
    );
  }
  return frame(
    readableLatexFallback(text),
    <>
      {hasInlineMath ? (
        <Text style={s.answer} selectable>
          {parts.map((part, i) =>
            part.type === "math" ? (
              <MathText
                key={i}
                latex={part.value}
                textColor={theme.text}
                fontSize={ANSWER_FONT_SIZE}
              />
            ) : (
              <Text key={i} style={s.answer}>
                {part.value}
              </Text>
            ),
          )}
        </Text>
      ) : (
        <Text style={s.answer} selectable>
          <MathText latex={text} textColor={theme.text} fontSize={ANSWER_FONT_SIZE} />
        </Text>
      )}
      {check}
    </>,
  );
}

const makeStyles = (t: Theme) =>
  StyleSheet.create({
    // The worked layout's section: heading at the margin, the work behind a rule.
    section: {
      alignSelf: "stretch",
      gap: Space.xs,
      marginBottom: PARAGRAPH_GAP,
    },
    label: {
      ...Type.body,
      ...Weight.semibold,
      color: t.assistantText,
    },
    rule: {
      marginLeft: Space.xxs,
      paddingLeft: Space.sm,
      borderLeftWidth: 2,
      borderLeftColor: t.separator,
    },
    // The same tinted box as a written-out answer (workout-answer), so it
    // follows the accent colour.
    box: {
      flexDirection: "row",
      alignItems: "center",
      backgroundColor: t.accentLight,
      borderRadius: Radius.md,
      paddingVertical: Space.sm,
      paddingHorizontal: Space.md,
    },
    // Gives the MathJax-SVG view and the scrolling lines a real layout width
    // (compact + alignSelf:center was the thin-sliver bug).
    fill: {
      flex: 1,
      minWidth: 0,
      gap: Space.xs,
    },
    successCheck: {
      marginLeft: Space.xs,
    },
    // Hosts a nested math View (sqrt/frac) as a direct child so iOS doesn't
    // clip it to a Text line box.
    answerRow: {
      flexDirection: "row",
      alignItems: "center",
      flexWrap: "nowrap",
      flexShrink: 0,
    },
    lineViewport: {
      alignSelf: "stretch",
    },
    lineScroll: {
      minWidth: "100%",
      flexGrow: 1,
      alignItems: "center",
    },
    answer: {
      // Source Sans Medium: a bare 500 weight drew the system font.
      ...Weight.medium,
      fontSize: ANSWER_FONT_SIZE,
      lineHeight: 28,
      color: t.text,
      flexShrink: 1,
    },
  });
