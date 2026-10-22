import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useClarifyActions, useClarifyMessage } from "@/components/rich/clarifyContext";
import { PARAGRAPH_GAP } from "@/components/markdown/markdownContentStyles";
import { useReplyStreaming } from "@/components/markdown/ReplyStreaming";
import {
  answersFromMessage,
  canSubmitClarify,
  clarifyMessage,
  parseClarifyCard,
  type ClarifyAnswer,
  type ClarifyAnswers,
  type ClarifyQuestion,
} from "@/lib/clarify/clarifyCard";
import { selection } from "@/lib/haptics";
import i18n from "@/lib/i18n";
import { plainFenceText } from "@/lib/lesson/lessonFences";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Button } from "@/ui/controls/Button";
import { TextField } from "@/ui/controls/TextField";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

type Props = { content: string };

const NO_ANSWER: ClarifyAnswer = { picked: [], other: null };

/**
 * A few questions before (or after) an answer, each with its choices and "Other…"
 * (docs/clarify.md). Submit sends the picks as the user's next message; Skip sends
 * "Just answer". The card is live only on the newest reply, while nothing is streaming;
 * once answered it stays, read-only, with the picks ticked.
 */
export function ClarifyCard({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const card = useMemo(() => parseClarifyCard(content), [content]);
  const actions = useClarifyActions();
  const message = useClarifyMessage();
  const streaming = useReplyStreaming();
  const [answers, setAnswers] = useState<ClarifyAnswers>({});
  const [sent, setSent] = useState(false);

  const nextUserText = message?.nextUserText ?? null;
  const sentAnswers = useMemo(
    () => (card && nextUserText ? answersFromMessage(card, nextUserText) : null),
    [card, nextUserText],
  );

  if (!card) {
    const plain = plainFenceText(content);
    return plain ? <Text style={[s.question, s.plain]}>{plain}</Text> : null;
  }

  const answered = sent || nextUserText != null;
  const live = actions != null && message?.latest === true && !answered && !actions.busy && !streaming;
  const shown = sentAnswers ?? answers;

  const update = (question: ClarifyQuestion, next: ClarifyAnswer) => {
    setAnswers((prev) => ({ ...prev, [question.id]: next }));
  };
  const pick = (question: ClarifyQuestion, option: string) => {
    selection();
    const current = answers[question.id] ?? NO_ANSWER;
    if (!question.multi) return update(question, { picked: [option], other: null });
    const picked = current.picked.includes(option)
      ? current.picked.filter((item) => item !== option)
      : [...current.picked, option];
    update(question, { ...current, picked });
  };
  const pickOther = (question: ClarifyQuestion) => {
    selection();
    const current = answers[question.id] ?? NO_ANSWER;
    if (!question.multi) return update(question, { picked: [], other: current.other ?? "" });
    update(question, { ...current, other: current.other == null ? "" : null });
  };
  const send = (text: string) => {
    if (!live || !actions) return;
    setSent(true);
    actions.send(text);
  };

  return (
    <View style={s.card} testID="clarify-card">
      <View style={s.badge}>
        <Text style={s.badgeText}>{i18n.t("clarify.badge")}</Text>
      </View>
      {card.questions.map((question) => (
        <QuestionBlock
          key={question.id}
          question={question}
          answer={shown[question.id] ?? NO_ANSWER}
          live={live}
          onPick={(option) => pick(question, option)}
          onPickOther={() => pickOther(question)}
          onOtherText={(other) => update(question, { ...(answers[question.id] ?? NO_ANSWER), other })}
          s={s}
        />
      ))}
      {live ? (
        <View style={s.actions}>
          <Button
            title={i18n.t("clarify.skip")}
            variant="ghost"
            onPress={() => send(i18n.t("clarify.skip_message"))}
            accessibilityLabel={i18n.t("clarify.skip_a11y")}
          />
          <Button
            title={i18n.t("clarify.submit")}
            onPress={() => send(clarifyMessage(card, answers))}
            disabled={!canSubmitClarify(card, answers)}
          />
        </View>
      ) : null}
    </View>
  );
}

function QuestionBlock({
  question,
  answer,
  live,
  onPick,
  onPickOther,
  onOtherText,
  s,
}: {
  question: ClarifyQuestion;
  answer: ClarifyAnswer;
  live: boolean;
  onPick: (option: string) => void;
  onPickOther: () => void;
  onOtherText: (text: string) => void;
  s: Styles;
}) {
  const otherPicked = answer.other != null;
  const otherLabel =
    !live && otherPicked && answer.other
      ? i18n.t("clarify.other_answer", { text: answer.other })
      : i18n.t("clarify.other");
  return (
    <View style={s.question} accessibilityRole={question.multi ? undefined : "radiogroup"}>
      <Text style={s.questionText}>{question.question}</Text>
      {question.options.map((option) => (
        <Choice
          key={option}
          label={option}
          checked={answer.picked.includes(option)}
          multi={question.multi}
          live={live}
          onPress={() => onPick(option)}
          s={s}
        />
      ))}
      <Choice
        label={otherLabel}
        checked={otherPicked}
        multi={question.multi}
        live={live}
        onPress={onPickOther}
        s={s}
      />
      {live && otherPicked ? (
        <TextField
          value={answer.other ?? ""}
          onChangeText={onOtherText}
          placeholder={i18n.t("clarify.other_placeholder")}
          accessibilityLabel={i18n.t("clarify.other_a11y", { question: question.question })}
          maxLength={80}
          autoFocus
        />
      ) : null}
    </View>
  );
}

function Choice({
  label,
  checked,
  multi,
  live,
  onPress,
  s,
}: {
  label: string;
  checked: boolean;
  multi: boolean;
  live: boolean;
  onPress: () => void;
  s: Styles;
}) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={!live}
      accessibilityRole={multi ? "checkbox" : "radio"}
      accessibilityState={{ checked, disabled: !live }}
      style={({ pressed }) => [s.option, pressed && s.pressed, !live && !checked && s.faded]}
    >
      <View style={[multi ? s.box : s.radio, checked && s.marked]}>
        {checked && multi ? <Icon name="check" size={IconSize.xs} color={theme.bg} /> : null}
        {checked && !multi ? <View style={s.radioDot} /> : null}
      </View>
      <Text style={s.optionText}>{label}</Text>
    </Pressable>
  );
}

