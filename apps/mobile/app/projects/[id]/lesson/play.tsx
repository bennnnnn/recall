import { useEffect, useMemo, useRef, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";
import { ActionShimmer } from "@/components/ActionShimmer";
import { Button } from "@/components/Button";
import { StateView } from "@/components/StateView";
import { VocabCard } from "@/components/VocabCard";
import { LessonCompleteCard } from "@/components/projects/LessonCompleteCard";
import { LessonGradeSheet } from "@/components/projects/LessonGradeSheet";
import { LessonOptionsSheet } from "@/components/projects/LessonOptionsSheet";
import { LessonPlayHeader } from "@/components/projects/LessonPlayHeader";
import { LessonQuizCards } from "@/components/projects/LessonQuizCards";
import { LessonStepTransition } from "@/components/projects/LessonStepTransition";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useLessonFeedback } from "@/hooks/useLessonFeedback";
import { useLessonPrefs } from "@/hooks/useLessonPrefs";
import { useLessonSession } from "@/hooks/useLessonSession";
import { isLanguageProject } from "@/lib/languageLevels";
import { lessonMapPath } from "@/lib/projects/chapterAccess";
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
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const projectId = typeof id === "string" ? id : "";
  const s = useMemo(() => makeStyles(theme), [theme]);
  const lesson = useLessonSession(projectId, isCurrent);
  const { prefs, updatePrefs, textScale } = useLessonPrefs();
  const [menuOpen, setMenuOpen] = useState(false);
  const {
    project,
    step,
    answer,
    error,
    empty,
    complete,
    reviewing,
    chapter,
    currentNumber,
    total,
    progressFill,
    canAdvance,
    submitLetter,
    continueLesson,
    groupDone,
  } = lesson;
  const audio = useLessonFeedback(answer, isCurrent, prefs.effectSound);
  const speakRef = useRef(audio.speak);
  speakRef.current = audio.speak;
  const celebrateRef = useRef(audio.celebrate);
  celebrateRef.current = audio.celebrate;
  const language = project && isLanguageProject(project.kind) ? project.target_language : "en";
  const teachWord = step?.kind === "teach" ? step.card.word : null;
  useEffect(() => {
    if (!prefs.readWords || !teachWord) return;
    speakRef.current(teachWord, language);
  }, [language, prefs.readWords, teachWord]);
  useEffect(() => {
    if (complete && groupDone) celebrateRef.current();
  }, [complete, groupDone]);
  if (!token) return <Redirect href="/login" />;
  if (!projectId) return <Redirect href="/projects" />;
  const quiz = step && step.kind !== "teach" ? step : null;
  const paneKey = complete ? "complete" : step ? `${step.itemId}:${step.kind}` : null;
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
    <SafeAreaView style={s.safe} edges={["top"]}>
      <LessonPlayHeader
        current={currentNumber}
        total={total}
        fill={progressFill}
        reviewing={reviewing}
        onClose={back}
        onOpenMenu={() => setMenuOpen(true)}
      />
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
        {paneKey ? (
          <LessonStepTransition stepKey={paneKey} fill={Boolean(quiz || complete)}>
            {complete ? (
              <LessonCompleteCard
                title={chapter}
                reviewing={reviewing}
                groupDone={groupDone}
              />
            ) : null}
            {step?.kind === "teach" ? (
              <VocabCard
                card={step.card}
                language={language}
                textScale={textScale}
                onSpeak={() => audio.speak(step.card.word, language)}
              />
            ) : null}
            {quiz ? (
              <>
                <Text
                  style={[s.question, { fontSize: 24 * textScale, lineHeight: 32 * textScale }]}
                >
                  {quiz.question}
                </Text>
                {quiz.contextSentence ? (
                  <Text
                    style={[
                      s.contextSentence,
                      { fontSize: 20 * textScale, lineHeight: 30 * textScale },
                    ]}
                  >
                    {quiz.contextSentence}
                  </Text>
                ) : null}
                <LessonQuizCards
                  choices={quiz.quiz.choices}
                  correctLetter={quiz.quiz.correct}
                  selectedLetter={reviewing ? quiz.quiz.correct : answer?.letter}
                  disabled={reviewing || answer?.status === "failed"}
                  textScale={textScale}
                  onSelect={submitLetter}
                />
              </>
            ) : null}
          </LessonStepTransition>
        ) : null}
        {!step && !empty && !complete && !lesson.loadError ? (
          <ActionShimmer label={t("lesson.loading")} color={theme.primary} />
        ) : null}
      </ScrollView>
      {(step?.kind === "teach" || reviewing) && (error || canAdvance) ? (
        <View style={[s.footer, { paddingBottom: Space.lg + insets.bottom }]}>
          {error ? (
            <>
              <Text style={s.error} accessibilityLiveRegion="polite">
                {error}
              </Text>
              <Button title={t("common.retry")} onPress={lesson.retryAnswer} />
            </>
          ) : (
            <Button
              title={t("lesson.continue")}
              onPress={() => {
                audio.stop();
                void continueLesson();
              }}
              style={s.nextBtn}
            />
          )}
        </View>
      ) : null}
      {quiz && answer && !reviewing ? (
        <LessonGradeSheet
          correct={answer.correct}
          explanation={quiz.explanation}
          error={error}
          showContinue={canAdvance}
          textScale={textScale}
          onContinue={() => {
            audio.stop();
            void continueLesson();
          }}
          onRetry={lesson.retryAnswer}
        />
      ) : null}
      <LessonOptionsSheet
        visible={menuOpen}
        prefs={prefs}
        onClose={() => setMenuOpen(false)}
        onChange={updatePrefs}
      />
    </SafeAreaView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    safe: { flex: 1, backgroundColor: theme.bg },
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
    contextSentence: { ...Type.body, color: theme.textSecondary },
    question: {
      fontSize: 24,
      fontWeight: "700",
      color: theme.text,
      lineHeight: 32,
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
