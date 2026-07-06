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
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { api, type Project } from "@/lib/api";
import {
  dailyGoalPickerOptions,
  formatDailyGoalLabel,
  resolveDailyGoal,
} from "@/lib/dailyGoals";
import { isLanguageProject } from "@/lib/languageLevels";
import { isTriviaProject } from "@/lib/projectUi";
import { useTheme } from "@/lib/theme";

type PickerTarget = {
  project: Project;
  kind: "language" | "trivia";
};

export default function LearningSettingsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [pickerTarget, setPickerTarget] = useState<PickerTarget | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const rows = await api.listProjects(token);
      setProjects(rows.filter((p) => !p.archived));
    } catch {
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const languageProject = projects.find((p) => isLanguageProject(p.kind));
  const triviaProject = projects.find((p) => isTriviaProject(p.kind));

  const saveDailyGoal = async (project: Project, nextGoal: number) => {
    if (!token || saving) return;
    setSaving(true);
    try {
      const updated = await api.updateProject(token, project.id, { daily_goal: nextGoal });
      setProjects((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
    } catch {
      Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      setSaving(false);
    }
  };

  if (!token) return <Redirect href="/login" />;

  if (loading && projects.length === 0) {
    return (
      <View style={s.center}>
        <StateView variant="loading" />
      </View>
    );
  }

  const hasLearningProjects = languageProject != null || triviaProject != null;

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
                  title={t("settings.learning.words_label")}
                  value={formatDailyGoalLabel(
                    resolveDailyGoal(languageProject.daily_goal),
                    "language",
                    t,
                  )}
                  onPress={() =>
                    setPickerTarget({ project: languageProject, kind: "language" })
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
                value={formatDailyGoalLabel(
                  resolveDailyGoal(triviaProject.daily_goal),
                  "trivia",
                  t,
                )}
                onPress={() => setPickerTarget({ project: triviaProject, kind: "trivia" })}
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
        title={
          pickerTarget?.kind === "trivia"
            ? t("settings.learning.questions_picker_title")
            : t("settings.learning.words_picker_title")
        }
        options={
          pickerTarget ? dailyGoalPickerOptions(pickerTarget.kind, t) : []
        }
        selectedKey={
          pickerTarget
            ? String(resolveDailyGoal(pickerTarget.project.daily_goal))
            : String(resolveDailyGoal(null))
        }
        onClose={() => setPickerTarget(null)}
        onSelect={(key) => {
          if (!pickerTarget) return;
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
