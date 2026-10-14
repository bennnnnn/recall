import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { RichBodyText } from "@/components/rich/RichBodyText";
import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";
import { notifySuccess, notifyWarning, selection } from "@/lib/haptics";
import i18n from "@/lib/i18n";
import { isUnfinishedJson } from "@/lib/jsonFence";
import { parseQuizFence } from "@/lib/lesson/lessonFences";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Button } from "@/ui/controls/Button";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

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
  const correct = attempt.checked && attempt.picked === quiz.answer;

  return (
    <View style={s.card} testID="quiz-card">
      <RichBodyText style={s.question}>{quiz.question}</RichBodyText>
      <View style={s.options} accessibilityRole="radiogroup">
        {quiz.options.map((option, index) => {
          const picked = attempt.picked === index;
          const isAnswer = attempt.checked && index === quiz.answer;
          const missed = attempt.checked && picked && !isAnswer;
          return (
            <Pressable
              key={`${index}:${option}`}
              onPress={() => pick(index)}
              accessibilityRole="radio"
              accessibilityState={{ checked: picked }}
              style={({ pressed }) => [
                s.option,
                picked && s.optionPicked,
                isAnswer && s.optionRight,
                missed && s.optionWrong,
                pressed && s.optionPressed,
              ]}
            >
              <View
                style={[
                  s.mark,
                  picked && s.markPicked,
                  isAnswer && s.markRight,
                  missed && s.markWrong,
                ]}
              >
                {isAnswer ? (
                  <Icon name="check" size={IconSize.xxs} color={theme.bg} />
                ) : missed ? (
                  <Icon name="close" size={IconSize.xxs} color={theme.bg} />
                ) : null}
              </View>
              <RichBodyText style={s.optionText}>{option}</RichBodyText>
            </Pressable>
          );
        })}
      </View>
      {attempt.checked ? (
        <View style={s.result} accessibilityLiveRegion="polite">
          <Text style={[s.verdict, { color: correct ? theme.success : theme.danger }]}>
            {correct ? i18n.t("rich.quiz_correct") : i18n.t("rich.quiz_wrong")}
          </Text>
          {quiz.explanation ? (
            <RichBodyText style={s.explanation}>{quiz.explanation}</RichBodyText>
          ) : null}
        </View>
      ) : (
        <Button
          title={i18n.t("rich.quiz_check")}
          onPress={check}
          size="sm"
          disabled={attempt.picked === null}
          style={s.check}
        />
      )}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      marginBottom: PARAGRAPH_GAP,
      padding: Space.md,
      gap: Space.sm,
      borderRadius: Radius.card,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
    },
    question: { ...Type.body, ...Weight.semibold, color: t.text },
    options: { gap: Space.xs },
    option: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 44,
      paddingVertical: Space.xs,
      paddingHorizontal: Space.sm,
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: t.border,
    },
    optionPicked: { borderColor: t.primary, backgroundColor: t.primaryLight },
    optionRight: { borderColor: t.success, backgroundColor: t.successLight },
    optionWrong: { borderColor: t.danger, backgroundColor: t.dangerLight },
    optionPressed: { opacity: 0.7 },
    mark: {
      width: 20,
      height: 20,
      borderRadius: Radius.full,
      borderWidth: 1.5,
      borderColor: t.textSecondary,
      alignItems: "center",
      justifyContent: "center",
    },
    markPicked: { borderColor: t.primary, borderWidth: 6 },
    markRight: { borderColor: t.success, backgroundColor: t.success, borderWidth: 0 },
    markWrong: { borderColor: t.danger, backgroundColor: t.danger, borderWidth: 0 },
    optionText: { flex: 1, ...Type.body, color: t.text },
    check: { alignSelf: "flex-start" },
    result: { gap: Space.xxs },
    verdict: { ...Type.body, ...Weight.bold },
    explanation: { ...Type.body, color: t.text },
    error: { ...Type.secondary, color: t.textSecondary, marginBottom: PARAGRAPH_GAP },
  });
}
