import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";
import { ActionShimmer } from "@/components/ActionShimmer";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { StateView } from "@/components/StateView";
import { VocabCard } from "@/components/VocabCard";
import { LessonCompleteCard } from "@/components/projects/LessonCompleteCard";
import { LessonQuizCards } from "@/components/projects/LessonQuizCards";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useLessonFeedback } from "@/hooks/useLessonFeedback";
import { useLessonSession } from "@/hooks/useLessonSession";
import { isLanguageProject } from "@/lib/languageLevels";
import { lessonMapPath } from "@/lib/projects/chapterAccess";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function LearningLessonPlayScreen() {
  const owner = useAccountViewOwner();
  return <LessonPlayContent key={owner.key} isCurrent={owner.isCurrent} />;
}

export function LessonPlayContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const projectId = typeof id === "string" ? id : "";
  const s = useMemo(() => makeStyles(theme), [theme]);
  const lesson = useLessonSession(projectId, isCurrent);
  const {
    project,
    step,
    answer,
    error,
    empty,
    complete,
    reviewing,
    currentNumber,
    total,
    progressFill,
    saving,
    canAdvance,
    submitLetter,
    continueLesson,
  } = lesson;
  const audio = useLessonFeedback(answer, isCurrent);
  if (!token) return <Redirect href="/login" />;
  if (!projectId) return <Redirect href="/projects" />;
  const language = project && isLanguageProject(project.kind) ? project.target_language : "en";
  const quiz = step && step.kind !== "teach" ? step : null;
  const back = () => {
    if (isCurrent()) {
      audio.stop();
      router.replace(lessonMapPath(projectId));
    }
  };
  const retryLoad = () => {
    if (isCurrent()) void lesson.load({ force: true });
  };
  return (
    <SafeAreaView style={s.safe} edges={["top", "bottom"]}>
      <View style={s.header}>
        <Pressable
          onPress={back}
          accessibilityRole="button"
          accessibilityLabel={t("lesson.close")}
          hitSlop={8}
        >
          <Icon name="close" size={26} color={theme.text} />
        </Pressable>
        <View
          style={s.progressTrack}
          accessibilityRole="progressbar"
          accessibilityValue={{ min: 0, max: total, now: lesson.learned + lesson.reviewed }}
        >
          <View style={[s.progressFill, { width: `${Math.round(progressFill * 100)}%` }]} />
        </View>
        <Text style={s.progressLabel}>
          {t(reviewing ? "lesson.review_of" : "lesson.step_of", { current: currentNumber, total })}
        </Text>
      </View>
      <View style={s.audioRow}>
        <Pressable
          accessibilityRole="switch"
          accessibilityState={{ checked: audio.sound }}
          accessibilityLabel={t("lesson.sound")}
          onPress={audio.toggleSound}
          style={s.audioControl}
        >
          <Icon
            name={audio.sound ? "volume-medium-outline" : "volume-mute-outline"}
            size={19}
            color={theme.textSecondary}
          />
          <Text style={s.progressLabel}>{t("lesson.sound")}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="switch"
          accessibilityState={{ checked: audio.voice }}
          accessibilityLabel={t("lesson.voice_feedback")}
          onPress={audio.toggleVoice}
          style={s.audioControl}
        >
          <Icon
            name="chatbubble-ellipses-outline"
            size={19}
            color={audio.voice ? theme.primary : theme.textTertiary}
          />
          <Text style={s.progressLabel}>{t("lesson.voice_feedback")}</Text>
        </Pressable>
      </View>
      <ScrollView
        contentContainerStyle={[s.body, quiz ? s.bodyQuiz : null]}
        keyboardShouldPersistTaps="handled"
      >
        {lesson.loadError ? (
          <StateView
            compact
            variant="error"
            title={t("projects.load_failed")}
            onRetry={retryLoad}
          />
        ) : null}
        {empty ? (
          <StateView
            variant="empty"
            icon="book-outline"
            title={t("lesson.chapter_empty")}
            onRetry={retryLoad}
          />
        ) : null}
        {complete ? (
          <LessonCompleteCard learned={lesson.learned} reviewed={lesson.reviewed} onBack={back} />
        ) : null}
        {step?.kind === "teach" ? (
          <VocabCard
            card={step.card}
            language={language}
            onSpeak={() => audio.speak(step.card.word, language)}
          />
        ) : null}
        {quiz ? (
          <>
            <Text style={s.question}>{quiz.question}</Text>
            {quiz.contextSentence ? (
              <Text style={s.contextSentence}>{quiz.contextSentence}</Text>
            ) : null}
            <LessonQuizCards
              choices={quiz.quiz.choices}
              correctLetter={quiz.quiz.correct}
              selectedLetter={answer?.letter}
              disabled={saving || answer?.status === "failed"}
              onSelect={submitLetter}
            />
            {answer ? (
              <View
                style={[
                  s.feedback,
                  { backgroundColor: answer.correct ? theme.successLight : theme.dangerLight },
                ]}
                accessibilityLiveRegion="polite"
              >
                <View style={s.feedbackTitle}>
                  <Icon
                    name={answer.correct ? "checkmark-circle" : "refresh-circle"}
                    size={24}
                    color={answer.correct ? theme.success : theme.danger}
                  />
                  <Text style={s.feedbackHeading}>
                    {t(answer.correct ? "lesson.correct" : "lesson.try_again")}
                  </Text>
                </View>
                <Text style={s.feedbackText}>{quiz.explanation}</Text>
              </View>
            ) : null}
          </>
        ) : null}
        {!step && !empty && !complete && !lesson.loadError ? (
          <ActionShimmer label={t("lesson.loading")} color={theme.primary} />
        ) : null}
      </ScrollView>
      {step ? (
        <View style={s.footer}>
          {error ? (
            <>
              <Text style={s.error} accessibilityLiveRegion="polite">
                {error}
              </Text>
              <Button title={t("common.retry")} onPress={lesson.retryAnswer} />
            </>
          ) : canAdvance ? (
            <Button
              title={t("lesson.continue")}
              onPress={() => {
                audio.stop();
                continueLesson();
              }}
              loading={saving}
              disabled={saving}
              style={s.nextBtn}
            />
          ) : saving ? (
            <ActionShimmer label={t("lesson.saving")} color={theme.primary} />
          ) : null}
        </View>
      ) : null}
    </SafeAreaView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    contextSentence: { ...Type.body, fontSize: 18, lineHeight: 28, color: theme.textSecondary },
    audioRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      justifyContent: "flex-end",
      paddingHorizontal: Space.lg,
      gap: Space.md,
    },
    audioControl: { flexDirection: "row", alignItems: "center", gap: Space.xs, minHeight: 44 },
    feedback: { padding: Space.md, borderRadius: Radius.lg, gap: Space.sm },
    feedbackTitle: { flexDirection: "row", gap: Space.sm, alignItems: "center" },
    feedbackHeading: { ...Type.body, fontWeight: "700", color: theme.text },
    feedbackText: { ...Type.body, color: theme.text, lineHeight: 26 },
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
