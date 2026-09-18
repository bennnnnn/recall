import { useCallback, useEffect, useState } from "react";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import {
  api,
  type JobMatchStatus,
  type JobSearchDashboard,
  type JobSearchInput,
} from "@/lib/api";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

const EMPTY: JobSearchDashboard = { profile: null, matches: [] };

export function useJobSearch(isCurrent: () => boolean) {
  const { token } = useAuth();
  const feedback = useActionFeedbackOptional();
  const [dashboard, setDashboard] = useState<JobSearchDashboard>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token) return;
      if (!opts?.silent) setLoading(true);
      try {
        const next = await api.getJobSearch(token);
        if (!isCurrent()) return;
        setDashboard(next);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const save = useCallback(
    async (input: JobSearchInput): Promise<boolean> => {
      if (!token || busy) return false;
      setBusy(true);
      try {
        const next = await api.saveJobSearch(token, input);
        if (!isCurrent()) return false;
        setDashboard(next);
        setError(false);
        return true;
      } catch (err) {
        if (isCurrent()) {
          const message = err instanceof Error ? err.message : "Could not save your job search";
          reportRecoverableError(feedback, message);
        }
        return false;
      } finally {
        if (isCurrent()) setBusy(false);
      }
    },
    [token, busy, isCurrent, feedback],
  );

  const setSearchStatus = useCallback(
    async (status: "active" | "paused") => {
      if (!token || busy) return;
      setBusy(true);
      try {
        const next = await api.setJobSearchStatus(token, status);
        if (isCurrent()) setDashboard(next);
      } catch {
        if (isCurrent()) reportRecoverableError(feedback, "Could not update your job search");
      } finally {
        if (isCurrent()) setBusy(false);
      }
    },
    [token, busy, isCurrent, feedback],
  );

  const setMatchStatus = useCallback(
    async (id: string, status: JobMatchStatus) => {
      if (!token) return;
      const previous = dashboard;
      setDashboard((current) => ({
        ...current,
        matches: current.matches.map((match) =>
          match.id === id ? { ...match, status } : match,
        ),
      }));
      try {
        const next = await api.setJobMatchStatus(token, id, status);
        if (isCurrent()) setDashboard(next);
      } catch {
        if (!isCurrent()) return;
        setDashboard(previous);
        reportRecoverableError(feedback, "Could not update this job");
      }
    },
    [token, dashboard, isCurrent, feedback],
  );

  const runNow = useCallback(async () => {
    if (!token || busy) return;
    setBusy(true);
    try {
      const next = await api.runJobSearchNow(token);
      if (isCurrent()) setDashboard(next);
    } catch (err) {
      if (isCurrent()) {
        const message = err instanceof Error ? err.message : "Could not start the job search";
        reportRecoverableError(feedback, message);
      }
    } finally {
      if (isCurrent()) setBusy(false);
    }
  }, [token, busy, isCurrent, feedback]);

  const remove = useCallback(async (): Promise<boolean> => {
    if (!token || busy) return false;
    setBusy(true);
    try {
      await api.deleteJobSearch(token);
      if (!isCurrent()) return false;
      setDashboard(EMPTY);
      return true;
    } catch {
      if (isCurrent()) reportRecoverableError(feedback, "Could not delete your job search");
      return false;
    } finally {
      if (isCurrent()) setBusy(false);
    }
  }, [token, busy, isCurrent, feedback]);

  return {
    dashboard,
    loading,
    busy,
    error,
    refresh,
    save,
    setSearchStatus,
    setMatchStatus,
    runNow,
    remove,
  };
}
