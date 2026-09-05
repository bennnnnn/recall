import { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { StepPicker } from "@/components/projects/StepPicker";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useProjects } from "@/contexts/ProjectsContext";
import { useProjectActions } from "@/hooks/useProjectActions";
import { getSessionGeneration } from "@/lib/auth";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useProjectMutationLock } from "@/lib/projects/projectMutationLock";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { LEARNING_LANGUAGES } from "@/lib/i18n/languages";
import {
  DEFAULT_VOCAB_DAILY_GOAL,
  VOCAB_DAILY_GOALS,
  type VocabDailyGoal,
} from "@/lib/projects/dailyGoals";
import { findLanguageProject } from "@/lib/projects/languageProject";
import { lessonMapPath } from "@/lib/projects/chapterAccess";
import {
  CREATE_DEFAULT_LEVEL,
  canAddLearningProject,
  createStepProgress,
  languageClassTitle,
  type CreateStep,
} from "@/lib/projects/projectCreateFlow";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function CreateLearningScreen() {
  const owner = useAccountViewOwner();
  return <CreateLearningView key={owner.key} owner={owner} />;
}

function CreateLearningView({ owner }: { owner: ReturnType<typeof useAccountViewOwner> }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { projects, setProjects, refresh } = useProjects();
  const { createProject } = useProjectActions();
  const feedback = useActionFeedbackOptional();

  const [step, setStep] = useState<CreateStep>("language");
  const [targetLanguage, setTargetLanguage] = useState("en");
  const [dailyGoal, setDailyGoal] = useState<VocabDailyGoal>(DEFAULT_VOCAB_DAILY_GOAL);
  const session = getSessionGeneration();
  const mutations = useProjectMutationLock();
  const creating = mutations.pending(`create:${targetLanguage}`);

  const { current, total } = createStepProgress(step, "language");

  if (!token) return <Redirect href="/login" />;
  if (!creating && !canAddLearningProject(projects)) return <Redirect href="/projects" />;

  const selectTargetLanguage = (code: string) => {
    if (!owner.isCurrent()) return;
    const existing = findLanguageProject(projects, code);
    if (existing) {
      router.replace(lessonMapPath(existing.id));
      return;
    }
    setTargetLanguage(code);
    setStep("daily");
  };

  const handleCreateLanguage = async () => {
    if (!token || !owner.isCurrent()) return;
    const release = mutations.begin(`create:${targetLanguage}`);
    if (!release) return;

    const title = languageClassTitle(targetLanguage);
    const optimisticId = `local-project-${session}-${targetLanguage}`;
    const now = new Date().toISOString();
    const optimistic = {
      id: optimisticId,
      title,
      description: "",
      kind: "language" as const,
      target_language: targetLanguage,
      native_language: null,
      level: CREATE_DEFAULT_LEVEL,
      daily_goal: dailyGoal,
      archived: false,
      created_at: now,
      updated_at: now,
    };

    setProjects((prev) => [optimistic, ...prev]);
    try {
      const project = await createProject({
        title,
        description: "",
        kind: "language",
        level: CREATE_DEFAULT_LEVEL,
        target_language: targetLanguage,
        daily_goal: dailyGoal,
      });
      if (session !== getSessionGeneration()) return;
      setProjects((prev) => [
        project,
        ...prev.filter((row) => row.id !== optimisticId && row.id !== project.id),
      ]);
      if (owner.isCurrent()) router.replace(lessonMapPath(project.id));
    } catch {
      if (session !== getSessionGeneration()) return;
      setProjects((prev) => prev.filter((row) => row.id !== optimisticId));
      void refresh({ silent: true, force: true, afterPending: true });
      if (owner.isCurrent()) reportRecoverableError(feedback, t("projects.create_failed"));
    } finally {
      release();
    }
  };

  return (
    <ScrollView
      style={s.root}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      keyboardShouldPersistTaps="handled"
    >
      <View
        style={s.progressTrack}
        accessibilityRole="progressbar"
        accessibilityValue={{ min: 1, max: total, now: current }}
        accessibilityLabel={t("projects.create_step", { current, total })}
      >
        <View style={[s.progressFill, { width: `${Math.round((current / total) * 100)}%` }]} />
      </View>
      <Text style={s.progressLabel}>{t("projects.create_step", { current, total })}</Text>

      {step === "language" ? (
        <View style={s.card}>
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
                  accessibilityRole="button"
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
        </View>
      ) : (
        <View style={s.card}>
          <StepPicker
            label={t("projects.daily_goal_label")}
            hint={t("projects.daily_goal_hint")}
            options={VOCAB_DAILY_GOALS.map((item) => ({
              key: String(item),
              value: item,
              label: t("projects.daily_goal_words", { count: item }),
            }))}
            isSelected={(value) => value === dailyGoal}
            onSelect={(value) => {
              if (owner.isCurrent()) setDailyGoal(value);
            }}
            backLabel={t("projects.back")}
            onBack={() => {
              if (owner.isCurrent()) setStep("language");
            }}
            continueLabel={t("projects.create")}
            onContinue={() => void handleCreateLanguage()}
            continueBusy={creating}
          />
        </View>
      )}
    </ScrollView>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    content: { padding: Space.md, gap: Space.sm },
    progressTrack: {
      height: 4,
      borderRadius: 2,
      backgroundColor: C.border,
      overflow: "hidden",
    },
    progressFill: {
      height: "100%",
      backgroundColor: C.primary,
      borderRadius: 2,
    },
    progressLabel: {
      ...Type.caption,
      color: C.textTertiary,
    },
    card: { gap: 10 },
    createLabel: { ...Type.title, color: C.text },
    stepHint: {
      ...Type.label,
      fontWeight: "400",
      color: C.textSecondary,
      marginBottom: Space.xxs,
    },
    subjectList: { gap: Space.xs },
    subjectRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingVertical: 14,
      paddingHorizontal: Space.sm,
      borderRadius: 14,
      backgroundColor: C.surfaceAlt,
      borderWidth: 1,
      borderColor: C.border,
    },
    subjectMain: { flex: 1, gap: 2 },
    subjectText: { ...Type.body, fontWeight: "600", color: C.text },
    subjectHint: { ...Type.caption, fontWeight: "400", color: C.textSecondary },
  });
}
