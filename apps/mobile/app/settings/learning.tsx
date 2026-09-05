import { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, Text, View } from "react-native";
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
import { getSessionGeneration } from "@/lib/auth";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useProjectMutationLock } from "@/lib/projects/projectMutationLock";
import { type Project } from "@/lib/api";
import { useProjectActions } from "@/hooks/useProjectActions";
import {
  dailyGoalPickerOptions,
  formatDailyGoalShort,
  resolveDailyGoal,
} from "@/lib/projects/dailyGoals";
import { isLanguageProject } from "@/lib/languageLevels";
import { languageLabel } from "@/lib/i18n/languages";
import { exportProjectAsPdf, projectHasExportableItems } from "@/lib/exportProjectPdf";
import { isShareCancelled } from "@/lib/exportPdf";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function LearningSettingsScreen() {
  const owner = useAccountViewOwner();
  return <LearningSettingsView key={owner.key} owner={owner} />;
}

function LearningSettingsView({ owner }: { owner: ReturnType<typeof useAccountViewOwner> }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const router = useRouter();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const { projects: allProjects, loading, error, refresh, setProjects } = useProjects();
  const { updateProject, getExportProject } = useProjectActions();
  const feedback = useActionFeedbackOptional();

  const session = getSessionGeneration();
  const mutations = useProjectMutationLock();
  const [openPicker, setOpenPicker] = useState<string | null>(null);

  const projects = useMemo(() => allProjects.filter((p) => !p.archived), [allProjects]);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: true });
    }, [refresh]),
  );

  const languageProjects = projects.filter((p) => isLanguageProject(p.kind));

  const saveDailyGoal = async (project: Project, nextGoal: number) => {
    if (!token || !owner.isCurrent()) return;
    const release = mutations.begin(`goal:${project.id}`);
    if (!release) return;
    const patchGoal = (goal: Project["daily_goal"]) =>
      setProjects((prev) =>
        prev.map((row) => (row.id === project.id ? { ...row, daily_goal: goal } : row)),
      );
    patchGoal(nextGoal);
    try {
      const updated = await updateProject(project.id, { daily_goal: nextGoal });
      if (session !== getSessionGeneration()) return;
      patchGoal(updated.daily_goal);
      void refresh({ silent: true, force: true, afterPending: true });
    } catch {
      if (session !== getSessionGeneration()) return;
      setProjects((prev) =>
        prev.map((row) =>
          row.id === project.id && row.daily_goal === nextGoal
            ? { ...row, daily_goal: project.daily_goal }
            : row,
        ),
      );
      void refresh({ silent: true, force: true, afterPending: true });
      if (owner.isCurrent()) reportRecoverableError(feedback, t("settings.learning.save_failed"));
    } finally {
      release();
    }
  };

  const exportPdf = async (project: Project) => {
    if (!token || !owner.isCurrent()) return;
    const release = mutations.begin("export");
    if (!release) return;
    try {
      const detail = await getExportProject(project.id);
      if (!owner.isCurrent()) return;
      if (!projectHasExportableItems(detail)) {
        Alert.alert(t("projects.export_pdf_empty_title"), t("projects.export_pdf_empty_body"));
        return;
      }
      await exportProjectAsPdf(
        detail,
        {
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
        },
        owner.isCurrent,
      );
    } catch (error) {
      if (!owner.isCurrent() || isShareCancelled(error)) return;
      reportRecoverableError(feedback, t("projects.export_pdf_failed"));
    } finally {
      release();
    }
  };

  if (!token) return <Redirect href="/login" />;

  const togglePicker = (id: string) => {
    if (!owner.isCurrent()) return;
    setOpenPicker((cur) => (cur === id ? null : id));
  };

  return (
    <View style={s.root}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
      >
        {error ? (
          <StateView
            variant="error"
            compact
            title={t("projects.load_failed")}
            onRetry={() => {
              if (owner.isCurrent()) void refresh({ force: true, afterPending: true });
            }}
            retryLabel={t("common.retry")}
          />
        ) : null}
        {loading && languageProjects.length === 0 && !error ? <ActivityIndicator /> : null}
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
                    icon="book-outline"
                    title={t("settings.learning.words_label")}
                    value={formatDailyGoalShort(resolveDailyGoal(languageProject.daily_goal))}
                    options={dailyGoalPickerOptions("language", t)}
                    selectedKey={String(resolveDailyGoal(languageProject.daily_goal))}
                    expanded={openPicker === `${languageProject.id}-daily`}
                    busy={mutations.pending(`goal:${languageProject.id}`)}
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
                </SettingsGroup>
              );
            })}
          </>
        ) : !loading && !error ? (
          <StateView
            variant="empty"
            compact
            icon="school-outline"
            title={t("settings.learning.empty")}
            onRetry={() => {
              if (owner.isCurrent()) router.push("/projects");
            }}
            retryLabel={t("settings.learning.create")}
          />
        ) : null}
      </ScrollView>
    </View>
  );
}
