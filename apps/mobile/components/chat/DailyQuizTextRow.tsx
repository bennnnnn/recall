import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import type { ParsedDailyQuizText } from "@/lib/dailyQuizMessage";
import type { ProjectQuizQuestion } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  parsed: ParsedDailyQuizText;
  question: ProjectQuizQuestion;
  submitting: boolean;
  allowRetry: boolean;
  active: boolean;
  onModalityChange: (modality: "mcq" | "definition" | "sentence") => void;
  onTextAnswer: (text: string, modality: "definition" | "sentence") => void;
  onSkip: () => void;
};

export function DailyQuizTextRow({
  parsed,
  question,
  submitting,
  allowRetry,
  active,
  onModalityChange,
  onTextAnswer,
  onSkip,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [textAnswer, setTextAnswer] = useState("");

  useEffect(() => {
    setTextAnswer("");
  }, [question.id, parsed.modality]);

  return (
    <View style={s.row}>
      <View style={s.bubble}>
        <Text style={s.progress}>
          {t("daily_quiz.progress", { done: parsed.progress.done, goal: parsed.progress.goal })}
        </Text>
        <View style={s.modeRow}>
          {(["mcq", "definition", "sentence"] as const).map((mode) => (
            <Pressable
              key={mode}
              style={[s.modeChip, parsed.modality === mode && s.modeChipActive]}
              disabled={!active || submitting}
              onPress={() => onModalityChange(mode)}
            >
              <Text style={[s.modeChipText, parsed.modality === mode && s.modeChipTextActive]}>
                {t(`daily_quiz.mode_${mode}`)}
              </Text>
            </Pressable>
          ))}
        </View>
        <Text style={s.word}>{parsed.topic}</Text>
        <Text style={s.prompt}>
          {parsed.modality === "definition"
            ? t("daily_quiz.prompt_definition")
            : t("daily_quiz.prompt_sentence")}
        </Text>
        <TextInput
          style={s.input}
          value={textAnswer}
          onChangeText={setTextAnswer}
          placeholder={t("daily_quiz.text_placeholder")}
          placeholderTextColor={theme.textTertiary}
          editable={active && !submitting}
          multiline
        />
        {active ? (
          <View style={s.actionRow}>
            <Pressable
              style={[s.primaryBtn, (submitting || !textAnswer.trim()) && s.primaryBtnDisabled]}
              disabled={submitting || !textAnswer.trim()}
              onPress={() => {
                const text = textAnswer.trim();
                if (!text) return;
                setTextAnswer("");
                onTextAnswer(text, parsed.modality);
              }}
            >
              <Text style={s.primaryBtnText}>{t("daily_quiz.check_answer")}</Text>
            </Pressable>
            {allowRetry ? (
              <Pressable style={s.secondaryBtn} disabled={submitting} onPress={onSkip}>
                <Text style={s.secondaryBtnText}>{t("daily_quiz.skip")}</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}
      </View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    row: { marginVertical: 4, paddingHorizontal: 16, alignItems: "stretch" },
    bubble: { gap: 10, paddingVertical: 2 },
    progress: { fontSize: 14, fontWeight: "600", color: t.textSecondary },
    modeRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    modeChip: {
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 999,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    modeChipActive: { backgroundColor: t.primaryLight, borderColor: t.primary },
    modeChipText: { fontSize: 13, color: t.textSecondary, fontWeight: "500" },
    modeChipTextActive: { color: t.primary, fontWeight: "700" },
    word: { fontSize: 22, fontWeight: "700", color: t.text },
    prompt: { fontSize: 15, color: t.textSecondary },
    input: {
      minHeight: 72,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      borderRadius: 12,
      padding: 12,
      fontSize: 16,
      color: t.text,
      backgroundColor: t.surface,
      textAlignVertical: "top",
    },
    actionRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, alignItems: "center" },
    primaryBtn: {
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderRadius: 12,
      backgroundColor: t.primary,
    },
    primaryBtnDisabled: { opacity: 0.5 },
    primaryBtnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
    secondaryBtn: {
      paddingHorizontal: 14,
      paddingVertical: 8,
      borderRadius: 10,
      backgroundColor: t.primaryLight,
    },
    secondaryBtnText: { color: t.primary, fontWeight: "600" },
  });
}
