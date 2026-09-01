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
      if (token && completed.chatId && completed.callId && completed.userText) {
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
      if (completed.userText) onFirstReply(completed.chatId);
    },
    [applyEvent, feedback, onFirstReply, setMessages, status, t, token],
  );

  const finalizeCurrentTurn = useCallback(
    (nextPhase: LiveTalkPhase = "recording") => {
      const completed = captureCurrentTurn();
      setPhase(nextPhase);
      if (!completed || !completed.userText) return;
      void finishTurn(completed);
    },
    [captureCurrentTurn, finishTurn],
  );

  const flushPendingTurn = useCallback(() => {
    if (turnIdRef.current && userTextRef.current) finalizeCurrentTurn("recording");
  }, [finalizeCurrentTurn]);

  const handleRealtimeEvent = useCallback(
    (event: RealtimeVoiceEvent) => {
      if (!visibleRef.current && event.type !== "connected") return;
      if (event.type === "connected") {
        setPhase("recording");
        return;
      }
      if (event.type === "speech_started") {
        setPhase("recording");
        return;
      }
      if (event.type === "speech_stopped") {
        setPhase("thinking");
        return;
      }
      if (event.type === "user_transcript") {
        flushPendingTurn();
        turnIdRef.current = String(Date.now());
        userTextRef.current = event.text.trim();
        assistantTextRef.current = "";
        if (!userTextRef.current) return;
        applyEvent({ type: "user", text: userTextRef.current });
        setPhase("thinking");
        return;
      }
      if (event.type === "response_started") {
        if (turnIdRef.current && userTextRef.current) setPhase("thinking");
        return;
      }
      if (event.type === "assistant_transcript") {
        if (!turnIdRef.current || !userTextRef.current) return;
        assistantTextRef.current = event.text;
        applyEvent({ type: "assistant", text: event.text });
        setPhase("speaking");
        return;
      }
      if (event.type === "response_done") {
        finalizeCurrentTurn("recording");
        return;
      }
      if (event.type === "error") {
        reportRecoverableError(feedback, event.message || t("chat.live_talk_failed"));
        setPhase("recording");
      }
    },
    [applyEvent, feedback, finalizeCurrentTurn, flushPendingTurn, t],
  );

  const close = useCallback(() => {
    sessionGenRef.current += 1;
    visibleRef.current = false;
    const completed = captureCurrentTurn();
    if (completed?.userText) void finishTurn(completed);
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
      void api
        .liveTalkStatus(token)
        .then((latest) => setStatus(latest))
        .catch(() => undefined);
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

  const toggle = useCallback(async () => {
    if (phase === "thinking") {
      sessionRef.current?.cancelResponse();
      setPhase("recording");
    }
  }, [phase]);

  const interrupt = useCallback(() => {
    // Reliable half-duplex mode intentionally disables barge-in.
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
