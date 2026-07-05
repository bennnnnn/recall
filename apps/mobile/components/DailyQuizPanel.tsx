import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";

import { VocabQuizChoices } from "@/components/VocabQuizChoices";
import type { ProjectDailyQuiz, ProjectQuizQuestion, QuizModality } from "@/lib/api";
import type { ParsedVocabQuiz } from "@/lib/parseVocabQuiz";
import type { QuizUiStyle } from "@/lib/quizUiPrefs";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  session: ProjectDailyQuiz | null;
  loading: boolean;
  submitting: boolean;
  quizVariant: "vocab" | "trivia";
  quizUiStyle: QuizUiStyle;
  modality: QuizModality;
  allowRetry: boolean;
  onModalityChange: (modality: QuizModality) => void;
  onMcqAnswer: (question: ProjectQuizQuestion, letter: "A" | "B" | "C" | "D") => void;
  onTextAnswer: (question: ProjectQuizQuestion, text: string, modality: "definition" | "sentence") => void;
  onSkip: (question: ProjectQuizQuestion) => void;
  onRetry?: () => void;
  error?: string | null;
};

function toParsedQuiz(question: ProjectQuizQuestion): ParsedVocabQuiz {
  return {
    word: question.topic,
    partOfSpeech: question.part_of_speech ?? undefined,
    question: question.question_text,
    correct: undefined,
    choices: question.choices.map((c) => ({ letter: c.letter, text: c.text })),
    quizType: question.quiz_kind === "trivia" ? "trivia" : "vocab",
  };
}

