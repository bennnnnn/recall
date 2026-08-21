import { useCallback, useMemo, useRef, useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { StateView } from "@/components/StateView";
import { TriviaTopicsPickerModal } from "@/components/projects/TriviaTopicsPickerModal";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useProjects } from "@/contexts/ProjectsContext";
import { type LanguageLevel, type Project } from "@/lib/api";
import { useProjectActions } from "@/hooks/useProjectActions";
import {
  dailyGoalPickerOptions,
  formatDailyGoalShort,
  resolveDailyGoal,
} from "@/lib/projects/dailyGoals";
import { isLanguageProject, levelLabelT, levelPickerOptions } from "@/lib/languageLevels";
import { languageLabel } from "@/lib/i18n/languages";
import { languageProjectTitle } from "@/lib/projects/projectCreateFlow";
import { isTriviaProject } from "@/lib/projects/projectUi";
import {
  encodeTriviaTopics,
  parseTriviaTopics,
  triviaDifficultyLabel,
  triviaDifficultyPickerOptions,
  type TriviaTopicId,
} from "@/lib/projects/triviaTopics";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

function mergeProjectRow(prev: Project[], updated: Project): Project[] {
  return prev.map((row) =>
    row.id === updated.id ? { ...updated, stats: row.stats ?? updated.stats } : row,
  );
}

