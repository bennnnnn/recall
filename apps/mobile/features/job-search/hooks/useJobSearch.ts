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
  type JobMatchView,
  type JobSearchDashboard,
  type JobSearchInput,
  type JobSearchProfile,
} from "@/lib/api";
import { cacheJobMatches } from "@/features/job-search/model/matchCache";
import { hasApplied } from "@/features/job-search/model/stages";
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
    status: previous?.status ?? "active",
    last_run_at: previous?.last_run_at ?? null,
    last_run_status: previous?.last_run_status ?? null,
    created_at: previous?.created_at ?? now,
    updated_at: now,
  };
}

export function useJobSearch(
  isCurrent: () => boolean,
  runId?: string,
  view?: JobMatchView,
  { autoRefresh = true }: { autoRefresh?: boolean } = {},
) {
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
  const pageBusyRef = useRef(false);
  const queryKey = `${view ?? "dashboard"}:${runId ?? ""}`;
  const queryKeyRef = useRef(queryKey);
  queryKeyRef.current = queryKey;
  const [loadedQuery, setLoadedQuery] = useState(queryKey);
  const loadedQueryRef = useRef(loadedQuery);
  loadedQueryRef.current = loadedQuery;
  const refreshRef = useRef<() => Promise<void>>(async () => {});

  // Mutation responses include the compatibility dashboard, not the selected page.
  // Keep loaded history and bookmarks when updating a job or the search settings.
  const reconcile = useCallback((next: JobSearchDashboard, id?: string, status?: JobMatchStatus) => {
    if (!view) return next;
    const current = dashboardRef.current;
    let removed = 0;
    const matches = current.matches.flatMap(match => {
      const updated = match.id === id
        ? { ...match, ...next.matches.find(item => item.id === id), ...(status ? { status } : {}) }
        : match;
      if (view === "applied" && !hasApplied(updated.status)) {
        removed++;
        return [];
      }
      return [updated];
    });
    return { ...next, matches, next_offset: current.next_offset == null ? null : current.next_offset - removed };
  }, [view]);

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token || mutationBusyRef.current) return;
      const request = ++refreshRequestRef.current;
      const query = queryKey;
      if (!opts?.silent) setLoading(true);
      try {
        const [next, results] = await Promise.all([
          view ? api.getJobSearch(token, false) : api.getJobSearch(token),
          view || runId ? api.getJobMatches(token, 0, runId, view) : Promise.resolve(null),
        ]);
        if (results) { next.matches = results.matches; next.next_offset = results.next_offset; }
        if (!isCurrent() || query !== queryKeyRef.current || request !== refreshRequestRef.current || mutationBusyRef.current) return;
        if (user?.id) cacheJobMatches(user.id, next.matches);
        dashboardRef.current = next;
        setDashboard(next);
        setLoadedQuery(query);
        setError(false);
      } catch {
        if (isCurrent() && query === queryKeyRef.current && request === refreshRequestRef.current) {
          setError(true);
          if (loadedQueryRef.current !== query) {
            setDashboard(current => ({ ...current, matches: [], next_offset: null }));
            setLoadedQuery(query);
          }
        }
      } finally {
        if (isCurrent() && query === queryKeyRef.current && request === refreshRequestRef.current) setLoading(false);
      }
    },
    [token, user?.id, isCurrent, runId, view, queryKey],
  );
  refreshRef.current = refresh;

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, view, runId]);

  useFocusEffect(useCallback(() => {
    if (!autoRefresh) return;
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
  }, [refresh, autoRefresh]));

  const save = useCallback(
    async (input: JobSearchInput): Promise<boolean> => {
      if (!token || mutationBusyRef.current || pageBusyRef.current || !isCurrent()) return false;
      const query = queryKeyRef.current;
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
        const next = reconcile(await api.saveJobSearch(token, input));
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
        if (isCurrent()) {
          setBusy(pageBusyRef.current);
          if (query !== queryKeyRef.current) void refreshRef.current();
        }
      }
    },
    [token, isCurrent, feedback, t, reconcile],
  );

  const setSearchStatus = useCallback(
    async (status: "active" | "paused") => {
      if (!token || mutationBusyRef.current || pageBusyRef.current || !isCurrent()) return;
      const query = queryKeyRef.current;
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
        const next = reconcile(await api.setJobSearchStatus(token, status));
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
        if (isCurrent()) {
          setBusy(pageBusyRef.current);
          if (query !== queryKeyRef.current) void refreshRef.current();
        }
      }
    },
    [token, isCurrent, feedback, t, reconcile],
  );

  const setMatchStatus = useCallback(
    async (id: string, status: JobMatchStatus) => {
      if (!token || mutationBusyRef.current || pageBusyRef.current || !isCurrent()) return;
      mutationBusyRef.current = true;
      setBusy(true);
      const query = queryKeyRef.current;
      const previous = dashboardRef.current;
      setDashboard((current) => ({
        ...current,
        matches: current.matches.map((match) =>
          match.id === id ? { ...match, status } : match,
        ),
      }));
      try {
        const next = reconcile(await api.setJobMatchStatus(token, id, status), id, status);
        if (user?.id) cacheJobMatches(user.id, next.matches);
        if (isCurrent()) setDashboard(next);
      } catch {
        if (!isCurrent()) return;
        setDashboard(previous);
        reportRecoverableError(feedback, t("my_job.error_match"));
      } finally {
        mutationBusyRef.current = false;
        if (isCurrent()) {
          setBusy(pageBusyRef.current);
          if (query !== queryKeyRef.current) void refreshRef.current();
        }
      }
    },
    [token, user?.id, dashboard, isCurrent, feedback, t, reconcile],
  );

  const setMatchSaved = useCallback(
    async (id: string, isSaved: boolean) => {
      if (!token || mutationBusyRef.current || pageBusyRef.current || !isCurrent()) return;
      mutationBusyRef.current = true;
      setBusy(true);
      const query = queryKeyRef.current;
      const previous = dashboardRef.current;
      setDashboard((current) => ({
        ...current,
        matches: current.matches.map((match) =>
          match.id === id ? { ...match, is_saved: isSaved } : match,
        ),
      }));
      try {
        const response = await api.setJobMatchSaved(token, id, isSaved);
        const next = reconcile(response, id);
        if (user?.id) cacheJobMatches(user.id, next.matches);
        if (isCurrent()) setDashboard(next);
      } catch {
        if (!isCurrent()) return;
        setDashboard(previous);
        reportRecoverableError(feedback, t("my_job.error_match"));
      } finally {
        mutationBusyRef.current = false;
        if (isCurrent()) {
          setBusy(pageBusyRef.current);
          if (query !== queryKeyRef.current) void refreshRef.current();
        }
      }
    },
    [token, user?.id, dashboard, isCurrent, feedback, t, reconcile],
  );

  const remove = useCallback(async (): Promise<boolean> => {
    if (!token || mutationBusyRef.current || pageBusyRef.current || !isCurrent()) return false;
    const query = queryKeyRef.current;
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
      if (isCurrent()) {
        setBusy(false);
        if (query !== queryKeyRef.current) void refreshRef.current();
      }
    }
  }, [token, isCurrent, feedback, t]);

  const runNow = useCallback(async (): Promise<boolean> => {
    if (!token || mutationBusyRef.current || pageBusyRef.current || !isCurrent()) return false;
    const query = queryKeyRef.current;
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
      const next = reconcile(await api.getJobSearch(token));
      requestKeyRef.current = null;
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
      if (isCurrent()) {
        setBusy(false);
        if (query !== queryKeyRef.current) void refreshRef.current();
      }
    }
  }, [token, isCurrent, feedback, t, reconcile]);

  const loadMore = useCallback(async () => {
    const offset = dashboardRef.current.next_offset;
    if (!token || offset == null || mutationBusyRef.current || pageBusyRef.current || loadedQuery !== queryKey) return;
    const query = queryKey;
    const request = refreshRequestRef.current;
    pageBusyRef.current = true;
    setBusy(true);
    try {
      const page = await api.getJobMatches(token, offset, runId, view);
      if (!isCurrent() || query !== queryKeyRef.current || request !== refreshRequestRef.current) return;
      const current = dashboardRef.current;
      const next = { ...current, next_offset: page.next_offset,
        matches: [...new Map([...current.matches, ...page.matches].map(match => [match.id, match])).values()] };
      dashboardRef.current = next;
      setDashboard(next);
      if (user?.id) cacheJobMatches(user.id, page.matches);
    } catch (err) {
      if (isCurrent() && query === queryKeyRef.current) reportRecoverableError(feedback, jobErrorMessage(err, t("my_job.refresh_error")));
    } finally { pageBusyRef.current = false; if (isCurrent() && !mutationBusyRef.current) setBusy(false); }
  }, [token, runId, view, queryKey, loadedQuery, user?.id, isCurrent, feedback, t]);

  return {
    dashboard: loadedQuery === queryKey ? dashboard : { ...dashboard, matches: [], next_offset: null },
    loadMore,
    loading: loading || loadedQuery !== queryKey,
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
