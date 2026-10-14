import { type ComponentProps, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { CodeBlock } from "@/components/CodeBlock";
import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";
import { CODE_FONT } from "@/lib/fonts";
import { notifySuccess, notifyWarning, selection } from "@/lib/haptics";
import i18n from "@/lib/i18n";
import { isUnfinishedJson } from "@/lib/jsonFence";
import { explanationParts, parseQuizFence } from "@/lib/lesson/lessonFences";
import { parseInlineMarkdown } from "@/lib/markdown/inlineMarkdown";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Italic, Type, Weight } from "@/lib/type";
import { Button } from "@/ui/controls/Button";

type Props = { content: string };
type Attempt = { picked: number | null; checked: boolean };

// The answer stays picked when the list recycles the message off screen and back.
const attempts = new Map<string, Attempt>();

/** "Your turn": pick an option, check it, see why. Nothing is sent to the chat. */
export function QuizCard({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const quiz = useMemo(() => parseQuizFence(content), [content]);
  const [attempt, setAttempt] = useState<Attempt>(
    () => attempts.get(content) ?? { picked: null, checked: false },
  );

  if (!quiz) {
    if (isUnfinishedJson(content)) return null;
    return <Text style={s.error}>{i18n.t("rich.quiz_error")}</Text>;
  }

  const save = (next: Attempt) => {
    attempts.set(content, next);
    setAttempt(next);
  };
  const pick = (index: number) => {
    selection();
    save({ picked: index, checked: false });
  };
  const check = () => {
    if (attempt.picked === null) return;
    if (attempt.picked === quiz.answer) notifySuccess();
    else notifyWarning();
    save({ ...attempt, checked: true });
  };
  const correct = attempt.picked === quiz.answer;
  const parts = explanationParts(quiz.explanation);
  // The verdict opens the first paragraph: "Not quite. enumerate() gives you …"
  const lead = parts[0]?.kind === "text" ? parts[0].text : null;
  const rest = lead === null ? parts : parts.slice(1);

  return (
    <View style={s.card} testID="quiz-card">
      <ChipText style={s.question} chip={s.chip}>
        {quiz.question}
      </ChipText>
      <View accessibilityRole="radiogroup">
        {quiz.options.map((option, index) => {
          const picked = attempt.picked === index;
          return (
            <Pressable
              key={`${index}:${option}`}
              onPress={() => pick(index)}
              accessibilityRole="radio"
              accessibilityState={{ checked: picked }}
              style={({ pressed }) => [s.option, pressed && s.pressed]}
            >
              <View style={[s.radio, picked && s.radioPicked]}>
                {picked ? <View style={s.radioDot} /> : null}
              </View>
              <ChipText style={s.optionText} chip={s.chip}>
                {option}
              </ChipText>
            </Pressable>
          );
        })}
      </View>
      <Button
        title={i18n.t("rich.quiz_check")}
        onPress={check}
        disabled={attempt.picked === null || attempt.checked}
      />
      {attempt.checked ? (
        <View style={s.result} accessibilityLiveRegion="polite">
          <Text style={s.explanation}>
            <Text style={s.verdict}>
              {correct
                ? i18n.t("rich.quiz_correct")
                : i18n.t("rich.quiz_wrong")}
            </Text>
            {lead ? " " : null}
            {lead ? <ChipSpans text={lead} chip={s.chip} /> : null}
          </Text>
          {rest.map((part, index) =>
            part.kind === "code" ? (
              <CodeBlock key={index} code={part.code} lang={part.lang} />
            ) : (
              <ChipText key={index} style={s.explanation} chip={s.chip}>
                {part.text}
              </ChipText>
            ),
          )}
        </View>
      ) : null}
    </View>
  );
}

type TextStyleProp = ComponentProps<typeof Text>["style"];

/** Inline markdown with `code` drawn as a gray chip, as in ChatGPT's quiz. */
function ChipText({
  children,
  style,
  chip,
}: {
  children: string;
  style: TextStyleProp;
  chip: TextStyleProp;
}) {
  return (
    <Text style={style}>
      <ChipSpans text={children} chip={chip} />
    </Text>
  );
}

function ChipSpans({ text, chip }: { text: string; chip: TextStyleProp }) {
  const tokens = useMemo(() => parseInlineMarkdown(text), [text]);
  if (tokens.length === 0) return <>{text}</>;
  return (
    <>
      {tokens.map((token, index) => {
        if (token.type === "code") {
          // Thin spaces pad the chip; nested Text takes no padding.
          return (
            <Text key={index} style={chip}>
              {` ${token.value} `}
            </Text>
          );
        }
        if (token.type === "bold") {
          return (
            <Text key={index} style={Weight.bold}>
              {token.value}
            </Text>
          );
        }
        if (token.type === "italic") {
          return (
            <Text key={index} style={Italic.regular}>
              {token.value}
            </Text>
          );
        }
        return token.value;
      })}
    </>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      marginBottom: PARAGRAPH_GAP,
      paddingHorizontal: Space.md,
      paddingTop: Space.md,
      paddingBottom: Space.lg,
      gap: Space.sm,
      borderRadius: Radius.menu,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
    },
    question: { ...Type.body, ...Weight.semibold, color: t.text },
    option: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 44,
      paddingVertical: Space.xxs,
    },
    pressed: { opacity: 0.6 },
    radio: {
      width: 22,
      height: 22,
      borderRadius: Radius.full,
      borderWidth: 1.5,
      borderColor: t.textSecondary,
      alignItems: "center",
      justifyContent: "center",
    },
    radioPicked: { borderColor: t.text, backgroundColor: t.text },
    radioDot: {
      width: 8,
      height: 8,
      borderRadius: Radius.full,
      backgroundColor: t.bg,
    },
    optionText: { flex: 1, ...Type.body, color: t.text },
    // Same size as inline code in replies, on a gray chip.
    chip: {
      ...Type.secondary,
      fontFamily: CODE_FONT,
      color: t.text,
      backgroundColor: t.surfaceAlt,
    },
    result: { gap: Space.sm, paddingHorizontal: Space.xxs },
    verdict: { ...Weight.bold, color: t.text },
    explanation: { ...Type.body, color: t.text },
    error: {
      ...Type.secondary,
      color: t.textSecondary,
      marginBottom: PARAGRAPH_GAP,
    },
  });
}
