import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import {
  api,
  type JobMatchStatus,
  type JobSearchDashboard,
  type JobSearchInput,
  type JobSearchProfile,
} from "@/lib/api";
import { cacheJobMatches } from "@/lib/jobSearch/matchCache";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

const EMPTY: JobSearchDashboard = { profile: null, matches: [] };

function optimisticProfile(
  input: JobSearchInput,
  previous: JobSearchProfile | null,
): JobSearchProfile {
  const now = new Date().toISOString();
  return {
    id: previous?.id ?? "local-job-search",
    ...input,
    resume_filename:
      input.resume_attachment_id === previous?.resume_attachment_id
        ? previous.resume_filename
        : null,
    status: previous?.status ?? "active",
    last_run_at: previous?.last_run_at ?? null,
    last_run_status: previous?.last_run_status ?? null,
    created_at: previous?.created_at ?? now,
    updated_at: now,
  };
}

export function useJobSearch(isCurrent: () => boolean) {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const [dashboard, setDashboard] = useState<JobSearchDashboard>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const dashboardRef = useRef(dashboard);
  dashboardRef.current = dashboard;
  const mutationBusyRef = useRef(false);

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token) return;
      if (!opts?.silent) setLoading(true);
      try {
        const next = await api.getJobSearch(token);
        if (user?.id) cacheJobMatches(user.id, next.matches);
        if (!isCurrent()) return;
        setDashboard(next);
        setError(false);
      } catch {
        if (isCurrent()) setError(true);
      } finally {
        if (isCurrent()) setLoading(false);
      }
    },
    [token, user?.id, isCurrent],
  );

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const save = useCallback(
    async (input: JobSearchInput): Promise<boolean> => {
      if (!token || mutationBusyRef.current || !isCurrent()) return false;
      const previous = dashboardRef.current;
      const optimistic = {
        ...previous,
        profile: optimisticProfile(input, previous.profile),
      };
      mutationBusyRef.current = true;
      setBusy(true);
      dashboardRef.current = optimistic;
      setDashboard(optimistic);
      try {
        const next = await api.saveJobSearch(token, input);
        if (!isCurrent()) return false;
        dashboardRef.current = next;
        setDashboard(next);
        setError(false);
        return true;
      } catch (err) {
        if (isCurrent()) {
          dashboardRef.current = previous;
          setDashboard(previous);
          const message = err instanceof Error ? err.message : t("my_job.error_save");
          reportRecoverableError(feedback, message);
        }
        return false;
      } finally {
        mutationBusyRef.current = false;
        if (isCurrent()) setBusy(false);
      }
    },
    [token, isCurrent, feedback, t],
  );

  const setSearchStatus = useCallback(
    async (status: "active" | "paused") => {
      if (!token || mutationBusyRef.current || !isCurrent()) return;
      const previous = dashboardRef.current;
      if (!previous.profile) return;
      const optimistic = {
        ...previous,
        profile: { ...previous.profile, status },
      };
      mutationBusyRef.current = true;
      setBusy(true);
      dashboardRef.current = optimistic;
      setDashboard(optimistic);
      try {
        const next = await api.setJobSearchStatus(token, status);
        if (isCurrent()) {
          dashboardRef.current = next;
          setDashboard(next);
        }
      } catch {
        if (isCurrent()) {
          dashboardRef.current = previous;
          setDashboard(previous);
          reportRecoverableError(feedback, t("my_job.error_update"));
        }
      } finally {
        mutationBusyRef.current = false;
        if (isCurrent()) setBusy(false);
      }
    },
    [token, isCurrent, feedback, t],
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
        if (user?.id) cacheJobMatches(user.id, next.matches);
        if (isCurrent()) setDashboard(next);
      } catch {
        if (!isCurrent()) return;
        setDashboard(previous);
        reportRecoverableError(feedback, t("my_job.error_match"));
      }
    },
    [token, user?.id, dashboard, isCurrent, feedback, t],
  );

  const remove = useCallback(async (): Promise<boolean> => {
    if (!token || mutationBusyRef.current || !isCurrent()) return false;
    mutationBusyRef.current = true;
    setBusy(true);
    try {
      await api.deleteJobSearch(token);
      if (!isCurrent()) return false;
      dashboardRef.current = EMPTY;
      setDashboard(EMPTY);
      return true;
    } catch {
      if (isCurrent()) reportRecoverableError(feedback, t("my_job.error_delete"));
      return false;
    } finally {
      mutationBusyRef.current = false;
      if (isCurrent()) setBusy(false);
    }
  }, [token, isCurrent, feedback, t]);

  const runNow = useCallback(async (): Promise<boolean> => {
    if (!token || mutationBusyRef.current || !isCurrent()) return false;
    const previous = dashboardRef.current;
    mutationBusyRef.current = true;
    setBusy(true);
    if (previous.profile) {
      const optimistic = {
        ...previous,
        profile: { ...previous.profile, last_run_status: null },
      };
      dashboardRef.current = optimistic;
      setDashboard(optimistic);
    }
    try {
      await api.runJobSearch(token);
      return true;
    } catch {
      if (isCurrent()) {
        dashboardRef.current = previous;
        setDashboard(previous);
        reportRecoverableError(feedback, t("my_job.error_run"));
      }
      return false;
    } finally {
      mutationBusyRef.current = false;
      if (isCurrent()) setBusy(false);
    }
  }, [token, isCurrent, feedback, t]);

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
