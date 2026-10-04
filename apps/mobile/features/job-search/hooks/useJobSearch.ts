import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";
import { randomUUID } from "expo-crypto";
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
import { cacheJobMatches } from "@/features/job-search/model/matchCache";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

function jobErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback;
  try {
    const payload: unknown = JSON.parse(error.message);
    return payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string" ? payload.detail : fallback;
  } catch { return error.message || fallback; }
}

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

export function useJobSearch(isCurrent: () => boolean, runId?: string) {
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
  const refreshRequestRef = useRef(0);
  const requestKeyRef = useRef<string | null>(null);

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token || mutationBusyRef.current) return;
      const request = ++refreshRequestRef.current;
      if (!opts?.silent) setLoading(true);
      try {
        const next = await api.getJobSearch(token);
        if (runId) { const results = await api.getJobMatches(token, 0, runId); next.matches = results.matches; next.next_offset = results.next_offset; }
        if (user?.id) cacheJobMatches(user.id, next.matches);
        if (!isCurrent() || request !== refreshRequestRef.current || mutationBusyRef.current) return;
        dashboardRef.current = next;
        setDashboard(next);
        setError(false);
      } catch {
        if (isCurrent()) setError(true);
      } finally {
        if (isCurrent()) setLoading(false);
      }
    },
    [token, user?.id, isCurrent, runId],
  );

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useFocusEffect(useCallback(() => {
    let visible = true;
    const timer = setInterval(() => {
      if (visible && AppState.currentState === "active" &&
          ["queued", "running"].includes(dashboardRef.current.latest_run?.state ?? "")) {
        void refresh({ silent: true });
      }
    }, 3000);
    const listener = AppState.addEventListener("change", (state) => {
      if (state === "active" && visible) void refresh({ silent: true });
    });
    return () => { visible = false; clearInterval(timer); listener.remove(); };
  }, [refresh]));

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
          const message = jobErrorMessage(err, t("my_job.error_save"));
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
      if (!token || mutationBusyRef.current || !isCurrent()) return;
      mutationBusyRef.current = true;
      setBusy(true);
      const previous = dashboardRef.current;
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
      } finally {
        mutationBusyRef.current = false;
        if (isCurrent()) setBusy(false);
      }
    },
    [token, user?.id, dashboard, isCurrent, feedback, t],
  );

  const setMatchSaved = useCallback(
    async (id: string, isSaved: boolean) => {
      if (!token || mutationBusyRef.current || !isCurrent()) return;
      mutationBusyRef.current = true;
      setBusy(true);
      const previous = dashboardRef.current;
      setDashboard((current) => ({
        ...current,
        matches: current.matches.map((match) =>
          match.id === id ? { ...match, is_saved: isSaved } : match,
        ),
      }));
      try {
        const next = await api.setJobMatchSaved(token, id, isSaved);
        if (user?.id) cacheJobMatches(user.id, next.matches);
        if (isCurrent()) setDashboard(next);
      } catch {
        if (!isCurrent()) return;
        setDashboard(previous);
        reportRecoverableError(feedback, t("my_job.error_match"));
      } finally {
        mutationBusyRef.current = false;
        if (isCurrent()) setBusy(false);
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
      requestKeyRef.current ??= randomUUID();
      await api.runJobSearch(token, requestKeyRef.current);
      requestKeyRef.current = null;
      const next = await api.getJobSearch(token);
      if (isCurrent()) { dashboardRef.current = next; setDashboard(next); }
      return true;
    } catch (err) {
      if (isCurrent()) {
        dashboardRef.current = previous;
        setDashboard(previous);
        reportRecoverableError(feedback, jobErrorMessage(err, t("my_job.error_run")));
      }
      return false;
    } finally {
      mutationBusyRef.current = false;
      if (isCurrent()) setBusy(false);
    }
  }, [token, isCurrent, feedback, t]);

  const loadMore = useCallback(async () => {
    const offset = dashboardRef.current.next_offset;
    if (!token || offset == null || mutationBusyRef.current) return;
    mutationBusyRef.current = true;
    setBusy(true);
    try {
      const page = await api.getJobMatches(token, offset, runId);
      if (!isCurrent()) return;
      setDashboard(current => ({ ...current, next_offset: page.next_offset,
        matches: [...new Map([...current.matches, ...page.matches].map(match => [match.id, match])).values()] }));
    } catch (err) {
      if (isCurrent()) reportRecoverableError(feedback, jobErrorMessage(err, t("my_job.refresh_error")));
    } finally { mutationBusyRef.current = false; if (isCurrent()) setBusy(false); }
  }, [token, runId, isCurrent, feedback, t]);

  return {
    dashboard,
    loadMore,
    loading,
    busy,
    error,
    refresh,
    save,
    setSearchStatus,
    setMatchStatus,
    setMatchSaved,
    runNow,
    remove,
  };
}
