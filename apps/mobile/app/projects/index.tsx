import { useCallback, useMemo, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Icon } from "@/components/Icon";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { type IoniconName } from "@/lib/icons";
import { useProjects } from "@/contexts/ProjectsContext";
import { useHome } from "@/contexts/HomeContext";
import { AddFab } from "@/components/AddFab";
import { Button } from "@/components/Button";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { LearningProjectCard } from "@/components/projects/LearningProjectCard";
import { StepPicker } from "@/components/projects/StepPicker";
import { type LanguageLevel, type Project, type ProjectKind } from "@/lib/api";
import { useProjectActions } from "@/hooks/useProjectActions";
import {
  DEFAULT_VOCAB_DAILY_GOAL,
  formatDailyGoalShort,
  resolveDailyGoal,
  VOCAB_DAILY_GOALS,
  type VocabDailyGoal,
} from "@/lib/projects/dailyGoals";
import { LANGUAGES } from "@/lib/i18n/languages";
import { isLanguageProject, LANGUAGE_LEVELS, levelLabelT } from "@/lib/languageLevels";
import { findLanguageProject } from "@/lib/projects/languageProject";
import { queueChatLaunch } from "@/lib/chatLaunch";
import {
  buildLanguageOnboardingPrompt,
  buildProjectAskPromptFromProject,
  buildProjectReviewPrompt,
  buildTriviaOnboardingPrompt,
  projectDetailForChat,
} from "@/lib/projects/projectChat";
import {
  canAddLearningProject,
  languageProjectTitle,
  triviaProjectTitle,
  type CreateStep,
} from "@/lib/projects/projectCreateFlow";
import { findTriviaProject } from "@/lib/projects/triviaProject";
import { isTriviaProject } from "@/lib/projects/projectUi";
import { invalidateProjectDetail, prefetchProjectDetails } from "@/lib/cache/projectDetailCache";
import {
  encodeTriviaTopics,
  formatTriviaTopicLabels,
  formatTriviaTopicsChip,
  TRIVIA_TOPICS,
  TRIVIA_DIFFICULTY_LEVELS,
  triviaDifficultyLabel,
  parseTriviaTopics,
  type TriviaTopicId,
} from "@/lib/projects/triviaTopics";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const SUBJECTS: ProjectKind[] = ["language", "trivia"];

function kindIcon(kind: ProjectKind): IoniconName {
  if (kind === "language" || kind === "vocabulary") return "language-outline";
  if (kind === "trivia") return "bulb-outline";
  return "folder-outline";
}

