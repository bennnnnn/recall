import { useCallback, useMemo, useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";
import { Redirect, useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { TriviaTopicsPickerModal } from "@/components/projects/TriviaTopicsPickerModal";
import { SettingsPickerModal } from "@/components/settings/SettingsPickerModal";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { api, type LanguageLevel, type Project } from "@/lib/api";
import {
  dailyGoalPickerOptions,
  formatDailyGoalShort,
  resolveDailyGoal,
} from "@/lib/dailyGoals";
import { isLanguageProject, levelLabel, levelPickerOptions } from "@/lib/languageLevels";
import { invalidateProjectDetail } from "@/lib/projectDetailCache";
import { englishProjectTitle } from "@/lib/projectCreateFlow";
import { isTriviaProject } from "@/lib/projectUi";
import {
  encodeTriviaTopics,
  parseTriviaTopics,
  triviaDifficultyLabel,
  triviaDifficultyPickerOptions,
  type TriviaTopicId,
} from "@/lib/triviaTopics";
import { useTheme } from "@/lib/theme";

function mergeProjectRow(prev: Project[], updated: Project): Project[] {
  return prev.map((row) =>
    row.id === updated.id ? { ...updated, stats: row.stats ?? updated.stats } : row,
  );
}

type PickerTarget =
  | { mode: "daily"; project: Project; kind: "language" | "trivia" }
  | { mode: "level"; project: Project; kind: "language" | "trivia" };

export default function LearningSettingsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const { projects: allProjects, refresh, setProjects } = useProjects();

  const [saving, setSaving] = useState(false);
  const [pickerTarget, setPickerTarget] = useState<PickerTarget | null>(null);
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

  const languageProject = projects.find((p) => isLanguageProject(p.kind));
  const triviaProject = projects.find((p) => isTriviaProject(p.kind));

  const saveDailyGoal = async (project: Project, nextGoal: number) => {
    if (!token || saving) return;
    setSaving(true);
    try {
      const updated = await api.updateProject(token, project.id, { daily_goal: nextGoal });
      setProjects((prev) => mergeProjectRow(prev, updated));
      invalidateProjectDetail(project.id);
      void refresh({ silent: true, force: true });
    } catch {
      Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      setSaving(false);
    }
  };

  const saveLevel = async (
    project: Project,
    level: LanguageLevel,
    kind: "language" | "trivia",
  ) => {
    if (!token || saving) return;
    setSaving(true);
    try {
      const patch =
        kind === "language"
          ? { level, title: englishProjectTitle(level, t) }
          : { level };
      const updated = await api.updateProject(token, project.id, patch);
      setProjects((prev) => mergeProjectRow(prev, updated));
      invalidateProjectDetail(project.id);
      void refresh({ silent: true, force: true });
    } catch {
      Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      setSaving(false);
    }
  };

  const saveTopics = async () => {
    if (!token || !topicsProject || saving || topicsDraft.length === 0) return;
    setSaving(true);
    try {
      const updated = await api.updateProject(token, topicsProject.id, {
        description: encodeTriviaTopics(topicsDraft),
      });
      setProjects((prev) => mergeProjectRow(prev, updated));
      invalidateProjectDetail(topicsProject.id);
      void refresh({ silent: true, force: true });
      setTopicsProject(null);
    } catch {
      Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      setSaving(false);
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

  const hasLearningProjects = languageProject != null || triviaProject != null;

  const pickerTitle =
    pickerTarget?.mode === "level"
      ? pickerTarget.kind === "trivia"
        ? t("settings.learning.difficulty_picker_title")
        : t("settings.learning.level_picker_title")
      : pickerTarget?.kind === "trivia"
        ? t("settings.learning.questions_picker_title")
        : t("settings.learning.words_picker_title");

  const pickerOptions =
    pickerTarget?.mode === "level"
      ? pickerTarget.kind === "trivia"
        ? triviaDifficultyPickerOptions(t)
        : levelPickerOptions()
      : pickerTarget
        ? dailyGoalPickerOptions(pickerTarget.kind, t)
        : [];

  const pickerSelectedKey =
    pickerTarget?.mode === "level"
      ? pickerTarget.project.level
      : pickerTarget
        ? String(resolveDailyGoal(pickerTarget.project.daily_goal))
        : String(resolveDailyGoal(null));

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 24 }]}
      >
        <Text style={s.sectionHint}>{t("settings.learning.hint")}</Text>

        {hasLearningProjects ? (
          <>
            {languageProject ? (
              <SettingsGroup label={t("settings.learning.english_section")} styles={s}>
                <SettingsLinkRow
                  title={t("settings.learning.level_label")}
                  value={levelLabel(languageProject.level)}
                  onPress={() =>
                    setPickerTarget({ mode: "level", project: languageProject, kind: "language" })
                  }
                  styles={s}
                  theme={theme}
                />
                <View style={s.menuSeparator} />
                <SettingsLinkRow
                  title={t("settings.learning.words_label")}
                  value={formatDailyGoalShort(resolveDailyGoal(languageProject.daily_goal))}
                  onPress={() =>
                    setPickerTarget({
                      mode: "daily",
                      project: languageProject,
                      kind: "language",
                    })
                  }
                  styles={s}
                  theme={theme}
                />
              </SettingsGroup>
            ) : null}

            {triviaProject ? (
              <SettingsGroup label={t("settings.learning.trivia_section")} styles={s}>
                <SettingsLinkRow
                  title={t("settings.learning.difficulty_label")}
                  value={triviaDifficultyLabel(triviaProject.level, t)}
                  onPress={() =>
                    setPickerTarget({ mode: "level", project: triviaProject, kind: "trivia" })
                  }
                  styles={s}
                  theme={theme}
                />
                <View style={s.menuSeparator} />
                <SettingsLinkRow
                  title={t("settings.learning.questions_label")}
                  value={formatDailyGoalShort(resolveDailyGoal(triviaProject.daily_goal))}
                  onPress={() =>
                    setPickerTarget({ mode: "daily", project: triviaProject, kind: "trivia" })
                  }
                  styles={s}
                  theme={theme}
                />
                <View style={s.menuSeparator} />
                <SettingsLinkRow
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
          <Text style={s.sectionHint}>{t("settings.learning.empty")}</Text>
        )}
      </ScrollView>

      <SettingsPickerModal
        visible={pickerTarget != null}
        title={pickerTitle}
        options={pickerOptions}
        selectedKey={pickerSelectedKey}
        onClose={() => setPickerTarget(null)}
        onSelect={(key) => {
          if (!pickerTarget) return;
          if (pickerTarget.mode === "level") {
            void saveLevel(pickerTarget.project, key as LanguageLevel, pickerTarget.kind);
            setPickerTarget(null);
            return;
          }
          const nextGoal = Number(key);
          if (!Number.isFinite(nextGoal)) return;
          void saveDailyGoal(pickerTarget.project, nextGoal);
          setPickerTarget(null);
        }}
        disabled={saving}
        styles={s}
        theme={theme}
      />

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