type Styles = ReturnType<typeof makeStyles>;

function makeStyles(t: Theme) {
  return StyleSheet.create({
    card: {
      marginBottom: PARAGRAPH_GAP,
      paddingHorizontal: Space.md,
      paddingTop: Space.md,
      paddingBottom: Space.md,
      gap: Space.md,
      borderRadius: Radius.menu,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
    },
    // The same soft pill as a lesson's "Exercise 1".
    badge: {
      alignSelf: "flex-start",
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: t.accentLight,
    },
    badgeText: { ...Type.secondary, ...Weight.semibold, color: t.accentDark },
    question: { gap: Space.xxs },
    questionText: { ...Type.body, ...Weight.semibold, color: t.text, marginBottom: Space.xxs },
    option: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: 44,
      paddingVertical: Space.xxs,
    },
    pressed: { opacity: 0.6 },
    faded: { opacity: 0.55 },
    radio: {
      width: 22,
      height: 22,
      borderRadius: Radius.full,
      borderWidth: 1.5,
      borderColor: t.textSecondary,
      alignItems: "center",
      justifyContent: "center",
    },
    box: {
      width: 22,
      height: 22,
      borderRadius: Radius.row,
      borderWidth: 1.5,
      borderColor: t.textSecondary,
      alignItems: "center",
      justifyContent: "center",
    },
    marked: { borderColor: t.text, backgroundColor: t.text },
    radioDot: {
      width: 8,
      height: 8,
      borderRadius: Radius.full,
      backgroundColor: t.bg,
    },
    optionText: { flex: 1, ...Type.body, color: t.text },
    actions: { flexDirection: "row", justifyContent: "flex-end", gap: Space.xs },
    plain: { marginBottom: PARAGRAPH_GAP },
  });
}
