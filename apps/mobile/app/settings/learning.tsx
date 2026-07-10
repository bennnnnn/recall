import { useCallback, useMemo, useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";
import { Redirect, useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

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
import { useTheme } from "@/lib/theme";

type PickerTarget =
  | { mode: "daily"; project: Project; kind: "language" | "trivia" }
  | { mode: "level"; project: Project };

export default function LearningSettingsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const { projects: allProjects, refresh, setProjects } = useProjects();

  const [saving, setSaving] = useState(false);
  const [pickerTarget, setPickerTarget] = useState<PickerTarget | null>(null);

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
      setProjects((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
      invalidateProjectDetail(project.id);
    } catch {
      Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      setSaving(false);
    }
  };

  const saveLevel = async (project: Project, level: LanguageLevel) => {
    if (!token || saving) return;
    setSaving(true);
    try {
      const updated = await api.updateProject(token, project.id, {
        level,
        title: englishProjectTitle(level, t),
      });
      setProjects((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
      invalidateProjectDetail(project.id);
    } catch {
      Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      setSaving(false);
    }
  };

  if (!token) return <Redirect href="/login" />;

  const hasLearningProjects = languageProject != null || triviaProject != null;

  const pickerTitle =
    pickerTarget?.mode === "level"
      ? t("settings.learning.level_picker_title")
      : pickerTarget?.kind === "trivia"
        ? t("settings.learning.questions_picker_title")
        : t("settings.learning.words_picker_title");

  const pickerOptions =
    pickerTarget?.mode === "level"
      ? levelPickerOptions()
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
          <SettingsGroup label={t("settings.learning.section")} styles={s}>
            {languageProject ? (
              <>
                <SettingsLinkRow
                  title={t("settings.learning.level_label")}
                  value={levelLabel(languageProject.level)}
                  onPress={() => setPickerTarget({ mode: "level", project: languageProject })}
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
                {triviaProject ? <View style={s.menuSeparator} /> : null}
              </>
            ) : null}
            {triviaProject ? (
              <SettingsLinkRow
                title={t("settings.learning.questions_label")}
                value={formatDailyGoalShort(resolveDailyGoal(triviaProject.daily_goal))}
                onPress={() =>
                  setPickerTarget({ mode: "daily", project: triviaProject, kind: "trivia" })
                }
                styles={s}
                theme={theme}
              />
            ) : null}
          </SettingsGroup>
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
            void saveLevel(pickerTarget.project, key as LanguageLevel);
            return;
          }
          const nextGoal = Number(key);
          if (!Number.isFinite(nextGoal)) return;
          void saveDailyGoal(pickerTarget.project, nextGoal);
        }}
        disabled={saving}
        styles={s}
        theme={theme}
      />
    </View>
  );
}
