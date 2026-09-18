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
const RUN_POLL_INTERVAL_MS = 2500;
const RUN_POLL_ATTEMPTS = 24;

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

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
    const previousRunAt = dashboard.profile?.last_run_at ?? null;
    setBusy(true);
    try {
      const started = await api.runJobSearchNow(token);
      if (!isCurrent()) return;
      setDashboard(started);
      setError(false);

      // The search runs on the durable worker after this HTTP request returns.
      // Keep the dashboard live so a user who tapped "Find jobs now" sees the
      // new matches without guessing when to pull-to-refresh.
      for (let attempt = 0; attempt < RUN_POLL_ATTEMPTS; attempt += 1) {
        await delay(RUN_POLL_INTERVAL_MS);
        if (!isCurrent()) return;
        try {
          const next = await api.getJobSearch(token);
          if (!isCurrent()) return;
          setDashboard(next);
          setError(false);
          const completedAt = next.profile?.last_run_at ?? null;
          if (completedAt && completedAt !== previousRunAt) return;
        } catch {
          // A temporary refresh failure does not mean the already-enqueued
          // search failed. Keep polling until the bounded window expires.
        }
      }
    } catch (err) {
      if (isCurrent()) {
        const message = err instanceof Error ? err.message : "Could not start the job search";
        reportRecoverableError(feedback, message);
      }
    } finally {
      if (isCurrent()) setBusy(false);
    }
  }, [token, busy, dashboard.profile?.last_run_at, isCurrent, feedback]);

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
