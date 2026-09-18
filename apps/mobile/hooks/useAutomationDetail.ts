import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { api, type Automation, type AutomationFrequency } from "@/lib/api";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

/** Single automation record plus edit, pause, and delete actions.
 * Run history stays internal; the detail screen mirrors a scheduled-task
 * editor instead of opening the automation's hidden chat transcript. */
export function useAutomationDetail(automationId: string, isCurrent: () => boolean) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const [automation, setAutomation] = useState<Automation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleted, setDeleted] = useState(false);

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token || !automationId) return;
      if (!opts?.silent) setLoading(true);
      try {
        const item = await api.getAutomation(token, automationId);
        if (!isCurrent()) return;
        setAutomation(item);
        setError(false);
      } catch {
        if (isCurrent()) setError(true);
      } finally {
        if (isCurrent()) setLoading(false);
      }
    },
    [token, automationId, isCurrent],
  );

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, automationId]);

  const update = useCallback(
    async (
      patch: Partial<{
        prompt: string;
        frequency: AutomationFrequency;
        next_run_at: string;
        status: "active" | "paused";
      }>,
    ) => {
      if (!token || !automation || saving) return;
      setSaving(true);
      try {
        const updated = await api.updateAutomation(token, automation.id, patch);
        if (isCurrent()) setAutomation(updated);
      } catch {
        if (isCurrent()) reportRecoverableError(feedback, t("automations.update_failed"));
      } finally {
        if (isCurrent()) setSaving(false);
      }
    },
    [token, automation, saving, isCurrent, feedback, t],
  );

  const togglePause = useCallback(() => {
    if (!automation) return;
    void update({ status: automation.status === "paused" ? "active" : "paused" });
  }, [automation, update]);

  const remove = useCallback(
    async (onDeleted: () => void) => {
      if (!token || !automation || saving) return;
      setSaving(true);
      try {
        await api.deleteAutomation(token, automation.id);
        if (!isCurrent()) return;
        setDeleted(true);
        onDeleted();
      } catch {
        if (isCurrent()) reportRecoverableError(feedback, t("automations.delete_failed"));
      } finally {
        if (isCurrent()) setSaving(false);
      }
    },
    [token, automation, saving, isCurrent, feedback, t],
  );

  return { automation, loading, error, saving, deleted, refresh, update, togglePause, remove };
}
