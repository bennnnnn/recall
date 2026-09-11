import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Alert, View } from "react-native";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsInlinePicker,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useProjectActions } from "@/hooks/useProjectActions";
import { getSessionGeneration } from "@/lib/auth";
import { type Learning } from "@/lib/api";
import { isShareCancelled } from "@/lib/exportPdf";
import { exportProjectAsPdf, projectHasExportableItems } from "@/lib/exportProjectPdf";
import {
  dailyGoalPickerOptions,
  formatDailyGoalShort,
  resolveDailyGoal,
} from "@/lib/projects/dailyGoals";
import { useProjectMutationLock } from "@/lib/projects/projectMutationLock";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { useTheme } from "@/lib/theme";

type Props = {
  project: Learning;
  isCurrent: () => boolean;
};

export function LessonMapOverflowMenu({ project, isCurrent }: Props) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const { updateProject, getExportProject } = useProjectActions();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const mutations = useProjectMutationLock();
  const [goalOpen, setGoalOpen] = useState(false);
  const [localGoal, setLocalGoal] = useState(resolveDailyGoal(project.daily_goal));

  useEffect(() => {
    setLocalGoal(resolveDailyGoal(project.daily_goal));
  }, [project.daily_goal]);

  const saveDailyGoal = async (nextGoal: number) => {
    if (!token || !isCurrent()) return;
    const release = mutations.begin(`goal:${project.id}`);
    if (!release) return;
    const previous = localGoal;
    setLocalGoal(nextGoal);
    try {
      const updated = await updateProject(project.id, { daily_goal: nextGoal });
      if (session !== getSessionGeneration()) return;
      setLocalGoal(resolveDailyGoal(updated.daily_goal));
    } catch {
      if (session !== getSessionGeneration()) return;
      setLocalGoal(previous);
      if (isCurrent()) reportRecoverableError(feedback, t("settings.learning.save_failed"));
    } finally {
      release();
    }
  };

  const exportPdf = async () => {
    if (!token || !isCurrent()) return;
    const release = mutations.begin("export");
    if (!release) return;
    try {
      const detail = await getExportProject(project.id);
      if (session !== getSessionGeneration() || !isCurrent()) return;
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
        isCurrent,
      );
    } catch (error) {
      if (!isCurrent() || isShareCancelled(error)) return;
      reportRecoverableError(feedback, t("projects.export_pdf_failed"));
    } finally {
      release();
    }
  };

  return (
    <SettingsGroup styles={s}>
      <SettingsInlinePicker
        title={t("settings.learning.words_label")}
        value={formatDailyGoalShort(localGoal)}
        options={dailyGoalPickerOptions("language", t)}
        selectedKey={String(localGoal)}
        expanded={goalOpen}
        busy={mutations.pending(`goal:${project.id}`)}
        onToggle={() => {
          if (isCurrent()) setGoalOpen((open) => !open);
        }}
        onSelect={(key) => {
          const nextGoal = Number(key);
          if (!Number.isFinite(nextGoal)) return;
          void saveDailyGoal(nextGoal);
        }}
        styles={s}
        theme={theme}
      />
      <View style={s.menuSeparator} />
      <SettingsLinkRow
        title={t("settings.learning.export_pdf")}
        onPress={() => void exportPdf()}
        styles={s}
        theme={theme}
      />
      {mutations.pending("export") ? (
        <View style={s.menuRow}>
          <ActivityIndicator color={theme.primary} />
        </View>
      ) : null}
    </SettingsGroup>
  );
}
