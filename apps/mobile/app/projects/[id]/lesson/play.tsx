import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { ActionShimmer } from "@/components/ActionShimmer";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { VocabCard } from "@/components/VocabCard";
import { LessonQuizCards } from "@/components/projects/LessonQuizCards";
import { LessonResultSheet } from "@/components/projects/LessonResultSheet";
import { useAuth } from "@/contexts/AuthContext";
import { useLessonSession } from "@/hooks/useLessonSession";
import { isLanguageProject } from "@/lib/languageLevels";
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
    chapter,
    step,
    feedback,
    error,
    empty,
    complete,
    currentNumber,
    total,
    progressFill,
    streaming,
    submitLetter,
    continueLesson,
    continueTeach,
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
          {currentNumber}/{Math.max(total, 1)}
        </Text>
      </View>

      <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
        {empty ? <Text style={s.status}>{t("lesson.chapter_empty")}</Text> : null}
        {complete ? <Text style={s.status}>{t("lesson.chapter_complete")}</Text> : null}
        {step?.kind === "teach" ? (
          <>
            {chapter ? <Text style={s.chapter}>{chapter}</Text> : null}
            <Text style={s.prompt}>{t("lesson.learn_this")}</Text>
            <VocabCard card={step.card} language={language} />
          </>
        ) : null}
        {quizStep ? (
          <>
            {chapter ? <Text style={s.chapter}>{chapter}</Text> : null}
            <Text style={s.question}>{quizStep.question}</Text>
            <LessonQuizCards
              choices={quizStep.quiz.choices}
              correctLetter={quizStep.quiz.correct}
              disabled={Boolean(feedback) || streaming}
              resetToken={`${quizStep.itemId}:${quizStep.kind}:${feedback ? "done" : "ready"}`}
              onSelect={submitLetter}
            />
          </>
        ) : null}
        {!step && !empty && !complete ? (
          <ActionShimmer label={t("lesson.loading")} color={theme.primary} />
        ) : null}
        {error ? <Text style={s.error}>{error}</Text> : null}
      </ScrollView>

      {step?.kind === "teach" && !feedback ? (
        <View style={s.typedWrap}>
          <Button title={t("lesson.continue")} onPress={continueTeach} />
        </View>
      ) : null}

      {feedback ? (
        <LessonResultSheet
          feedback={feedback}
          language={language}
          onContinue={continueLesson}
        />
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
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
    },
    progressTrack: {
      flex: 1,
      height: 8,
      borderRadius: 4,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    progressFill: {
      height: "100%",
      backgroundColor: theme.success,
    },
    progressLabel: {
      ...Type.caption,
      color: theme.textSecondary,
      minWidth: 44,
      textAlign: "right",
    },
    body: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.md,
      paddingBottom: Space.xl,
      gap: Space.md,
      flexGrow: 1,
    },
    question: {
      fontSize: 22,
      fontWeight: "700",
      color: theme.text,
      lineHeight: 28,
    },
    chapter: {
      ...Type.caption,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    prompt: {
      ...Type.secondary,
      color: theme.textSecondary,
    },
    status: {
      ...Type.body,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
      marginTop: Space.lg,
    },
    error: {
      ...Type.secondary,
      color: theme.danger,
      textAlign: "center",
    },
    typedWrap: {
      paddingHorizontal: Space.lg,
      paddingBottom: Space.md,
    },
  });
}
