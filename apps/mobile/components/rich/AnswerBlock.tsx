import { type ReactNode, useMemo } from "react";
import { StyleSheet, Text, useWindowDimensions, View, type StyleProp, type TextStyle } from "react-native";
import { useTranslation } from "react-i18next";

import { ProseAnswer, ScrollingLine } from "@/components/rich/answerLines";
import { AccessibleElementChildren } from "@/components/rich/accessibleElement";
import { MathSvgView } from "@/components/rich/MathSvgView";
import { MathText } from "@/components/rich/MathText";
import { italicEdge } from "@/components/rich/mathText/runs";
import { splitAnswerNotation } from "@/lib/answerNotation";
import {
  answerReadsAsProse,
  normalizeAnswerContent,
  splitAnswerBranches,
  spokenAnswerValue,
} from "@/lib/math/answerLayout";
import { isHeavyInlineMath } from "@/lib/math/fenceRetag";
import { splitInlineMath } from "@/lib/markdown/preprocess";
import { latexLeanEm } from "@/lib/math/glyphs";
import { latexHasNestedMathView } from "@/lib/math/text";
import { stripTrailingFenceCloser } from "@/lib/fence/openTail";
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
// A display answer wider than its card shrinks this far to stay whole (14pt of 20) before it scrolls.
const ANSWER_MIN_FIT = 0.7;

function answerNeedsDisplayMath(text: string): boolean {
  if (isHeavyInlineMath(text)) return true;
  return splitInlineMath(text).some(
    (p) => p.type === "math" && isHeavyInlineMath(p.value),
  );
}

type Styles = ReturnType<typeof makeStyles>;

/**
 * The card's heading ("Answer", "Answer (a)") and its box. A value no solver checked
 * (`verified: false`) sits in the same box, only without the check.
 */
function AnswerFrame({
  parsed,
  spoken,
  styles: s,
  children,
}: {
  parsed: ReturnType<typeof splitAnswerNotation>;
  spoken: string;
  styles: Styles;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <View
      style={s.section}
      accessible
      accessibilityRole="text"
      accessibilityLabel={t("rich.answer_a11y", { text: spoken })}
    >
      <View style={s.heading}>
        <Text testID="answer-label" style={s.label}>
          {parsed.part
            ? t("rich.answer_part_label", { part: parsed.part })
            : t("rich.answer_label")}
        </Text>
      </View>
      <View testID="answer-box" style={s.box}>
        {/* The frame reads the value; nothing in the box is a second stop. */}
        <AccessibleElementChildren>{children}</AccessibleElementChildren>
      </View>
    </View>
  );
}

/**
 * The final answer, drawn like the worked layout's Answer section: the
 * "Answer" heading ("Answer (a)" for one part), and the value alone in a white,
 * bordered box.
 * Every ```answer fence lands here; the green check after the value is the
 * server's (a body that opens with `verified: true`, see lib/answerNotation.ts)
 * and needs the reply to have settled. A value no solver checked (`verified: false`)
 * sits in the same box with no check: the check is the only difference.
 *
 * Light answers stay on native `MathText`. Heavy LaTeX environments
 * (`\begin{cases|matrix|aligned|…}`) render as MathJax-SVG in a slot that
 * fills the box — never `compact` + centered zero-width wrap, which used to
 * collapse into a thin vertical sliver / tall pill inside this box.
 */
/**
 * The answer as one selectable Text. A Text that ends on a formula nested in it is the box
 * the formula's last letter leans out of (`P = IV` drew its V cut off), so it keeps that
 * ink itself and moves nothing (`endsOn`: the formula it ends on, or "").
 */
function FormulaLine({ style, endsOn, children }: { style: StyleProp<TextStyle>; endsOn: string; children: ReactNode }) {
  const { fontScale } = useWindowDimensions();
  const edge = italicEdge(latexLeanEm(endsOn), ANSWER_FONT_SIZE, fontScale, true);
  return (
    <Text style={[style, edge]} selectable>
      {children}
    </Text>
  );
}

export function AnswerBlock({ content, settled = true }: Props) {
  const theme = useTheme();
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
    <AnswerFrame parsed={parsed} spoken={spoken} styles={s}>
      {value}
    </AnswerFrame>
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
  if (answerReadsAsProse(text)) {
    return frame(
      spokenAnswerValue(parsed.body),
      <View style={s.fill}>
        <ProseAnswer parts={parts} textStyle={s.answer} flowStyle={s.prose} fontSize={ANSWER_FONT_SIZE}>
          {check}
        </ProseAnswer>
      </View>,
    );
  }
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
      spokenAnswerValue(parsed.body),
      <>
        <View style={s.fill}>
          <MathSvgView latex={text} textColor={theme.text} minHeight={48} em={ANSWER_FONT_SIZE} minFit={ANSWER_MIN_FIT} />
        </View>
        {check}
      </>,
    );
  }
  if (hasNestedView) {
    // The check sits on the last line's row, so it scrolls with that line.
    return frame(
      spokenAnswerValue(parsed.body),
      <View style={s.fill}>
        {nativeLines.map((line, lineIndex) => (
          <ScrollingLine
            key={lineIndex}
            testID={`answer-line-scroll-${lineIndex}`}
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
          </ScrollingLine>
        ))}
      </View>,
    );
  }
  return frame(
    spokenAnswerValue(parsed.body),
    <>
      {hasInlineMath ? (
        <FormulaLine style={s.answer} endsOn={parts.at(-1)?.type === "math" ? parts.at(-1)!.value : ""}>
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
        </FormulaLine>
      ) : (
        <FormulaLine style={s.answer} endsOn={text}>
          <MathText latex={text} textColor={theme.text} fontSize={ANSWER_FONT_SIZE} />
        </FormulaLine>
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
    heading: {
      flexDirection: "row",
      alignItems: "baseline",
      gap: Space.sm,
    },
    label: {
      ...Type.body,
      ...Weight.bold,
      color: t.assistantText,
    },
    // The same bordered box as a written-out answer (workout-answer): the page's own
    // background inside the stronger 1pt border the composer uses. The answer sits
    // centred; no side rule.
    box: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: t.bg,
      borderWidth: 1,
      borderColor: t.borderStrong,
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
      alignItems: "center",
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
    // A sentence answer: centred rows that wrap at the card's edge.
    prose: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "stretch",
    },
    lineScroll: {
      minWidth: "100%",
      flexGrow: 1,
      alignItems: "center",
      justifyContent: "center",
    },
    answer: {
      ...Weight.medium,
      fontSize: ANSWER_FONT_SIZE,
      lineHeight: 28,
      color: t.text,
      flexShrink: 1,
    },
  });
