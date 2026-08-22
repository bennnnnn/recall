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
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { LearningProjectCard } from "@/components/projects/LearningProjectCard";
import { StepPicker } from "@/components/projects/StepPicker";
import { type LanguageLevel } from "@/lib/api";
import { useProjectActions } from "@/hooks/useProjectActions";
import {
  DEFAULT_VOCAB_DAILY_GOAL,
  formatDailyGoalShort,
  resolveDailyGoal,
  VOCAB_DAILY_GOALS,
  type VocabDailyGoal,
} from "@/lib/projects/dailyGoals";
import { LEARNING_LANGUAGES } from "@/lib/i18n/languages";
import { LANGUAGE_LEVELS, levelLabelT } from "@/lib/languageLevels";
import { findLanguageProject } from "@/lib/projects/languageProject";
import { openLearningLesson } from "@/lib/lessonLaunch";
import { lessonMapPath } from "@/lib/projects/chapterAccess";
import {
  buildLanguageOnboardingPrompt,
} from "@/lib/projects/projectChat";
import {
  canAddLearningProject,
  languageProjectTitle,
  type CreateStep,
} from "@/lib/projects/projectCreateFlow";
import { prefetchProjectDetails } from "@/lib/cache/projectDetailCache";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

function kindIcon(kind: string): IoniconName {
  if (kind === "language" || kind === "vocabulary") return "language-outline";
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
  const [kind, setKind] = useState<"language" | null>(null);
  const [targetLanguage, setTargetLanguage] = useState("en");
  const [level, setLevel] = useState<LanguageLevel>("level1");
  const [dailyGoal, setDailyGoal] = useState<VocabDailyGoal>(DEFAULT_VOCAB_DAILY_GOAL);
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
    setDailyGoal(DEFAULT_VOCAB_DAILY_GOAL);
    setCreating(false);
  }, []);

  const openCreate = useCallback(() => {
    resetCreate();
    setKind("language");
    setCreateStep("language");
  }, [resetCreate]);

  if (!token) return <Redirect href="/login" />;

  const selectTargetLanguage = (code: string) => {
    const existing = findLanguageProject(projects, code);
    if (existing) {
      resetCreate();
      router.push(lessonMapPath(existing.id));
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
      openLearningLesson(router, {
        projectId: project.id,
        prompt: buildLanguageOnboardingPrompt(title, level, dailyGoal, targetLanguage),
        quizLanguage: targetLanguage,
        quizVariant: "vocab",
      });
    } catch {
      feedback?.error(t("projects.create_failed"));
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  };

  const renderCreateSteps = () => {
    if (!createStep) return null;

    return (
      <>
        {createStep === "language" ? (
          <>
            <Text style={s.createLabel}>{t("projects.language_pick_label")}</Text>
            <Text style={s.stepHint}>{t("projects.language_pick_hint")}</Text>
            <View style={s.subjectList}>
              {LEARNING_LANGUAGES.map((item) => {
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

        {createStep === "daily" ? (
          <StepPicker
            label={t("projects.daily_goal_label")}
            hint={t("projects.daily_goal_hint")}
            options={VOCAB_DAILY_GOALS.map((item) => ({
              key: String(item),
              value: item,
              label: t("projects.daily_goal_words", { count: item }),
            }))}
            isSelected={(value) => value === dailyGoal}
            onSelect={setDailyGoal}
            backLabel={t("projects.back")}
            onBack={() => setCreateStep("level")}
            continueLabel={t("projects.create")}
            onContinue={() => void handleCreateLanguage()}
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
            const dailyValue = formatDailyGoalShort(resolveDailyGoal(project.daily_goal));
            return (
              <LearningProjectCard
                project={project}
                icon={kindIcon(project.kind)}
                levelLabel={levelLabelT(project.level, t)}
                dailyLabel={dailyValue}
                onOpen={() => router.push(lessonMapPath(project.id))}
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
