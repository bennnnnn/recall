import { useEffect, useState, type RefObject } from "react";
import type { View } from "react-native";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useProjectActions } from "@/features/learning/hooks/useProjectActions";
import { getSessionGeneration } from "@/lib/auth";
import { type Learning } from "@/lib/api";
import { isShareCancelled } from "@/lib/exportPdf";
import { exportProjectAsPdf, projectHasExportableItems } from "@/features/learning/model/exportProjectPdf";
import {
  dailyGoalPickerOptions,
  formatDailyGoalShort,
  resolveDailyGoal,
} from "@/features/learning/model/dailyGoals";
import { useProjectMutationLock } from "@/features/learning/model/projectMutationLock";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { alert } from "@/ui/overlay/dialogs";
import { Menu } from "@/ui/overlay/Menu";

type Props = {
  project: Learning;
  isCurrent: () => boolean;
  visible: boolean;
  /** The header ⋮ button. */
  anchorRef: RefObject<View | null>;
  onClose: () => void;
};

/** Lesson map ⋮: words per day (a choice menu) and Export PDF. */
export function LessonMapOverflowMenu({ project, isCurrent, visible, anchorRef, onClose }: Props) {
  const { token } = useAuth();
  const { t } = useTranslation();
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
    feedback?.info(t("chat.status.preparing"), { icon: "file-text" });
    try {
      const detail = await getExportProject(project.id);
      if (session !== getSessionGeneration() || !isCurrent()) return;
      if (!projectHasExportableItems(detail)) {
        feedback?.dismiss();
        void alert({
          title: t("projects.export_pdf_empty_title"),
          message: t("projects.export_pdf_empty_body"),
        });
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
      feedback?.dismiss();
    } catch (error) {
      if (!isCurrent() || isShareCancelled(error)) {
        feedback?.dismiss();
        return;
      }
      reportRecoverableError(feedback, t("projects.export_pdf_failed"));
    } finally {
      release();
    }
  };

  return (
    <>
      <Menu
        visible={visible}
        onClose={onClose}
        anchorRef={anchorRef}
        testID="lesson-map-menu"
        items={[
          {
            key: "goal",
            icon: "target",
            label: t("settings.learning.words_label"),
            trailing: formatDailyGoalShort(localGoal),
            disabled: mutations.pending(`goal:${project.id}`),
            onPress: () => {
              if (isCurrent()) setGoalOpen(true);
            },
          },
          {
            key: "export",
            icon: "file-text",
            label: t("settings.learning.export_pdf"),
            disabled: mutations.pending("export"),
            onPress: () => void exportPdf(),
          },
        ]}
      />
      <Menu
        visible={goalOpen}
        onClose={() => setGoalOpen(false)}
        anchorRef={anchorRef}
        selectable
        title={t("settings.learning.words_label")}
        testID="lesson-goal-menu"
        items={dailyGoalPickerOptions("language", t).map((option) => ({
          key: option.key,
          label: option.label,
          selected: option.key === String(localGoal),
          onPress: () => {
            const nextGoal = Number(option.key);
            if (Number.isFinite(nextGoal) && nextGoal !== localGoal) void saveDailyGoal(nextGoal);
          },
        }))}
      />
    </>
  );
}
