import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { MathBlock } from "@/components/rich/MathView";
import { MathText } from "@/components/rich/MathText";
import { looksLikeLatexFence } from "@/lib/mathFenceRetag";
import { splitInlineMath } from "@/lib/markdownPreprocess";
import { Theme, useTheme } from "@/lib/theme";

type Props = { content: string };

function normalizeAnswerContent(raw: string): string {
  const text = raw.trim();
  const boxed = text.match(/^\\boxed\{([\s\S]+)\}$/);
  if (boxed) return boxed[1].trim();
  return text;
}

/**
 * Final-answer / definition card — same gray surface as other math blocks,
 * no Copy affordance. Prefer MathBlock when the body is equation-like.
 */
export function AnswerBlock({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const text = normalizeAnswerContent(content);
  const parts = splitInlineMath(text);
  const hasInlineMath = parts.some((p) => p.type === "math");

  // Equation bodies render like every other display-math fence (gray MathBlock).
  if (!hasInlineMath && looksLikeLatexFence(text)) {
    return <MathBlock latex={text} />;
  }

  return (
    <View style={s.wrap} accessibilityRole="text" accessibilityLabel={`Answer: ${text}`}>
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
          {text}
        </Text>
      )}
    </View>
  );
}

const makeStyles = (t: Theme) =>
  StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      marginVertical: 6,
      paddingVertical: 12,
      paddingHorizontal: 14,
      borderRadius: 10,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.contentSurface,
      alignItems: "center",
      justifyContent: "center",
    },
    answer: {
      fontSize: 18,
      lineHeight: 26,
      fontWeight: "600",
      color: t.text,
      textAlign: "center",
    },
  });
