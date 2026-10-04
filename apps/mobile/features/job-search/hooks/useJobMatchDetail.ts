import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, Linking } from "react-native";
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
  const mutationBusyRef = useRef(false);
  const notesDirtyRef = useRef(false);
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
    if (!currentToken || !id || !isActive() || mutationBusyRef.current) return;
    const request = ++loadRequestRef.current;
    if (!matchRef.current) setLoading(true);
    setLoadError(false);
    try {
      const next = await api.getJobMatch(currentToken, id);
      if (!isActive() || request !== loadRequestRef.current) return;
      if (accountId) cacheJobMatch(accountId, next);
      setCurrentMatch(next);
      if (!notesDirtyRef.current) setNotesDraftState(next.notes ?? "");
      setLoading(false);
    } catch (error) {
      if (!isActive() || request !== loadRequestRef.current) return;
      setLoading(false);
      if (error && typeof error === "object" && "status" in error && error.status === 404) {
        setCurrentMatch(null);
        setLoadError(false);
      } else setLoadError(true);
    }
  }, [accountId, id, isActive, setCurrentMatch]);

  useEffect(() => {
    void load();
    const listener = AppState.addEventListener("change", state => { if (state === "active") void load(); });
    return () => listener.remove();
  }, [load]);

  const updateStatus = useCallback(
    async (status: JobMatchStatus, notes?: string | null) => {
      const currentToken = tokenRef.current;
      const previous = matchRef.current;
      if (!currentToken || !previous || !isActive() || mutationBusyRef.current) return false;
      mutationBusyRef.current = true;
      loadRequestRef.current += 1;
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
        if (notes !== undefined) { notesDirtyRef.current = false; setNotesDraftState(confirmed.notes ?? ""); }
        if (status === "hidden") router.back();
        return true;
      } catch {
        if (!isActive() || request !== mutationRequestRef.current) return false;
        setCurrentMatch(previous);
        if (accountId) cacheJobMatch(accountId, previous);
        if (notes !== undefined) setNotesDraftState(previous.notes ?? "");
        reportRecoverableError(feedback, t("my_job.error_match"));
        return false;
      } finally { mutationBusyRef.current = false; }
    },
    [accountId, feedback, isActive, router, setCurrentMatch, t],
  );

  const updateSaved = useCallback(
    async (isSaved: boolean) => {
      const currentToken = tokenRef.current;
      const previous = matchRef.current;
      if (!currentToken || !previous || !isActive() || mutationBusyRef.current) return false;
      mutationBusyRef.current = true;
      loadRequestRef.current += 1;
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
      } finally { mutationBusyRef.current = false; }
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
    notesDirtyRef.current = true;
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
