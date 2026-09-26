import { useCallback, useEffect, useRef, useState } from "react";
import { Linking } from "react-native";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { api, type JobMatch, type JobMatchStatus } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import {
  cacheJobMatch,
  cacheJobMatches,
  getCachedJobMatch,
} from "@/features/job-search/model/matchCache";
import { alertDialog } from "@/ui/overlay/dialogs";

export function useJobMatchDetail(id: string | undefined, isCurrent: () => boolean) {
  const { token, user } = useAuth();
  const accountId = user?.id;
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const router = useRouter();
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const isCurrentRef = useRef(isCurrent);
  isCurrentRef.current = isCurrent;
  const mountedRef = useRef(false);
  const loadRequestRef = useRef(0);
  const mutationRequestRef = useRef(0);
  const letterRequestRef = useRef(0);
  const letterBusyRef = useRef(false);
  const initialMatch = id && accountId ? getCachedJobMatch(accountId, id) : null;
  const [match, setMatch] = useState<JobMatch | null>(initialMatch);
  const matchRef = useRef<JobMatch | null>(initialMatch);
  const [loading, setLoading] = useState(Boolean(id && token && !initialMatch));
  const [loadError, setLoadError] = useState(false);
  const [notesDraft, setNotesDraftState] = useState(initialMatch?.notes ?? "");
  const [stageOpen, setStageOpen] = useState(false);
  const [letterOpen, setLetterOpen] = useState(false);
  const [letterLoading, setLetterLoading] = useState(false);
  const [letter, setLetter] = useState<string | null>(null);

  const setCurrentMatch = useCallback((next: JobMatch | null) => {
    matchRef.current = next;
    setMatch(next);
  }, []);

  const isActive = useCallback(
    () => mountedRef.current && isCurrentRef.current(),
    [],
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      loadRequestRef.current += 1;
      mutationRequestRef.current += 1;
      letterRequestRef.current += 1;
    };
  }, []);

  const load = useCallback(async () => {
    const currentToken = tokenRef.current;
    if (!currentToken || !id || !isActive()) return;
    const request = ++loadRequestRef.current;
    if (!matchRef.current) setLoading(true);
    setLoadError(false);
    try {
      const dashboard = await api.getJobSearch(currentToken);
      if (!isActive() || request !== loadRequestRef.current) return;
      if (accountId) cacheJobMatches(accountId, dashboard.matches);
      const next = dashboard.matches.find((item) => item.id === id) ?? null;
      setCurrentMatch(next);
      setNotesDraftState(next?.notes ?? "");
      setLoading(false);
    } catch {
      if (!isActive() || request !== loadRequestRef.current) return;
      setLoading(false);
      setLoadError(true);
    }
  }, [accountId, id, isActive, setCurrentMatch]);

  useEffect(() => {
    if (!initialMatch) void load();
    // `initialMatch` is the mount-time cache snapshot for this keyed view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  const updateStatus = useCallback(
    async (status: JobMatchStatus, notes?: string | null) => {
      const currentToken = tokenRef.current;
      const previous = matchRef.current;
      if (!currentToken || !previous || !isActive()) return false;
      const request = ++mutationRequestRef.current;
      const next: JobMatch = {
        ...previous,
        status,
        notes: notes === undefined ? previous.notes : notes,
      };
      setCurrentMatch(next);
      if (accountId) cacheJobMatch(accountId, next);
      try {
        const dashboard = await api.setJobMatchStatus(
          currentToken,
          previous.id,
          status,
          notes,
        );
        if (!isActive() || request !== mutationRequestRef.current) return false;
        if (accountId) cacheJobMatches(accountId, dashboard.matches);
        const confirmed =
          dashboard.matches.find((item) => item.id === previous.id) ?? next;
        setCurrentMatch(confirmed);
        if (notes !== undefined) setNotesDraftState(confirmed.notes ?? "");
        if (status === "hidden") router.back();
        return true;
      } catch {
        if (!isActive() || request !== mutationRequestRef.current) return false;
        setCurrentMatch(previous);
        if (accountId) cacheJobMatch(accountId, previous);
        if (notes !== undefined) setNotesDraftState(previous.notes ?? "");
        reportRecoverableError(feedback, t("my_job.error_match"));
        return false;
      }
    },
    [accountId, feedback, isActive, router, setCurrentMatch, t],
  );

  const updateSaved = useCallback(
    async (isSaved: boolean) => {
      const currentToken = tokenRef.current;
      const previous = matchRef.current;
      if (!currentToken || !previous || !isActive()) return false;
      const request = ++mutationRequestRef.current;
      const next: JobMatch = { ...previous, is_saved: isSaved };
      setCurrentMatch(next);
      if (accountId) cacheJobMatch(accountId, next);
      try {
        const dashboard = await api.setJobMatchSaved(currentToken, previous.id, isSaved);
        if (!isActive() || request !== mutationRequestRef.current) return false;
        if (accountId) cacheJobMatches(accountId, dashboard.matches);
        const confirmed =
          dashboard.matches.find((item) => item.id === previous.id) ?? next;
        setCurrentMatch(confirmed);
        return true;
      } catch {
        if (!isActive() || request !== mutationRequestRef.current) return false;
        setCurrentMatch(previous);
        if (accountId) cacheJobMatch(accountId, previous);
        reportRecoverableError(feedback, t("my_job.error_match"));
        return false;
      }
    },
    [accountId, feedback, isActive, setCurrentMatch, t],
  );

  const saveNotes = useCallback(() => {
    const current = matchRef.current;
    if (!current || !isActive()) return;
    const notes = notesDraft.trim();
    if ((current.notes ?? "") === notes) return;
    void updateStatus(current.status, notes === "" ? null : notes);
  }, [isActive, notesDraft, updateStatus]);

  const setNotesDraft = useCallback((value: string) => {
    setNotesDraftState(value);
  }, []);

  const openJob = useCallback(async () => {
    const current = matchRef.current;
    if (!current || !isActive()) return;
    try {
      await Linking.openURL(current.url);
    } catch {
      if (isActive()) {
        void alertDialog({
          title: t("my_job.open_failed_title"),
          message: t("my_job.open_failed_body"),
        });
      }
    }
  }, [isActive, t]);

  const generateLetter = useCallback(async () => {
    const currentToken = tokenRef.current;
    const current = matchRef.current;
    if (!currentToken || !current || letterBusyRef.current || !isActive()) return;
    const request = ++letterRequestRef.current;
    letterBusyRef.current = true;
    tap();
    setLetterOpen(true);
    setLetterLoading(true);
    setLetter(null);
    try {
      const result = await api.generateCoverLetter(currentToken, current.id);
      if (isActive() && request === letterRequestRef.current) {
        setLetter(result.cover_letter);
      }
    } catch {
      if (isActive() && request === letterRequestRef.current) {
        setLetterOpen(false);
        reportRecoverableError(feedback, t("my_job.cover_letter_error"));
      }
    } finally {
      if (request === letterRequestRef.current) {
        letterBusyRef.current = false;
        if (isActive()) setLetterLoading(false);
      }
    }
  }, [feedback, isActive, t]);

  return {
    match,
    loading,
    loadError,
    load,
    updateStatus,
    updateSaved,
    notesDraft,
    setNotesDraft,
    saveNotes,
    openJob,
    stageOpen,
    setStageOpen,
    letterOpen,
    setLetterOpen,
    letterLoading,
    letter,
    generateLetter,
  };
}