function SimpleMcqChoices({
  quiz,
  disabled,
  onSelect,
  theme,
}: {
  quiz: ParsedVocabQuiz;
  disabled?: boolean;
  onSelect: (letter: "A" | "B" | "C" | "D") => void;
  theme: Theme;
}) {
  const s = useMemo(() => makeSimpleMcqStyles(theme), [theme]);
  const { t } = useTranslation();
  const topic = quiz.word.trim();
  const prompt =
    quiz.quizType === "trivia"
      ? quiz.question?.trim() || topic
      : quiz.question?.trim() || t("quiz.question_default");

  return (
    <View style={s.block}>
      {quiz.quizType === "vocab" ? <Text style={s.word}>{topic}</Text> : null}
      <Text style={s.prompt}>{prompt}</Text>
      {quiz.choices.map((choice) => (
        <Pressable
          key={choice.letter}
          style={s.choice}
          disabled={disabled}
          onPress={() => onSelect(choice.letter)}
        >
          <Text style={s.choiceLetter}>{choice.letter}</Text>
          <Text style={s.choiceText}>{choice.text}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function DailyQuizPanel({
  session,
  loading,
  submitting,
  quizVariant,
  quizUiStyle,
  modality,
  allowRetry,
  onModalityChange,
  onMcqAnswer,
  onTextAnswer,
  onSkip,
  onRetry,
  error,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [textAnswer, setTextAnswer] = useState("");
  const question = session?.current ?? null;
  const parsed = useMemo(() => (question ? toParsedQuiz(question) : null), [question]);

  useEffect(() => {
    setTextAnswer("");
  }, [question?.id]);

  if (loading && !session) {
    return (
      <View style={s.wrap}>
        <ActivityIndicator color={theme.primary} />
        <Text style={s.hint}>{t("daily_quiz.loading")}</Text>
      </View>
    );
  }

  if (session?.complete && !question) {
    return (
      <View style={s.wrap}>
        <Text style={s.doneTitle}>{t("daily_quiz.done_title")}</Text>
        <Text style={s.hint}>{t("daily_quiz.done_body")}</Text>
      </View>
    );
  }

  if (!question || !parsed) {
    return (
      <View style={s.wrap}>
        <Text style={s.hint}>{error ? t("daily_quiz.error") : t("daily_quiz.empty")}</Text>
        {onRetry ? (
          <Pressable style={s.secondaryBtn} onPress={onRetry}>
            <Text style={s.secondaryBtnText}>{t("common.retry")}</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }

  const showVocabModes = question.quiz_kind === "vocab";
  const showSkip = showVocabModes && modality !== "mcq";

  return (
    <View style={s.wrap}>
      <Text style={s.progress}>
        {t("daily_quiz.progress", {
          done: session?.answered_count ?? 0,
          goal: session?.daily_goal ?? 0,
        })}
      </Text>

      {showVocabModes ? (
        <View style={s.modeRow}>
          {(["mcq", "definition", "sentence"] as const).map((mode) => (
            <Pressable
              key={mode}
              style={[s.modeChip, modality === mode && s.modeChipActive]}
              onPress={() => onModalityChange(mode)}
            >
              <Text style={[s.modeChipText, modality === mode && s.modeChipTextActive]}>
                {t(`daily_quiz.mode_${mode}`)}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      {modality === "mcq" ? (
        quizUiStyle === "card" ? (
          <VocabQuizChoices
            quiz={parsed}
            variant={quizVariant}
            disabled={submitting}
            language="en"
            onSelect={(letter) => onMcqAnswer(question, letter)}
          />
        ) : (
          <SimpleMcqChoices
            quiz={parsed}
            disabled={submitting}
            theme={theme}
            onSelect={(letter) => onMcqAnswer(question, letter)}
          />
        )
      ) : (
        <View style={s.textBlock}>
          <Text style={s.word}>{question.topic}</Text>
          <Text style={s.prompt}>
            {modality === "definition"
              ? t("daily_quiz.prompt_definition")
              : t("daily_quiz.prompt_sentence")}
          </Text>
          <TextInput
            style={s.input}
            value={textAnswer}
            onChangeText={setTextAnswer}
            placeholder={t("daily_quiz.text_placeholder")}
            placeholderTextColor={theme.textTertiary}
            editable={!submitting}
            multiline
          />
          <View style={s.actionRow}>
            <Pressable
              style={[s.primaryBtn, submitting && s.primaryBtnDisabled]}
              disabled={submitting || !textAnswer.trim()}
              onPress={() => {
                const text = textAnswer.trim();
                if (!text) return;
                setTextAnswer("");
                onTextAnswer(question, text, modality);
              }}
            >
              <Text style={s.primaryBtnText}>{t("daily_quiz.check_answer")}</Text>
            </Pressable>
            {showSkip || allowRetry ? (
              <Pressable
                style={s.secondaryBtn}
                disabled={submitting}
                onPress={() => onSkip(question)}
              >
                <Text style={s.secondaryBtnText}>{t("daily_quiz.skip")}</Text>
              </Pressable>
            ) : null}
          </View>
        </View>
      )}

      {submitting ? <ActivityIndicator color={theme.primary} style={s.spinner} /> : null}
    </View>
  );
}

function makeSimpleMcqStyles(t: Theme) {
  return StyleSheet.create({
    block: { gap: 8 },
    word: { fontSize: 22, fontWeight: "700", color: t.text },
    prompt: { fontSize: 15, color: t.textSecondary, marginBottom: 4 },
    choice: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 12,
      paddingHorizontal: 12,
      borderRadius: 12,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
    },
    choiceLetter: { fontSize: 16, fontWeight: "700", color: t.primary, width: 20 },
    choiceText: { flex: 1, fontSize: 15, color: t.text },
  });
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      marginHorizontal: 12,
      marginBottom: 8,
      padding: 14,
      borderRadius: 16,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      gap: 10,
    },
    progress: { fontSize: 14, fontWeight: "600", color: t.textSecondary },
    hint: { fontSize: 15, color: t.textSecondary, textAlign: "center" },
    doneTitle: { fontSize: 18, fontWeight: "700", color: t.text, textAlign: "center" },
    modeRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    modeChip: {
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 999,
      backgroundColor: t.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    modeChipActive: { backgroundColor: t.primaryLight, borderColor: t.primary },
    modeChipText: { fontSize: 13, color: t.textSecondary, fontWeight: "500" },
    modeChipTextActive: { color: t.primary, fontWeight: "700" },
    textBlock: { gap: 8 },
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
      backgroundColor: t.bg,
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
    spinner: { marginTop: 4 },
  });
}
