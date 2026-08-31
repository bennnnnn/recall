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
  const turnIdRef = useRef("");
  const turnChatIdRef = useRef<string | null>(null);
  const assistantTextRef = useRef("");
  const userTextRef = useRef("");
  const visibleRef = useRef(false);
  const finishTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  visibleRef.current = visible;

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

  const finishTurn = useCallback(async () => {
    const completedTurnId = turnIdRef.current;
    if (!completedTurnId) return;
    const completedChatId = turnChatIdRef.current;
    const completedUserText = userTextRef.current.trim();
    const completedAssistantText = assistantTextRef.current.trim();

    // Persistence, title generation, memory extraction, todo extraction, and RAG
    // indexing are deliberately outside the first-audio path. Capture the final
    // transcript now and let the server hydrate canonical message rows later.
    if (token && completedChatId && (completedUserText || completedAssistantText)) {
      void api
        .persistRealtimeLiveTalkTurn(token, {
          chatId: completedChatId,
          userText: completedUserText,
          assistantText: completedAssistantText,
        })
        .then(() => api.listMessages(token, completedChatId, { limit: 40 }))
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
        completedTurnId,
      );
      onFirstReply(completedChatId);
    } catch {
      // The spoken response already succeeded. Status refresh must not make the
      // completed voice turn look failed.
      applyEvent(
        {
          type: "done",
          remaining: status?.remaining ?? 0,
          limit: status?.limit ?? 0,
          user_message: null,
          assistant_message: null,
        },
        completedTurnId,
      );
    } finally {
      if (turnIdRef.current === completedTurnId) {
        turnIdRef.current = "";
        assistantTextRef.current = "";
        userTextRef.current = "";
        setPhase("idle");
      }
    }
  }, [applyEvent, feedback, onFirstReply, setMessages, status, t, token]);

  const flushPendingTurn = useCallback(() => {
    if (finishTimerRef.current != null) {
      clearTimeout(finishTimerRef.current);
      finishTimerRef.current = null;
      void finishTurn();
    }
  }, [finishTurn]);

  const handleRealtimeEvent = useCallback(
    (event: RealtimeVoiceEvent) => {
      if (!visibleRef.current && event.type !== "connected") return;
      if (event.type === "connected") {
        setPhase("idle");
        return;
      }
      if (event.type === "speech_started") {
        flushPendingTurn();
        if (!turnIdRef.current) turnIdRef.current = String(Date.now());
        assistantTextRef.current = "";
        userTextRef.current = "";
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
        finishTimerRef.current = setTimeout(() => {
          finishTimerRef.current = null;
          void finishTurn();
        }, REALTIME_TRANSCRIPT_GRACE_MS);
        return;
      }
      if (event.type === "error") {
        reportRecoverableError(feedback, event.message || t("chat.live_talk_failed"));
        setPhase("idle");
      }
    },
    [applyEvent, feedback, finishTurn, flushPendingTurn, t],
  );

  const close = useCallback(() => {
    if (finishTimerRef.current != null) {
      clearTimeout(finishTimerRef.current);
      finishTimerRef.current = null;
    }
    sessionRef.current?.close();
    sessionRef.current = null;
    turnIdRef.current = "";
    assistantTextRef.current = "";
    userTextRef.current = "";
    setMuted(false);
    setPhase("idle");
    setVisible(false);
  }, []);

  const open = useCallback(async () => {
    if (!token) return;
    if (isOffline) {
      alertForGate("offline");
      return;
    }
    try {
      const next = await api.liveTalkStatus(token);
      setStatus(next);
      const gate = liveTalkGate(next, isOffline);
      if (gate !== "ok") {
        alertForGate(gate);
        return;
      }
      const activeChatId = await ensureChatId();
      turnChatIdRef.current = activeChatId;
      setMuted(false);
      setPhase("thinking");
      setVisible(true);
      const session = await createRealtimeVoiceSession({
        token,
        chatId: activeChatId,
        onEvent: handleRealtimeEvent,
      });
      if (!visibleRef.current) {
        session.close();
        return;
      }
      sessionRef.current = session;
      setPhase("idle");
    } catch (error) {
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
    if (phase === "thinking") setPhase("idle");
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

  useEffect(() => close, [close]);

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
