import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { MathFormulaWebView } from "@/components/rich/MathFormulaWebView";
import { MathText } from "@/components/rich/MathText";
import { isHeavyInlineMath, stripEmbeddedDollarWraps, stripRedundantDollarWrap } from "@/lib/math/mathFenceRetag";
import { splitInlineMath } from "@/lib/markdown/markdownPreprocess";
import { latexHasNestedMathView, readableLatexFallback } from "@/lib/mathText";
import { stripTrailingFenceCloser } from "@/lib/streamingOpenFence";
import { Theme, useTheme } from "@/lib/theme";
import { supportsInlineHtmlMathWebView } from "@/lib/mathWebViewSupport";
import { getPreviewWebView } from "@/lib/webView";

type Props = { content: string };

function normalizeAnswerContent(raw: string): string {
  const text = stripTrailingFenceCloser(raw.trim());
  const boxed = text.match(/^\\boxed\{([\s\S]+)\}$/);
  if (boxed) return boxed[1].trim();
  return stripEmbeddedDollarWraps(stripRedundantDollarWrap(text));
}

function answerNeedsKatex(text: string): boolean {
  if (isHeavyInlineMath(text)) return true;
  return splitInlineMath(text).some((p) => p.type === "math" && isHeavyInlineMath(p.value));
}

/**
 * Final answer — same gray surface as other math blocks, no Copy affordance.
 * (```answer / short numeric or simplified-expression finals only.)
 *
 * Light answers stay on native `MathText`. Heavy LaTeX environments
 * (`\begin{cases|matrix|aligned|…}`) use the KaTeX WebView in **stretch
 * displayMode** — never `compact` + centered zero-width wrap, which used to
 * collapse into a thin vertical sliver / tall pill inside this gray box.
 */
export function AnswerBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const text = normalizeAnswerContent(content);
  const parts = splitInlineMath(text);
  const hasInlineMath = parts.some((p) => p.type === "math");
  const preview = getPreviewWebView();
  const useKatex = answerNeedsKatex(text) && supportsInlineHtmlMathWebView(preview?.mode);
  // A nested math View (stacked frac / sqrt) must be a direct child of the box,
  // NOT wrapped in a Text. iOS clips a View nested inside a Text to the line
  // box — which cut the radicand's bottom (the digit under √ lost its baseline)
  // in this gray answer box. Mirrors markdownRenderRules' nested-View guard.
  const hasNestedView = hasInlineMath
    ? parts.some((p) => p.type === "math" && latexHasNestedMathView(p.value))
    : latexHasNestedMathView(text);

  // Drop a trailing lone ":" when nested math Views are present — the colon
  // can't share the math View's line box and strands as a lone "two dots".
  // Mirrors markdownRenderRules' trailing-colon drop (MO-020).
  const trimmedParts = hasNestedView && hasInlineMath
    ? parts.filter((p, i) => {
        if (p.type !== "text") return true;
        if (i !== parts.length - 1) return true;
        return p.value.trim() !== ":";
      })
    : parts;

  return (
    <View
      style={s.row}
      accessibilityRole="text"
      accessibilityLabel={t("rich.answer_a11y", { text: readableLatexFallback(text) })}
    >
      <View style={[s.box, useKatex ? s.boxStretch : null]}>
        {useKatex ? (
          <MathFormulaWebView
            latex={text}
            displayMode
            minHeight={48}
            textColor={theme.text}
            bgColor={theme.surfaceAlt}
          />
        ) : hasNestedView ? (
          <View style={s.answerRow} testID="answer-row">
            {hasInlineMath
              ? trimmedParts.map((part, i) =>
                  part.type === "math" ? (
                    <MathText key={i} latex={part.value} textColor={theme.text} />
                  ) : (
                    <Text key={i} style={s.answer} selectable>
                      {part.value}
                    </Text>
                  ),
                )
              : (
                <MathText latex={text} textColor={theme.text} />
              )}
          </View>
        ) : hasInlineMath ? (
          <Text style={s.answer} selectable>
            {parts.map((part, i) =>
              part.type === "math" ? (
                <MathText key={i} latex={part.value} textColor={theme.text} />
              ) : (
                <Text key={i} style={s.answer}>
                  {part.value}
                </Text>
              ),
            )}
          </Text>
        ) : (
          <Text style={s.answer} selectable>
            <MathText latex={text} textColor={theme.text} />
          </Text>
        )}
      </View>
    </View>
  );
}

const makeStyles = (t: Theme) =>
  StyleSheet.create({
    row: {
      alignSelf: "stretch",
      alignItems: "center",
      marginVertical: 10,
    },
    box: {
      alignSelf: "center",
      maxWidth: "100%",
      paddingVertical: 10,
      paddingHorizontal: 18,
      // One step stronger than contentSurface so finals read on the chat
      // canvas / assistant bubble without introducing a new hue.
      backgroundColor: t.surfaceAlt,
      borderRadius: 10,
      alignItems: "center",
      justifyContent: "center",
    },
    // Full-width chrome so the KaTeX WebView gets a real layout width
    // (compact + alignSelf:center was the thin-sliver bug).
    boxStretch: {
      alignSelf: "stretch",
      alignItems: "stretch",
      paddingHorizontal: 10,
    },
    // Hosts a nested math View (sqrt/frac) as a direct child so iOS doesn't
    // clip it to a Text line box. Centers the run like the `answer` Text would.
    answerRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      flexWrap: "wrap",
    },
    answer: {
      fontSize: 20,
      lineHeight: 28,
      fontWeight: "500",
      color: t.text,
      textAlign: "center",
    },
  });
