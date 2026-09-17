import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { api, type Automation, type AutomationFrequency, type AutomationStatus } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/client";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

/** List + create for the Automations tab. Automations are a low-traffic,
 * single-surface list (no Home chip, no cross-screen cache need per
 * chat-ux-bans #10) — a plain fetch-on-focus hook is enough; no global
 * context like Todos/Projects. */
export function useAutomationsList(isCurrent: () => boolean) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token) return;
      if (!opts?.silent) setLoading(true);
      try {
        const rows = await api.listAutomations(token);
        if (!isCurrent()) return;
        setAutomations(rows);
        setError(false);
      } catch {
        if (isCurrent()) setError(true);
      } finally {
        if (isCurrent()) setLoading(false);
      }
    },
    [token, isCurrent],
  );

  useEffect(() => {
    void refresh();
    // Only on mount / token change — screens re-trigger via useFocusEffect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const create = useCallback(
    async (
      params: { prompt: string; frequency: AutomationFrequency; nextRunAt: string },
      onCreated: (automation: Automation) => void,
    ) => {
      if (!token || creating) return;
      setCreating(true);
      try {
        const created = await api.createAutomation(token, params);
        if (!isCurrent()) return;
        setAutomations((rows) => [created, ...rows]);
        onCreated(created);
      } catch (err) {
        if (!isCurrent()) return;
        if (err instanceof ApiRequestError && err.status === 422) {
          reportRecoverableError(feedback, t("automations.max_active_reached"));
        } else {
          reportRecoverableError(feedback, t("automations.create_failed"));
        }
      } finally {
        if (isCurrent()) setCreating(false);
      }
    },
    [token, creating, isCurrent, feedback, t],
  );

  /** Edit / pause-resume from the list's long-press menu, so quick actions
   * don't require navigating into the detail screen first. */
  const update = useCallback(
    async (
      id: string,
      patch: Partial<{
        prompt: string;
        frequency: AutomationFrequency;
        next_run_at: string;
        status: Extract<AutomationStatus, "active" | "paused">;
      }>,
    ) => {
      if (!token) return;
      try {
        const updated = await api.updateAutomation(token, id, patch);
        if (!isCurrent()) return;
        setAutomations((rows) => rows.map((row) => (row.id === id ? updated : row)));
      } catch {
        if (isCurrent()) reportRecoverableError(feedback, t("automations.update_failed"));
      }
    },
    [token, isCurrent, feedback, t],
  );

  const remove = useCallback(
    async (id: string) => {
      if (!token) return;
      try {
        await api.deleteAutomation(token, id);
        if (!isCurrent()) return;
        setAutomations((rows) => rows.filter((row) => row.id !== id));
      } catch {
        if (isCurrent()) reportRecoverableError(feedback, t("automations.delete_failed"));
      }
    },
    [token, isCurrent, feedback, t],
  );

  return { automations, loading, error, creating, refresh, create, update, remove };
}
