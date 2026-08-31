import { useCallback, useEffect, useRef, useState } from "react";
import { BackHandler } from "react-native";
import { useRouter } from "expo-router";

import { useDrawer } from "@/contexts/DrawerContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api } from "@/lib/api";
import type { Message } from "@/lib/api";
import { applyLiveTalkChatEvent, type LiveTalkSpeakEvent } from "@/lib/liveTalkEvents";
import {
  liveTalkErrorGate,
  liveTalkGate,
  liveTalkShouldAttachSession,
  type LiveTalkGate,
  type LiveTalkPhase,
  type LiveTalkStatus,
} from "@/lib/liveTalkLogic";
import {
  createRealtimeVoiceSession,
  type RealtimeVoiceEvent,
  type RealtimeVoiceSession,
} from "@/lib/realtimeVoice";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

type DraftChat = {
  prepareDraftChat: (
    projectId?: string | null,
    model?: string,
    quizMode?: import("@/lib/quizMode").QuizMode | null,
    opts?: { force?: boolean },
  ) => Promise<string | null>;
  skipLoadForChatIdRef: React.MutableRefObject<string | null>;
  draftChatIdRef: React.MutableRefObject<string | null>;
  setDraftChatId: React.Dispatch<React.SetStateAction<string | null>>;
  creatingRef: React.MutableRefObject<boolean>;
};

type Options = {
  token: string | null;
  chatId: string | null;
  setChatId: React.Dispatch<React.SetStateAction<string | null>>;
  setChatTitle: React.Dispatch<React.SetStateAction<string | null>>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  draft: DraftChat;
  router: ReturnType<typeof useRouter>;
  selectedModel: string;
  isOffline: boolean;
  onUpgrade: () => void;
  onScrollToLatest: () => void;
  newMessageCountRef: React.MutableRefObject<number>;
  onFirstReply: (chatId?: string | null) => void;
  t: (key: string) => string;
};

type CompletedTurn = {
  id: string;
  chatId: string | null;
  callId: string | null;
  userText: string;
  assistantText: string;
};

const REALTIME_TRANSCRIPT_GRACE_MS = 350;

