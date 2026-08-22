import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { ActionShimmer } from "@/components/ActionShimmer";
import { Icon } from "@/components/Icon";
import { VocabCard } from "@/components/VocabCard";
import { LessonQuizCards } from "@/components/projects/LessonQuizCards";
import { LessonResultSheet } from "@/components/projects/LessonResultSheet";
import { LessonTypedAnswer } from "@/components/projects/LessonTypedAnswer";
import { useAuth } from "@/contexts/AuthContext";
import { useLessonSession } from "@/hooks/useLessonSession";
import {
  completedTodayCount,
  resolveProjectDailyGoal,
} from "@/lib/projects/projectChat";
import { isLanguageProject } from "@/lib/languageLevels";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function LearningLessonScreen() {
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
    feedback,
    typed,
    setTyped,
    error,
    streaming,
    submitLetter,
    submitTyped,
    continueLesson,
  } = useLessonSession(projectId);

  if (!token) return <Redirect href="/login" />;
  if (!projectId) return <Redirect href="/projects" />;

  const done = project ? completedTodayCount(project.stats) : 0;
  const goal = project ? Math.max(1, resolveProjectDailyGoal(project)) : 1;
  const progress = Math.min(1, done / goal);
  const language = project && isLanguageProject(project.kind) ? project.target_language : "en";
  const showTyped =
    !feedback && (step.kind === "vocab_card" || step.kind === "open_ended");

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
          <View style={[s.progressFill, { width: `${Math.round(progress * 100)}%` }]} />
        </View>
        <Text style={s.progressLabel}>
          {done}/{goal}
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={s.body}
        keyboardShouldPersistTaps="handled"
      >
        {step.kind === "quiz" ? (
          <>
            <Text style={s.question}>{step.question}</Text>
            <LessonQuizCards
              choices={step.quiz.choices}
              correctLetter={step.quiz.correct}
              disabled={Boolean(feedback) || streaming}
              resetToken={`${step.messageId}:${feedback ? "done" : "ready"}`}
              onSelect={submitLetter}
            />
          </>
        ) : null}
        {step.kind === "vocab_card" ? (
          <>
            <VocabCard card={step.card} language={language} />
            {step.prompt ? <Text style={s.prompt}>{step.prompt}</Text> : null}
          </>
        ) : null}
        {step.kind === "open_ended" || step.kind === "idle" ? (
          <Text style={s.question}>{step.prompt}</Text>
        ) : null}
        {step.kind === "loading" ? (
          <ActionShimmer label={t("lesson.loading")} color={theme.primary} />
        ) : null}
        {error ? <Text style={s.error}>{error}</Text> : null}
      </ScrollView>

      {showTyped ? (
        <View style={s.typedWrap}>
          <LessonTypedAnswer
            value={typed}
            onChange={setTyped}
            onSubmit={submitTyped}
            disabled={streaming}
          />
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
      minWidth: 36,
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
    prompt: {
      ...Type.secondary,
      color: theme.textSecondary,
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
