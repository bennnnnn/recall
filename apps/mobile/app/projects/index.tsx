import { useCallback, useMemo, useState } from "react";
import {
  Alert,
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
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { LearningProjectCard } from "@/components/projects/LearningProjectCard";
import { StepPicker } from "@/components/projects/StepPicker";
import { api, type LanguageLevel, type Project, type ProjectKind } from "@/lib/api";
import {
  dailyGoalPickerOptions,
  DEFAULT_VOCAB_DAILY_GOAL,
  formatDailyGoalShort,
  resolveDailyGoal,
  VOCAB_DAILY_GOALS,
  type VocabDailyGoal,
} from "@/lib/dailyGoals";
import { isLanguageProject, LANGUAGE_LEVELS, levelLabel } from "@/lib/languageLevels";
import { findLanguageProject } from "@/lib/languageProject";
import { queueChatLaunch } from "@/lib/chatLaunch";
import {
  buildEnglishOnboardingPrompt,
  buildProjectAskPromptFromProject,
  buildProjectReviewPrompt,
  buildTriviaOnboardingPrompt,
  projectDetailForChat,
} from "@/lib/projectChat";
import {
  canAddLearningProject,
  englishProjectTitle,
  triviaProjectTitle,
  type CreateStep,
} from "@/lib/projectCreateFlow";
import { findTriviaProject } from "@/lib/triviaProject";
import { isTriviaProject } from "@/lib/projectUi";
import { invalidateProjectDetail, prefetchProjectDetails } from "@/lib/projectDetailCache";
import {
  encodeTriviaTopics,
  formatTriviaTopicLabels,
  formatTriviaTopicsChip,
  TRIVIA_TOPICS,
  TRIVIA_DIFFICULTY_LEVELS,
  triviaDifficultyLabel,
  parseTriviaTopics,
  type TriviaTopicId,
} from "@/lib/triviaTopics";
import { Theme, useTheme } from "@/lib/theme";

const SUBJECTS: ProjectKind[] = ["language", "trivia"];

function kindIcon(kind: ProjectKind): keyof typeof Ionicons.glyphMap {
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
  const visibleProjects = projects;
  const showAddLearning = useMemo(
    () => canAddLearningProject(projects),
    [projects],
  );

  const [createStep, setCreateStep] = useState<CreateStep | null>(null);
  const [kind, setKind] = useState<ProjectKind | null>(null);
  const [level, setLevel] = useState<LanguageLevel>("level1");
  const [triviaLevel, setTriviaLevel] = useState<LanguageLevel>("level3");
  const [dailyGoal, setDailyGoal] = useState<VocabDailyGoal>(DEFAULT_VOCAB_DAILY_GOAL);
  const [triviaTopics, setTriviaTopics] = useState<TriviaTopicId[]>(["history", "science"]);
  const [creating, setCreating] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);

  useFocusEffect(
    useCallback(() => {
      // Force after quiz sessions so Today x/y isn't stuck on a 20s stale window.
      void refresh({ silent: true, force: true });
    }, [refresh]),
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

  if (!token) return <Redirect href="/login" />;

  const resetCreate = () => {
    setCreateStep(null);
    setKind(null);
    setLevel("level1");
    setTriviaLevel("level3");
    setDailyGoal(DEFAULT_VOCAB_DAILY_GOAL);
    setTriviaTopics(["history", "science"]);
    setCreating(false);
  };

  const openCreate = () => {
    resetCreate();
    setCreateStep("subject");
  };

  const startStudyForProject = (project: Project) => {
    const isTrivia = isTriviaProject(project.kind);
    const isLang = isLanguageProject(project.kind);
    const variant = isTrivia ? "trivia" : isLang ? "vocab" : undefined;
    invalidateProjectDetail(project.id);
    queueChatLaunch(
      buildProjectAskPromptFromProject(project, t),
      project.id,
      isLang ? "en" : undefined,
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
      isLang ? "en" : undefined,
      variant,
      "chat",
    );
    router.replace("/");
  };

  const selectSubject = (next: ProjectKind) => {
    if (next === "language") {
      const existing = findLanguageProject(projects, "en");
      if (existing) {
        resetCreate();
        router.push(`/projects/${existing.id}`);
        return;
      }
      setKind(next);
      setCreateStep("level");
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

  const handleCreateEnglish = async () => {
    if (!token || kind !== "language" || creating) return;

    const title = englishProjectTitle(level, t);

    setCreating(true);
    try {
      const project = await api.createProject(token, {
        title,
        description: "",
        kind: "language",
        level,
        target_language: "en",
        daily_goal: dailyGoal,
      });
      resetCreate();
      setProjects((prev) => [project, ...prev]);
      queueChatLaunch(buildEnglishOnboardingPrompt(title, level, dailyGoal), project.id, "en", "vocab", "chat");
      router.replace("/");
    } catch {
      Alert.alert(t("common.error"), t("projects.create_failed"));
    } finally {
      setCreating(false);
    }
  };

  const handleCreateTrivia = async () => {
    if (!token || kind !== "trivia" || creating || triviaTopics.length === 0) return;

    const title = triviaProjectTitle(t);
    const description = encodeTriviaTopics(triviaTopics);
    const topicLabels = formatTriviaTopicLabels(triviaTopics, t);

    setCreating(true);
    try {
      const project = await api.createProject(token, {
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
      Alert.alert(t("common.error"), t("projects.create_failed"));
    } finally {
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
                const existingEnglish =
                  item === "language" ? findLanguageProject(projects, "en") : undefined;
                const existingTrivia = item === "trivia" ? findTriviaProject(projects) : undefined;
                const continueHint =
                  existingEnglish && item === "language"
                    ? t("projects.language_continue")
                    : existingTrivia && item === "trivia"
                      ? t("projects.trivia_continue")
                      : null;
                return (
                  <Pressable
                    key={item}
                    style={s.subjectRow}
                    onPress={() => selectSubject(item)}
                  >
                    <View style={s.subjectIcon}>
                      <Ionicons name={kindIcon(item)} size={22} color={C.primary} />
                    </View>
                    <View style={s.subjectMain}>
                      <Text style={s.subjectText}>{t(`projects.kind.${item}`)}</Text>
                      {continueHint ? (
                        <Text style={s.subjectHint}>{continueHint}</Text>
                      ) : null}
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={C.textTertiary} />
                  </Pressable>
                );
              })}
            </View>
          </>
        ) : null}

        {createStep === "level" ? (
          <StepPicker
            label={t("projects.level_label")}
            hint={t("projects.level_hint")}
            options={LANGUAGE_LEVELS.map((item) => ({
              key: item,
              value: item,
              label: levelLabel(item),
            }))}
            isSelected={(value) => value === level}
            onSelect={setLevel}
            backLabel={t("projects.back")}
            onBack={() => setCreateStep("subject")}
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
              void (kind === "trivia" ? handleCreateTrivia() : handleCreateEnglish())
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
        <ScrollView
          contentContainerStyle={s.content}
          keyboardShouldPersistTaps="handled"
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
        >
          {showAddLearning ? (
            <Pressable style={s.newProjectBtn} onPress={openCreate}>
              <Ionicons name="add-circle-outline" size={22} color={C.primary} />
              <Text style={s.newProjectText}>{t("projects.add_learning")}</Text>
            </Pressable>
          ) : null}

          {!error && visibleProjects.length === 0 ? (
            <StateView
              variant="empty"
              title={t("projects.empty_title")}
              message={t("projects.empty_body")}
            />
          ) : null}

          {error ? (
            <StateView
              variant="error"
              title={t("common.error")}
              onRetry={() => void refresh()}
              retryLabel={t("common.retry")}
            />
          ) : (
            visibleProjects.map((project) => {
              const isTrivia = isTriviaProject(project.kind);
              const levelValue = isTrivia
                ? triviaDifficultyLabel(project.level, t)
                : levelLabel(project.level);
              const dailyValue = formatDailyGoalShort(resolveDailyGoal(project.daily_goal));
              const topicIds = parseTriviaTopics(project.description);
              const topicsChip = isTrivia ? formatTriviaTopicsChip(topicIds, t) : undefined;
              return (
                <LearningProjectCard
                  key={project.id}
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
            })
          )}
        </ScrollView>
      )}

      <Modal
        visible={createStep !== null}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={resetCreate}
      >
        <KeyboardAvoidingView
          style={[s.modalRoot, { paddingTop: insets.top }]}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <View style={s.modalHeader}>
            <Pressable style={s.modalClose} onPress={resetCreate} hitSlop={8}>
              <Ionicons name="close" size={26} color={C.textSecondary} />
            </Pressable>
            <Text style={s.modalHeaderTitle}>{t("projects.add_learning")}</Text>
            <View style={s.modalClose} />
          </View>
          <ScrollView
            contentContainerStyle={[s.modalContent, { paddingBottom: insets.bottom + 24 }]}
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
    content: { padding: 16, gap: 12, paddingBottom: 32 },
    newProjectBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 14,
      paddingHorizontal: 14,
      borderRadius: 14,
      backgroundColor: C.primaryLight,
    },
    newProjectText: { fontSize: 16, fontWeight: "700", color: C.primary },
    modalRoot: { flex: 1, backgroundColor: C.bg },
    modalHeader: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: C.border,
    },
    modalClose: { width: 40, alignItems: "center", justifyContent: "center" },
    modalHeaderTitle: {
      flex: 1,
      textAlign: "center",
      fontSize: 17,
      fontWeight: "700",
      color: C.text,
    },
    modalContent: { padding: 16 },
    createCard: { gap: 10 },
    createLabel: { fontSize: 20, fontWeight: "700", color: C.text },
    stepHint: { fontSize: 14, color: C.textSecondary, marginBottom: 4 },
    subjectList: { gap: 8 },
    subjectRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 12,
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
    subjectText: { fontSize: 16, fontWeight: "600", color: C.text },
    subjectMain: { flex: 1, gap: 2 },
    subjectHint: { fontSize: 13, color: C.textSecondary },
    subjectRowMuted: { opacity: 0.65 },
    subjectTextActive: { color: C.primaryDark },
    input: {
      backgroundColor: C.surface,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: C.border,
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 16,
      color: C.text,
    },
    inputMultiline: { minHeight: 88, textAlignVertical: "top" },
    empty: {
      textAlign: "center",
      color: C.textSecondary,
      fontSize: 15,
      paddingVertical: 24,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingVertical: 14,
      paddingHorizontal: 12,
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
    rowTitle: { fontSize: 16, fontWeight: "700", color: C.text },
    rowMeta: { fontSize: 13, color: C.textSecondary },
    topicsDone: { fontSize: 16, fontWeight: "700", color: C.primary },
    topicsDoneDisabled: { opacity: 0.4 },
    fieldLabel: {
      fontSize: 14,
      fontWeight: "600",
      color: C.textSecondary,
      marginTop: 4,
    },
  });
}
