import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { ActionShimmer } from "@/components/ActionShimmer";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { VocabCard } from "@/components/VocabCard";
import { LessonCompleteCard } from "@/components/projects/LessonCompleteCard";
import { LessonQuizCards } from "@/components/projects/LessonQuizCards";
import { useAuth } from "@/contexts/AuthContext";
import { useLessonSession } from "@/hooks/useLessonSession";
import { isLanguageProject } from "@/lib/languageLevels";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function LearningLessonPlayScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const projectId = typeof id === "string" ? id : "";
  const s = useMemo(() => makeStyles(theme), [theme]);
  const {
    project,
    step,
    error,
    empty,
    complete,
    sessionEndedEarly,
    reviewing,
    currentNumber,
    total,
    progressFill,
    saving,
    canAdvance,
    submitLetter,
    recordWrongAnswer,
    continueLesson,
  } = useLessonSession(projectId);

  if (!token) return <Redirect href="/login" />;
  if (!projectId) return <Redirect href="/projects" />;

  const language = project && isLanguageProject(project.kind) ? project.target_language : "en";
  const quizStep = step && (step.kind === "use" || step.kind === "meaning") ? step : null;

  return (
    <SafeAreaView style={s.safe} edges={["top", "bottom"]}>
      <View style={s.header}>
        <Pressable
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel={t("lesson.close")}
          hitSlop={8}
        >
          <Icon name="close" size={26} color={theme.text} />
        </Pressable>
        <View style={s.progressTrack} accessibilityRole="progressbar">
          <View style={[s.progressFill, { width: `${Math.round(progressFill * 100)}%` }]} />
        </View>
        <Text style={s.progressLabel}>
          {t(reviewing ? "lesson.review_of" : "lesson.step_of", {
            current: currentNumber,
            total: Math.max(total, 1),
          })}
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={[
          s.body,
          step?.kind === "teach" ? s.bodyCard : null,
          quizStep ? s.bodyQuiz : null,
        ]}
        keyboardShouldPersistTaps="handled"
      >
        {empty ? <Text style={s.status}>{t("lesson.chapter_empty")}</Text> : null}
        {complete ? <LessonCompleteCard /> : null}
        {sessionEndedEarly ? (
          <View style={s.pausedWrap}>
            <Text style={s.status}>{t("lesson.more_to_learn")}</Text>
            <Button title={t("common.done")} onPress={() => router.back()} />
          </View>
        ) : null}
        {step?.kind === "teach" ? (
          <VocabCard card={step.card} language={language} />
        ) : null}
        {quizStep ? <Text style={s.question}>{quizStep.question}</Text> : null}
        {quizStep ? (
          <LessonQuizCards
            choices={quizStep.quiz.choices}
            correctLetter={quizStep.quiz.correct}
            disabled={saving}
            resetToken={`${quizStep.itemId}:${quizStep.kind}`}
            onSelect={submitLetter}
            onWrongAnswer={recordWrongAnswer}
          />
        ) : null}
        {!step && !empty && !complete && !sessionEndedEarly ? (
          <ActionShimmer label={t("lesson.loading")} color={theme.primary} />
        ) : null}
      </ScrollView>

      {step && canAdvance ? (
        <View style={s.footer}>
          {error ? <Text style={s.error}>{error}</Text> : null}
          <Button
            title={t("lesson.continue")}
            onPress={continueLesson}
            loading={saving}
            disabled={saving}
            style={s.nextBtn}
          />
        </View>
      ) : null}
    </SafeAreaView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    safe: { flex: 1, backgroundColor: theme.bg },
    header: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingHorizontal: Space.lg,
      paddingTop: Space.sm,
      paddingBottom: Space.md,
    },
    progressTrack: {
      flex: 1,
      height: 5,
      borderRadius: Radius.full,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    progressFill: {
      height: "100%",
      backgroundColor: theme.primary,
    },
    progressLabel: {
      ...Type.caption,
      color: theme.textSecondary,
    },
    body: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.xl,
      paddingBottom: Space.xl,
      gap: Space.md,
      flexGrow: 1,
    },
    bodyCard: {
      flexGrow: 1,
    },
    bodyQuiz: {
      flexGrow: 1,
      justifyContent: "center",
      gap: Space.xl,
    },
    question: {
      fontSize: 22,
      fontWeight: "700",
      color: theme.text,
      lineHeight: 28,
    },
    status: {
      ...Type.body,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
      marginTop: Space.lg,
    },
    pausedWrap: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      gap: Space.lg,
    },
    footer: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.lg,
      paddingBottom: Space.lg,
      gap: Space.sm,
    },
    nextBtn: {
      minHeight: 52,
      borderRadius: 18,
    },
    error: {
      ...Type.secondary,
      color: theme.danger,
      textAlign: "center",
    },
  });
}
