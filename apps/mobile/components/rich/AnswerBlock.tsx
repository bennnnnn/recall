import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { MathText } from "@/components/rich/MathText";
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
 * Highlighted final-answer card for math (and similar) results — a rectangle
 * with no Copy affordance. Copy templates are for paste-and-send drafts only.
 */
export function AnswerBlock({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const text = normalizeAnswerContent(content);
  const parts = splitInlineMath(text);
  const hasMath = parts.some((p) => p.type === "math");

  return (
    <View style={s.wrap} accessibilityRole="text" accessibilityLabel={`Answer: ${text}`}>
      {hasMath ? (
        <Text style={s.answer} selectable>
          {parts.map((part, i) =>
            part.type === "math" ? (
              <MathText key={i} latex={part.value} textColor={theme.primary} />
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
      marginVertical: 8,
      paddingVertical: 16,
      paddingHorizontal: 18,
      borderRadius: 12,
      borderWidth: 1.5,
      borderColor: t.primary,
      backgroundColor: t.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    answer: {
      fontSize: 28,
      lineHeight: 36,
      fontWeight: "700",
      color: t.primary,
      textAlign: "center",
    },
  });