export default function ProjectsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { projects, loading, error, refresh, setProjects } = useProjects();
  const { refresh: refreshHome } = useHome();
  const { createProject } = useProjectActions();
  const feedback = useActionFeedbackOptional();
  const visibleProjects = useMemo(
    () => projects.filter((p) => !p.archived),
    [projects],
  );
  const showAddLearning = useMemo(
    () => canAddLearningProject(projects),
    [projects],
  );

  const [createStep, setCreateStep] = useState<CreateStep | null>(null);
  const [kind, setKind] = useState<ProjectKind | null>(null);
  const [targetLanguage, setTargetLanguage] = useState("en");
  const [level, setLevel] = useState<LanguageLevel>("level1");
  const [triviaLevel, setTriviaLevel] = useState<LanguageLevel>("level3");
  const [dailyGoal, setDailyGoal] = useState<VocabDailyGoal>(DEFAULT_VOCAB_DAILY_GOAL);
  const [triviaTopics, setTriviaTopics] = useState<TriviaTopicId[]>(["history", "science"]);
  const [creating, setCreating] = useState(false);
  const creatingRef = useRef(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);

  useFocusEffect(
    useCallback(() => {
      // Stale-gated. Quiz returns bust projectDetailCache; do not force /home
      // and /projects on every Learning open.
      void refresh({ silent: true });
      void refreshHome({ silent: true });
    }, [refresh, refreshHome]),
  );

  useFocusEffect(
    useCallback(() => {
      if (!token || visibleProjects.length === 0) return;
      prefetchProjectDetails(
        token,
        visibleProjects.map((p) => p.id),
      );
    }, [token, visibleProjects]),
  );

  const resetCreate = useCallback(() => {
    setCreateStep(null);
    setKind(null);
    setTargetLanguage("en");
    setLevel("level1");
    setTriviaLevel("level3");
    setDailyGoal(DEFAULT_VOCAB_DAILY_GOAL);
    setTriviaTopics(["history", "science"]);
    setCreating(false);
  }, []);

  const openCreate = useCallback(() => {
    resetCreate();
    setCreateStep("subject");
  }, [resetCreate]);

  if (!token) return <Redirect href="/login" />;

  const startStudyForProject = (project: Project) => {
    const isTrivia = isTriviaProject(project.kind);
    const isLang = isLanguageProject(project.kind);
    const variant = isTrivia ? "trivia" : isLang ? "vocab" : undefined;
    invalidateProjectDetail(project.id);
    queueChatLaunch(
      buildProjectAskPromptFromProject(project, t),
      project.id,
      isLang ? project.target_language : undefined,
      variant,
      "chat",
    );
    router.replace("/");
  };

  const startReviewForProject = (project: Project) => {
    const detail = projectDetailForChat(project);
    const isTrivia = isTriviaProject(project.kind);
    const isLang = isLanguageProject(project.kind);
    const variant = isTrivia ? "trivia" : isLang ? "vocab" : undefined;
    invalidateProjectDetail(project.id);
    queueChatLaunch(
      buildProjectReviewPrompt(detail),
      project.id,
      isLang ? project.target_language : undefined,
      variant,
      "chat",
    );
    router.replace("/");
  };

  const selectSubject = (next: ProjectKind) => {
    if (next === "language") {
      setKind(next);
      setCreateStep("language");
      return;
    }
    if (next === "trivia") {
      const existing = findTriviaProject(projects);
      if (existing) {
        resetCreate();
        router.push(`/projects/${existing.id}`);
        return;
      }
      setKind(next);
      setCreateStep("topics");
    }
  };

  const selectTargetLanguage = (code: string) => {
    const existing = findLanguageProject(projects, code);
    if (existing) {
      resetCreate();
      router.push(`/projects/${existing.id}`);
      return;
    }
    setTargetLanguage(code);
    setCreateStep("level");
  };

  const handleCreateLanguage = async () => {
    if (!token || kind !== "language" || creatingRef.current) return;

    const title = languageProjectTitle(level, targetLanguage);

    creatingRef.current = true;
    setCreating(true);
    try {
      const project = await createProject({
        title,
        description: "",
        kind: "language",
        level,
        target_language: targetLanguage,
        daily_goal: dailyGoal,
      });
      resetCreate();
      setProjects((prev) => [project, ...prev]);
      queueChatLaunch(
        buildLanguageOnboardingPrompt(title, level, dailyGoal, targetLanguage),
        project.id,
        targetLanguage,
        "vocab",
        "chat",
      );
      router.replace("/");
    } catch {
      feedback?.error(t("projects.create_failed"));
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  };

  const handleCreateTrivia = async () => {
    if (
      !token ||
      kind !== "trivia" ||
      creatingRef.current ||
      triviaTopics.length === 0
    )
      return;

    const title = triviaProjectTitle(t);
    const description = encodeTriviaTopics(triviaTopics);
    const topicLabels = formatTriviaTopicLabels(triviaTopics, t);

    creatingRef.current = true;
    setCreating(true);
    try {
      const project = await createProject({
        title,
        description,
        kind: "trivia",
        level: triviaLevel,
        target_language: "en",
        daily_goal: dailyGoal,
      });
      resetCreate();
      setProjects((prev) => [project, ...prev]);
      queueChatLaunch(
        buildTriviaOnboardingPrompt(topicLabels, dailyGoal, triviaLevel),
        project.id,
        undefined,
        "trivia",
        "chat",
      );
      router.replace("/");
    } catch {
      feedback?.error(t("projects.create_failed"));
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  };

  const toggleTriviaTopic = (topicId: TriviaTopicId) => {
    setTriviaTopics((prev) => {
      if (prev.includes(topicId)) {
        const next = prev.filter((id) => id !== topicId);
        return next.length > 0 ? next : prev;
      }
      return [...prev, topicId];
    });
  };

  const renderCreateSteps = () => {
    if (!createStep) return null;

    return (
      <>
        {createStep === "subject" ? (
          <>
            <Text style={s.createLabel}>{t("projects.what_to_learn")}</Text>
            <View style={s.subjectList}>
              {SUBJECTS.map((item) => {
                const existingTrivia = item === "trivia" ? findTriviaProject(projects) : undefined;
                const continueHint =
                  existingTrivia && item === "trivia" ? t("projects.trivia_continue") : null;
                return (
                  <Pressable
                    key={item}
                    style={s.subjectRow}
                    onPress={() => selectSubject(item)}
                  >
                    <View style={s.subjectIcon}>
                      <Icon name={kindIcon(item)} size={22} color={C.primary} />
                    </View>
                    <View style={s.subjectMain}>
                      <Text style={s.subjectText}>{t(`projects.kind.${item}`)}</Text>
                      {continueHint ? (
                        <Text style={s.subjectHint}>{continueHint}</Text>
                      ) : null}
                    </View>
                    <Icon name="chevron-forward" size={18} color={C.textTertiary} />
                  </Pressable>
                );
              })}
            </View>
          </>
        ) : null}

        {createStep === "language" ? (
          <>
            <Text style={s.createLabel}>{t("projects.language_pick_label")}</Text>
            <Text style={s.stepHint}>{t("projects.language_pick_hint")}</Text>
            <View style={s.subjectList}>
              {LANGUAGES.map((item) => {
                const existing = findLanguageProject(projects, item.code);
                return (
                  <Pressable
                    key={item.code}
                    style={s.subjectRow}
                    onPress={() => selectTargetLanguage(item.code)}
                  >
                    <View style={s.subjectMain}>
                      <Text style={s.subjectText}>{item.label}</Text>
                      {existing ? (
                        <Text style={s.subjectHint}>{t("projects.language_continue")}</Text>
                      ) : null}
                    </View>
                    <Icon name="chevron-forward" size={18} color={C.textTertiary} />
                  </Pressable>
                );
              })}
            </View>
            <Button
              title={t("projects.back")}
              onPress={() => setCreateStep("subject")}
              variant="outline"
            />
          </>
        ) : null}

        {createStep === "level" ? (
          <StepPicker
            label={t("projects.level_label")}
            hint={t("projects.level_hint")}
            options={LANGUAGE_LEVELS.map((item) => ({
              key: item,
              value: item,
              label: levelLabelT(item, t),
            }))}
            isSelected={(value) => value === level}
            onSelect={setLevel}
            backLabel={t("projects.back")}
            onBack={() => setCreateStep("language")}
            continueLabel={t("common.continue")}
            onContinue={() => setCreateStep("daily")}
          />
        ) : null}

        {createStep === "topics" ? (
          <StepPicker
            label={t("projects.trivia.topics_label")}
            hint={t("projects.trivia.topics_hint")}
            options={TRIVIA_TOPICS.map((topic) => ({
              key: topic.id,
              value: topic.id,
              label: t(topic.labelKey),
            }))}
            isSelected={(value) => triviaTopics.includes(value)}
            onSelect={toggleTriviaTopic}
            backLabel={t("projects.back")}
            onBack={() => setCreateStep("subject")}
            continueLabel={t("common.continue")}
            onContinue={() => setCreateStep("trivia_level")}
          />
        ) : null}

        {createStep === "trivia_level" ? (
          <StepPicker
            label={t("projects.trivia.difficulty_label")}
            hint={t("projects.trivia.difficulty_hint")}
            options={TRIVIA_DIFFICULTY_LEVELS.map((item) => ({
              key: item.level,
              value: item.level,
              label: t(item.labelKey),
            }))}
            isSelected={(value) => value === triviaLevel}
            onSelect={setTriviaLevel}
            backLabel={t("projects.back")}
            onBack={() => setCreateStep("topics")}
            continueLabel={t("common.continue")}
            onContinue={() => setCreateStep("daily")}
          />
        ) : null}

        {createStep === "daily" ? (
          <StepPicker
            label={
              kind === "trivia" ? t("projects.trivia.daily_label") : t("projects.daily_goal_label")
            }
            hint={
              kind === "trivia" ? t("projects.trivia.daily_hint") : t("projects.daily_goal_hint")
            }
            options={VOCAB_DAILY_GOALS.map((item) => ({
              key: String(item),
              value: item,
              label:
                kind === "trivia"
                  ? t("projects.trivia.daily_questions", { count: item })
                  : t("projects.daily_goal_words", { count: item }),
            }))}
            isSelected={(value) => value === dailyGoal}
            onSelect={setDailyGoal}
            backLabel={t("projects.back")}
            onBack={() => setCreateStep(kind === "trivia" ? "trivia_level" : "level")}
            continueLabel={t("projects.create")}
            onContinue={() =>
              void (kind === "trivia" ? handleCreateTrivia() : handleCreateLanguage())
            }
            continueBusy={creating}
          />
        ) : null}
      </>
    );
  };

  return (
    <View style={s.root}>
      {loading && visibleProjects.length === 0 && !error ? (
        <SkeletonList />
      ) : (
        <FlashList
          data={error ? [] : visibleProjects}
          keyExtractor={(project) => project.id}
          contentContainerStyle={s.content}
          keyboardShouldPersistTaps="handled"
          ItemSeparatorComponent={() => <View style={s.listGap} />}
          refreshControl={
            <RefreshControl
              refreshing={pullRefreshing}
              onRefresh={async () => {
                setPullRefreshing(true);
                await refresh({ silent: true, force: true });
                setPullRefreshing(false);
              }}
              tintColor={C.primary}
            />
          }
          ListHeaderComponent={
            <>
              {!error && visibleProjects.length === 0 ? (
                <StateView variant="empty" title={t("projects.empty_title")} />
              ) : null}
              {error ? (
                <StateView
                  variant="error"
                  title={t("common.error")}
                  onRetry={() => void refresh()}
                  retryLabel={t("common.retry")}
                />
              ) : null}
            </>
          }
          renderItem={({ item: project }) => {
            const isTrivia = isTriviaProject(project.kind);
            const levelValue = isTrivia
              ? triviaDifficultyLabel(project.level, t)
              : levelLabelT(project.level, t);
            const dailyValue = formatDailyGoalShort(resolveDailyGoal(project.daily_goal));
            const topicIds = parseTriviaTopics(project.description);
            const topicsChip = isTrivia ? formatTriviaTopicsChip(topicIds, t) : undefined;
            return (
              <LearningProjectCard
                project={project}
                icon={kindIcon(project.kind)}
                levelLabel={levelValue}
                dailyLabel={dailyValue}
                topicsChip={topicsChip}
                onOpen={() => router.push(`/projects/${project.id}`)}
                onStudy={() => startStudyForProject(project)}
                onReview={() => startReviewForProject(project)}
              />
            );
          }}
        />
      )}

      {showAddLearning ? (
        <AddFab
          onPress={openCreate}
          accessibilityLabel={t("projects.add_learning_a11y")}
        />
      ) : null}

      <Modal
        visible={createStep !== null}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => {
          if (!creating) resetCreate();
        }}
      >
        <KeyboardAvoidingView
          style={[s.modalRoot, { paddingTop: insets.top }]}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <View style={s.modalHeader}>
            <Pressable
              style={s.modalClose}
              onPress={resetCreate}
              disabled={creating}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel={t("common.close")}
            >
              <Icon name="close" size={26} color={C.textSecondary} />
            </Pressable>
            <Text style={s.modalHeaderTitle}>{t("projects.add_learning")}</Text>
            <View style={s.modalClose} />
          </View>
          <ScrollView
            contentContainerStyle={[s.modalContent, { paddingBottom: insets.bottom + Space.lg }]}
            keyboardShouldPersistTaps="handled"
          >
            <View style={s.createCard}>{renderCreateSteps()}</View>
          </ScrollView>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    content: { padding: Space.md, paddingBottom: 96 },
    listGap: { height: Space.sm },
    modalRoot: { flex: 1, backgroundColor: C.bg },
    modalHeader: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: Space.sm,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: C.border,
    },
    modalClose: { width: 40, alignItems: "center", justifyContent: "center" },
    modalHeaderTitle: {
      flex: 1,
      textAlign: "center",
      ...Type.navTitle,
      color: C.text,
    },
    modalContent: { padding: Space.md },
    createCard: { gap: 10 },
    createLabel: { ...Type.title, color: C.text },
    stepHint: { ...Type.label, fontWeight: "400", color: C.textSecondary, marginBottom: Space.xxs },
    subjectList: { gap: Space.xs },
    subjectRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingVertical: 14,
      paddingHorizontal: Space.sm,
      borderRadius: 14,
      backgroundColor: C.surface,
      borderWidth: 1,
      borderColor: C.border,
    },
    subjectRowActive: {
      borderColor: C.primary,
      backgroundColor: C.primaryLight,
    },
    subjectIcon: {
      width: 40,
      height: 40,
      borderRadius: 12,
      backgroundColor: C.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    subjectText: { ...Type.body, fontWeight: "600", color: C.text },
    subjectMain: { flex: 1, gap: 2 },
    subjectHint: { ...Type.caption, fontWeight: "400", color: C.textSecondary },
    subjectRowMuted: { opacity: 0.65 },
    subjectTextActive: { color: C.primaryDark },
    input: {
      backgroundColor: C.surface,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: C.border,
      paddingHorizontal: Space.sm,
      paddingVertical: 10,
      ...Type.body,
      color: C.text,
    },
    inputMultiline: { minHeight: 88, textAlignVertical: "top" },
    empty: {
      textAlign: "center",
      color: C.textSecondary,
      ...Type.secondary,
      paddingVertical: Space.lg,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingVertical: 14,
      paddingHorizontal: Space.sm,
      borderRadius: 14,
      backgroundColor: C.surface,
    },
    rowIcon: {
      width: 40,
      height: 40,
      borderRadius: 12,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    rowMain: { flex: 1, gap: 2 },
    rowTitle: { ...Type.body, fontWeight: "700", color: C.text },
    rowMeta: { ...Type.caption, fontWeight: "400", color: C.textSecondary },
    topicsDone: { ...Type.body, fontWeight: "700", color: C.primary },
    topicsDoneDisabled: { opacity: 0.4 },
    fieldLabel: {
      ...Type.label,
      color: C.textSecondary,
      marginTop: Space.xxs,
    },
  });
}
