import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { MathText } from "@/components/rich/MathText";
import { stripEmbeddedDollarWraps, stripRedundantDollarWrap } from "@/lib/mathFenceRetag";
import { splitInlineMath } from "@/lib/markdownPreprocess";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

function normalizeAnswerContent(raw: string): string {
  const text = raw.trim();
  const boxed = text.match(/^\\boxed\{([\s\S]+)\}$/);
  if (boxed) return boxed[1].trim();
  return stripEmbeddedDollarWraps(stripRedundantDollarWrap(text));
}

/**
 * Final answer — same gray surface as other math blocks, no Copy affordance.
 * (```answer / short numeric or simplified-expression finals only.)
 *
 * Always renders via native `MathText` (no WebView). A WebView in the
 * centered gray box had no intrinsic width — `alignSelf: "center"` collapsed
 * it to a thin vertical sliver (the "thin line" artifact), and its
 * grow-only/overshooting height reports stretched the box into a tall pill.
 * `MathText` handles every token a final answer uses (\pm → ±, \text{},
 * \sqrt{}, \frac, superscripts, Greek) with reliable native layout.
 */
export function AnswerBlock({ content }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const text = normalizeAnswerContent(content);
  const parts = splitInlineMath(text);
  const hasInlineMath = parts.some((p) => p.type === "math");

  return (
    <View style={s.row} accessibilityRole="text" accessibilityLabel={t("rich.answer_a11y", { text })}>
      <View style={s.box}>
        {hasInlineMath ? (
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
    answer: {
      fontSize: 20,
      lineHeight: 28,
      fontWeight: "500",
      color: t.text,
      textAlign: "center",
    },
  });