export default function LearningSettingsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const router = useRouter();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const { projects: allProjects, refresh, setProjects } = useProjects();
  const { updateProject } = useProjectActions();
  const feedback = useActionFeedbackOptional();

  const [saving, setSaving] = useState(false);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const savingRef = useRef(false);
  const [openPicker, setOpenPicker] = useState<string | null>(null);
  const [topicsProject, setTopicsProject] = useState<Project | null>(null);
  const [topicsDraft, setTopicsDraft] = useState<TriviaTopicId[]>([]);

  const projects = useMemo(
    () => allProjects.filter((p) => !p.archived),
    [allProjects],
  );

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: true });
    }, [refresh]),
  );

  const languageProjects = projects.filter((p) => isLanguageProject(p.kind));
  const triviaProject = projects.find((p) => isTriviaProject(p.kind));

  const saveDailyGoal = async (project: Project, nextGoal: number) => {
    if (!token || savingRef.current) return;
    savingRef.current = true;
    setSavingKey(`${project.id}-daily`);
    setSaving(true);
    try {
      const updated = await updateProject(project.id, { daily_goal: nextGoal });
      setProjects((prev) => mergeProjectRow(prev, updated));
      void refresh({ silent: true, force: true });
    } catch {
      if (feedback) feedback.error(t("settings.learning.save_failed"));
      else Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      savingRef.current = false;
      setSaving(false);
      setSavingKey(null);
    }
  };

  const saveLevel = async (
    project: Project,
    level: LanguageLevel,
    kind: "language" | "trivia",
  ) => {
    if (!token || savingRef.current) return;
    savingRef.current = true;
    setSavingKey(`${project.id}-level`);
    setSaving(true);
    try {
      const patch =
        kind === "language"
          ? { level, title: languageProjectTitle(level, project.target_language) }
          : { level };
      const updated = await updateProject(project.id, patch);
      setProjects((prev) => mergeProjectRow(prev, updated));
      void refresh({ silent: true, force: true });
    } catch {
      if (feedback) feedback.error(t("settings.learning.save_failed"));
      else Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      savingRef.current = false;
      setSaving(false);
      setSavingKey(null);
    }
  };

  const saveTopics = async () => {
    if (!token || !topicsProject || savingRef.current || topicsDraft.length === 0) return;
    savingRef.current = true;
    setSavingKey(`${topicsProject.id}-topics`);
    setSaving(true);
    try {
      const updated = await updateProject(topicsProject.id, {
        description: encodeTriviaTopics(topicsDraft),
      });
      setProjects((prev) => mergeProjectRow(prev, updated));
      void refresh({ silent: true, force: true });
      setTopicsProject(null);
    } catch {
      if (feedback) feedback.error(t("settings.learning.save_failed"));
      else Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      savingRef.current = false;
      setSaving(false);
      setSavingKey(null);
    }
  };

  const toggleTopicsDraft = (topicId: TriviaTopicId) => {
    setTopicsDraft((prev) => {
      if (prev.includes(topicId)) {
        const next = prev.filter((id) => id !== topicId);
        return next.length > 0 ? next : prev;
      }
      return [...prev, topicId];
    });
  };

  const openTopicsPicker = (project: Project) => {
    const topicIds = parseTriviaTopics(project.description);
    setTopicsDraft(
      topicIds.length > 0 ? (topicIds as TriviaTopicId[]) : ["history", "science"],
    );
    setTopicsProject(project);
  };

  if (!token) return <Redirect href="/login" />;

  const hasLearningProjects = languageProjects.length > 0 || triviaProject != null;

  const togglePicker = (id: string) => {
    setOpenPicker((cur) => (cur === id ? null : id));
  };

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        {hasLearningProjects ? (
          <>
            <Text style={s.sectionHint}>{t("settings.learning.hint")}</Text>
            {languageProjects.map((languageProject) => (
              <SettingsGroup
                key={languageProject.id}
                label={languageLabel(languageProject.target_language)}
                styles={s}
              >
                <SettingsInlinePicker
                  icon="school-outline"
                  title={t("settings.learning.level_label")}
                  value={levelLabelT(languageProject.level, t)}
                  options={levelPickerOptions(t)}
                  selectedKey={languageProject.level}
                  expanded={openPicker === `${languageProject.id}-level`}
                  disabled={saving}
                  busy={savingKey === `${languageProject.id}-level`}
                  onToggle={() => togglePicker(`${languageProject.id}-level`)}
                  onSelect={(key) =>
                    void saveLevel(languageProject, key as LanguageLevel, "language")
                  }
                  styles={s}
                  theme={theme}
                />
                <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
                <SettingsInlinePicker
                  icon="book-outline"
                  title={t("settings.learning.words_label")}
                  value={formatDailyGoalShort(resolveDailyGoal(languageProject.daily_goal))}
                  options={dailyGoalPickerOptions("language", t)}
                  selectedKey={String(resolveDailyGoal(languageProject.daily_goal))}
                  expanded={openPicker === `${languageProject.id}-daily`}
                  disabled={saving}
                  busy={savingKey === `${languageProject.id}-daily`}
                  onToggle={() => togglePicker(`${languageProject.id}-daily`)}
                  onSelect={(key) => {
                    const nextGoal = Number(key);
                    if (!Number.isFinite(nextGoal)) return;
                    void saveDailyGoal(languageProject, nextGoal);
                  }}
                  styles={s}
                  theme={theme}
                />
              </SettingsGroup>
            ))}

            {triviaProject ? (
              <SettingsGroup label={t("settings.learning.trivia_section")} styles={s}>
                <SettingsInlinePicker
                  icon="speedometer-outline"
                  title={t("settings.learning.difficulty_label")}
                  value={triviaDifficultyLabel(triviaProject.level, t)}
                  options={triviaDifficultyPickerOptions(t)}
                  selectedKey={triviaProject.level}
                  expanded={openPicker === `${triviaProject.id}-level`}
                  disabled={saving}
                  busy={savingKey === `${triviaProject.id}-level`}
                  onToggle={() => togglePicker(`${triviaProject.id}-level`)}
                  onSelect={(key) =>
                    void saveLevel(triviaProject, key as LanguageLevel, "trivia")
                  }
                  styles={s}
                  theme={theme}
                />
                <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
                <SettingsInlinePicker
                  icon="help-circle-outline"
                  title={t("settings.learning.questions_label")}
                  value={formatDailyGoalShort(resolveDailyGoal(triviaProject.daily_goal))}
                  options={dailyGoalPickerOptions("trivia", t)}
                  selectedKey={String(resolveDailyGoal(triviaProject.daily_goal))}
                  expanded={openPicker === `${triviaProject.id}-daily`}
                  disabled={saving}
                  busy={savingKey === `${triviaProject.id}-daily`}
                  onToggle={() => togglePicker(`${triviaProject.id}-daily`)}
                  onSelect={(key) => {
                    const nextGoal = Number(key);
                    if (!Number.isFinite(nextGoal)) return;
                    void saveDailyGoal(triviaProject, nextGoal);
                  }}
                  styles={s}
                  theme={theme}
                />
                <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
                <SettingsLinkRow
                  icon="list-outline"
                  title={t("settings.learning.topics_label")}
                  value={t("projects.list.topics_value", {
                    count: parseTriviaTopics(triviaProject.description).length,
                  })}
                  onPress={() => openTopicsPicker(triviaProject)}
                  styles={s}
                  theme={theme}
                />
              </SettingsGroup>
            ) : null}
          </>
        ) : (
          <StateView
            variant="empty"
            compact
            icon="school-outline"
            title={t("settings.learning.empty")}
            onRetry={() => router.push("/projects")}
            retryLabel={t("settings.learning.create")}
          />
        )}
      </ScrollView>

      <TriviaTopicsPickerModal
        visible={topicsProject != null}
        selected={topicsDraft}
        saving={saving}
        onClose={() => setTopicsProject(null)}
        onDone={() => void saveTopics()}
        onToggle={toggleTopicsDraft}
      />
    </View>
  );
}
