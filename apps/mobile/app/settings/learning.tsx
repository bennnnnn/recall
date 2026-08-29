import { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { StateView } from "@/components/StateView";
import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
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
import {
  exportProjectAsPdf,
  projectHasExportableItems,
} from "@/lib/exportProjectPdf";
import { isShareCancelled } from "@/lib/exportPdf";
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
  const { updateProject, deleteProject, getExportProject } = useProjectActions();
  const feedback = useActionFeedbackOptional();

  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [openPicker, setOpenPicker] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);

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

  const saveDailyGoal = async (project: Project, nextGoal: number) => {
    if (!token) return;
    const key = `${project.id}-daily`;
    if (savingKey === key) return;
    setSavingKey(key);
    setProjects((prev) => mergeProjectRow(prev, { ...project, daily_goal: nextGoal }));
    try {
      const updated = await updateProject(project.id, { daily_goal: nextGoal });
      setProjects((prev) => mergeProjectRow(prev, updated));
      void refresh({ silent: true, force: true });
    } catch {
      setProjects((prev) => mergeProjectRow(prev, project));
      if (feedback) feedback.error(t("settings.learning.save_failed"));
      else Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      setSavingKey((cur) => (cur === key ? null : cur));
    }
  };

  const saveLevel = async (project: Project, level: LanguageLevel) => {
    if (!token) return;
    const key = `${project.id}-level`;
    if (savingKey === key) return;
    const draft: Project = {
      ...project,
      level,
      title: languageProjectTitle(level, project.target_language),
    };
    setSavingKey(key);
    setProjects((prev) => mergeProjectRow(prev, draft));
    try {
      const updated = await updateProject(project.id, {
        level,
        title: draft.title,
      });
      setProjects((prev) => mergeProjectRow(prev, updated));
      void refresh({ silent: true, force: true });
    } catch {
      setProjects((prev) => mergeProjectRow(prev, project));
      if (feedback) feedback.error(t("settings.learning.save_failed"));
      else Alert.alert(t("common.error"), t("settings.learning.save_failed"));
    } finally {
      setSavingKey((cur) => (cur === key ? null : cur));
    }
  };

  const confirmDelete = (project: Project) => {
    if (!token || deletingId) return;
    Alert.alert(
      t("projects.delete_title", { title: project.title }),
      t("projects.delete_body"),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: async () => {
            setDeletingId(project.id);
            try {
              await deleteProject(project.id);
              setProjects((prev) => prev.filter((p) => p.id !== project.id));
              void refresh({ silent: true, force: true });
            } catch {
              if (feedback) feedback.error(t("projects.delete_failed"));
              else Alert.alert(t("common.error"), t("projects.delete_failed"));
            } finally {
              setDeletingId(null);
            }
          },
        },
      ],
    );
  };

  const exportPdf = async (project: Project) => {
    if (!token || exportingId) return;
    setExportingId(project.id);
    try {
      const detail = await getExportProject(project.id);
      if (!projectHasExportableItems(detail)) {
        Alert.alert(
          t("projects.export_pdf_empty_title"),
          t("projects.export_pdf_empty_body"),
        );
        return;
      }
      await exportProjectAsPdf(detail, {
        mastered: t("projects.export_pdf.section_mastered"),
        learning: t("projects.export_pdf.section_learning"),
        new: t("projects.export_pdf.section_new"),
        empty: t("projects.export_pdf.empty"),
        definition: t("projects.export_pdf.definition"),
        example: t("projects.export_pdf.example"),
        topic: t("projects.export_pdf.topic"),
        summary: ({ total, mastered, learning, newCount }) =>
          t("projects.export_pdf.summary", {
            total,
            mastered,
            learning,
            new: newCount,
          }),
      });
    } catch (error) {
      if (isShareCancelled(error)) return;
      reportRecoverableError(feedback, t("projects.export_pdf_failed"));
    } finally {
      setExportingId(null);
    }
  };

  if (!token) return <Redirect href="/login" />;

  const togglePicker = (id: string) => {
    setOpenPicker((cur) => (cur === id ? null : id));
  };

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        {languageProjects.length > 0 ? (
          <>
            <Text style={s.sectionHint}>{t("settings.learning.hint")}</Text>
            {languageProjects.map((languageProject) => {
              const stats = languageProject.stats;
              const statsSummary = stats
                ? t("settings.learning.stats_summary", {
                    week: stats.added_this_week,
                    total: stats.mastered_count,
                    streak: stats.streak_days ?? 0,
                  })
                : null;
              return (
                <SettingsGroup
                  key={languageProject.id}
                  label={languageLabel(languageProject.target_language)}
                  styles={s}
                >
                  {statsSummary ? (
                    <View style={s.menuRow}>
                      <Icon name="stats-chart-outline" size={20} color={theme.textTertiary} />
                      <View style={s.rowBody}>
                        <Text style={s.rowTitle}>{statsSummary}</Text>
                      </View>
                    </View>
                  ) : null}
                  <SettingsInlinePicker
                    icon="school-outline"
                    title={t("settings.learning.level_label")}
                    value={levelLabelT(languageProject.level, t)}
                    options={levelPickerOptions(t)}
                    selectedKey={languageProject.level}
                    expanded={openPicker === `${languageProject.id}-level`}
                    busy={savingKey === `${languageProject.id}-level`}
                    onToggle={() => togglePicker(`${languageProject.id}-level`)}
                    onSelect={(key) => void saveLevel(languageProject, key as LanguageLevel)}
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
                  <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
                  <SettingsLinkRow
                    icon="document-text-outline"
                    title={t("settings.learning.export_pdf")}
                    onPress={() => void exportPdf(languageProject)}
                    styles={s}
                    theme={theme}
                  />
                  <View style={[s.menuSeparator, s.menuSeparatorWithIcon]} />
                  <Pressable
                    style={({ pressed }) => [s.menuRow, pressed && s.rowPressed]}
                    onPress={() => confirmDelete(languageProject)}
                    disabled={Boolean(deletingId)}
                    accessibilityRole="button"
                  >
                    <View style={s.rowBody}>
                      <Text style={[s.rowTitle, { color: theme.danger }]}>
                        {deletingId === languageProject.id
                          ? t("common.deleting")
                          : t("settings.learning.delete_class")}
                      </Text>
                    </View>
                    {deletingId === languageProject.id ? (
                      <ActivityIndicator size="small" color={theme.danger} />
                    ) : null}
                  </Pressable>
                </SettingsGroup>
              );
            })}
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
    </View>
  );
}