export function useLiveTalk({
  token,
  chatId,
  setChatId,
  setChatTitle,
  setMessages,
  draft,
  router,
  selectedModel,
  isOffline,
  onUpgrade,
  onScrollToLatest,
  newMessageCountRef,
  onFirstReply,
  t,
}: Options) {
  const feedback = useActionFeedbackOptional();
  const drawerOpen = useDrawer().isOpen;
  const [visible, setVisible] = useState(false);
  const [phase, setPhase] = useState<LiveTalkPhase>("idle");
  const [muted, setMuted] = useState(false);
  const [status, setStatus] = useState<LiveTalkStatus | null>(null);
  const sessionRef = useRef<RealtimeVoiceSession | null>(null);
  const callIdRef = useRef<string | null>(null);
  const turnIdRef = useRef("");
  const turnChatIdRef = useRef<string | null>(null);
  const assistantTextRef = useRef("");
  const userTextRef = useRef("");
  const visibleRef = useRef(false);
  const sessionGenRef = useRef(0);
  const finishTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const alertForGate = useCallback(
    (gate: LiveTalkGate) => {
      if (gate === "upgrade") {
        onUpgrade();
        return;
      }
      const message =
        gate === "limit"
          ? t("chat.live_talk_limit_body")
          : gate === "offline"
            ? t("chat.offline_body")
            : gate === "unconfigured"
              ? t("chat.live_talk_not_configured")
              : t("chat.live_talk_unavailable_body");
      reportRecoverableError(feedback, message);
    },
    [feedback, onUpgrade, t],
  );

  const ensureChatId = useCallback(async (): Promise<string | null> => {
    if (chatId) return chatId;
    draft.creatingRef.current = true;
    try {
      const id = await draft.prepareDraftChat(undefined, selectedModel);
      if (!id) return null;
      draft.skipLoadForChatIdRef.current = id;
      setChatTitle(null);
      setChatId(id);
      draft.draftChatIdRef.current = null;
      draft.setDraftChatId(null);
      router.setParams({ chatId: id });
      return id;
    } finally {
      draft.creatingRef.current = false;
    }
  }, [chatId, draft, router, selectedModel, setChatId, setChatTitle]);

  const applyEvent = useCallback(
    (event: LiveTalkSpeakEvent, turnId = turnIdRef.current) => {
      if (!turnId) return;
      setMessages((prev) => applyLiveTalkChatEvent(prev, turnId, event));
      if (event.type === "done") {
        newMessageCountRef.current += 2;
        onScrollToLatest();
      }
    },
    [newMessageCountRef, onScrollToLatest, setMessages],
  );

  const captureCurrentTurn = useCallback((): CompletedTurn | null => {
    const id = turnIdRef.current;
    if (!id) return null;
    const completed: CompletedTurn = {
      id,
      chatId: turnChatIdRef.current,
      callId: callIdRef.current,
      userText: userTextRef.current.trim(),
      assistantText: assistantTextRef.current.trim(),
    };
    turnIdRef.current = "";
    userTextRef.current = "";
    assistantTextRef.current = "";
    return completed;
  }, []);

  const finishTurn = useCallback(
    async (completed: CompletedTurn) => {
      // Persistence, title generation, memory extraction, todo extraction, and
      // RAG indexing stay outside the audio path. The completed turn is an
      // immutable snapshot so a fast barge-in cannot mutate what gets saved.
      if (token && completed.chatId && completed.callId && (completed.userText || completed.assistantText)) {
        void api
          .persistRealtimeLiveTalkTurn(token, {
            chatId: completed.chatId,
            callId: completed.callId,
            userText: completed.userText,
            assistantText: completed.assistantText,
          })
          .then(() => api.listMessages(token, completed.chatId!, { limit: 40 }))
          .then((page) => {
            if (page.messages.length > 0) setMessages(page.messages);
          })
          .catch((error: unknown) => {
            reportRecoverableError(
              feedback,
              error instanceof Error ? error.message : t("chat.live_talk_failed"),
            );
          });
      }

      try {
        const next = token ? await api.liveTalkStatus(token) : status;
        if (next) setStatus(next);
        applyEvent(
          {
            type: "done",
            remaining: next?.remaining ?? status?.remaining ?? 0,
            limit: next?.limit ?? status?.limit ?? 0,
            user_message: null,
            assistant_message: null,
          },
          completed.id,
        );
        onFirstReply(completed.chatId);
      } catch {
        // Voice already succeeded. A status refresh failure must not make the
        // completed turn look failed.
        applyEvent(
          {
            type: "done",
            remaining: status?.remaining ?? 0,
            limit: status?.limit ?? 0,
            user_message: null,
            assistant_message: null,
          },
          completed.id,
        );
      }
    },
    [applyEvent, feedback, onFirstReply, setMessages, status, t, token],
  );

  const finalizeCurrentTurn = useCallback(() => {
    const completed = captureCurrentTurn();
    if (!completed) return;
    setPhase("idle");
    void finishTurn(completed);
  }, [captureCurrentTurn, finishTurn]);

  const flushPendingTurn = useCallback(() => {
    if (finishTimerRef.current != null) {
      clearTimeout(finishTimerRef.current);
      finishTimerRef.current = null;
    }
    if (turnIdRef.current && (userTextRef.current || assistantTextRef.current)) {
      finalizeCurrentTurn();
    }
  }, [finalizeCurrentTurn]);

  const handleRealtimeEvent = useCallback(
    (event: RealtimeVoiceEvent) => {
      if (!visibleRef.current && event.type !== "connected") return;
      if (event.type === "connected") {
        setPhase("recording");
        return;
      }
      if (event.type === "speech_started") {
        // If the user barges in while the prior response is finishing, freeze
        // that completed turn before starting a new one.
        flushPendingTurn();
        turnIdRef.current = String(Date.now());
        userTextRef.current = "";
        assistantTextRef.current = "";
        setPhase("recording");
        return;
      }
      if (event.type === "speech_stopped") {
        setPhase("thinking");
        return;
      }
      if (event.type === "response_started") {
        if (!turnIdRef.current) turnIdRef.current = String(Date.now());
        setPhase("thinking");
        return;
      }
      if (event.type === "user_transcript") {
        if (!turnIdRef.current) turnIdRef.current = String(Date.now());
        userTextRef.current = event.text;
        applyEvent({ type: "user", text: event.text });
        return;
      }
      if (event.type === "assistant_transcript") {
        if (!turnIdRef.current) turnIdRef.current = String(Date.now());
        assistantTextRef.current = event.text;
        applyEvent({ type: "assistant", text: event.text });
        setPhase("speaking");
        return;
      }
      if (event.type === "response_done") {
        if (finishTimerRef.current != null) clearTimeout(finishTimerRef.current);
        // This grace affects only persistence/UI canonicalization, never audible
        // audio. It allows the final input-transcription event to arrive if it
        // trails response.done by a few network frames.
        finishTimerRef.current = setTimeout(() => {
          finishTimerRef.current = null;
          finalizeCurrentTurn();
        }, REALTIME_TRANSCRIPT_GRACE_MS);
        return;
      }
      if (event.type === "error") {
        reportRecoverableError(feedback, event.message || t("chat.live_talk_failed"));
        setPhase("idle");
      }
    },
    [applyEvent, feedback, finalizeCurrentTurn, flushPendingTurn, t],
  );

  const close = useCallback(() => {
    sessionGenRef.current += 1;
    visibleRef.current = false;
    if (finishTimerRef.current != null) {
      clearTimeout(finishTimerRef.current);
      finishTimerRef.current = null;
    }
    const completed = captureCurrentTurn();
    if (completed && (completed.userText || completed.assistantText)) {
      void finishTurn(completed);
    }
    sessionRef.current?.close();
    sessionRef.current = null;
    callIdRef.current = null;
    setMuted(false);
    setPhase("idle");
    setVisible(false);
  }, [captureCurrentTurn, finishTurn]);
  const closeRef = useRef(close);
  closeRef.current = close;

  const open = useCallback(async () => {
    if (!token) return;
    if (isOffline) {
      alertForGate("offline");
      return;
    }
    const gen = sessionGenRef.current + 1;
    sessionGenRef.current = gen;
    try {
      const next = await api.liveTalkStatus(token);
      if (!liveTalkShouldAttachSession(gen, sessionGenRef.current)) return;
      setStatus(next);
      const gate = liveTalkGate(next, isOffline);
      if (gate !== "ok") {
        alertForGate(gate);
        return;
      }
      const activeChatId = await ensureChatId();
      if (!liveTalkShouldAttachSession(gen, sessionGenRef.current)) return;
      turnChatIdRef.current = activeChatId;
      visibleRef.current = true;
      setMuted(false);
      setPhase("thinking");
      setVisible(true);
      const session = await createRealtimeVoiceSession({
        token,
        chatId: activeChatId,
        onEvent: handleRealtimeEvent,
      });
      if (!liveTalkShouldAttachSession(gen, sessionGenRef.current)) {
        session.close();
        return;
      }
      sessionRef.current = session;
      callIdRef.current = session.callId;
      setPhase("recording");
    } catch (error) {
      if (!liveTalkShouldAttachSession(gen, sessionGenRef.current)) return;
      visibleRef.current = false;
      setVisible(false);
      setPhase("idle");
      alertForGate(liveTalkErrorGate(error));
    }
  }, [token, isOffline, alertForGate, ensureChatId, handleRealtimeEvent]);

  const toggleMute = useCallback(() => {
    const next = !muted;
    setMuted(next);
    sessionRef.current?.setMuted(next);
  }, [muted]);

  // Semantic VAD owns turn boundaries. Normal interruption is simply speaking
  // over the assistant; the Realtime session has interrupt_response enabled.
  const toggle = useCallback(async () => {
    if (phase === "thinking") {
      sessionRef.current?.cancelResponse();
      setPhase("idle");
    }
  }, [phase]);

  const interrupt = useCallback(() => {
    // Kept for the existing UI contract. Barge-in is automatic in Realtime.
  }, []);

  const yieldToComposer = useCallback(() => {
    close();
  }, [close]);

  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (drawerOpen) return false;
      close();
      return true;
    });
    return () => sub.remove();
  }, [visible, drawerOpen, close]);

  useEffect(() => {
    // Fast Refresh preserves `visible` and drops the native peer. A leftover
    // overlay with no session looks like Live Talk is on and hears nothing.
    if (visible && !sessionRef.current) {
      visibleRef.current = false;
      setVisible(false);
      setPhase("idle");
    }
    return () => closeRef.current();
  }, []);

  return {
    visible,
    phase,
    meterLevel: phase === "recording" ? 0.8 : phase === "speaking" ? 0.55 : 0.12,
    recording: phase === "recording",
    muted,
    open,
    close,
    toggle,
    toggleMute,
    yieldToComposer,
    interrupt,
  };
}
