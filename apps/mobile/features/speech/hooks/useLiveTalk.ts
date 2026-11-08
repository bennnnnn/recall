import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MutableRefObject,
  type SetStateAction,
} from "react";
import { AppState, BackHandler, Linking } from "react-native";

import { useDrawerControls } from "@/contexts/DrawerContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api } from "@/lib/api";
import type { Message } from "@/lib/api";
import { applyLiveTalkChatEvent, type LiveTalkSpeakEvent } from "@/features/speech/model/liveTalkEvents";
import { createInOrder, createLiveTalkTurns, type LiveTalkTurn } from "@/features/speech/model/liveTalkTurns";
import {
  liveTalkCallEnds,
  liveTalkCallErrorKey,
  liveTalkErrorGate,
  liveTalkGateMessageKey,
  liveTalkSessionLimitMs,
  liveTalkGate,
  liveTalkSaveEndsCall,
  liveTalkSaveFailedKey,
  liveTalkShouldAttachSession,
  liveTalkShouldCloseOnAppState,
  liveTalkShouldCloseOnChatChange,
  liveTalkTimeUpKey,
  type LiveTalkGate,
  type LiveTalkPhase,
  type LiveTalkStatus,
} from "@/features/speech/model/liveTalkLogic";
import { stopReadAloud } from "@/features/speech/model/readAloudSession";
import type { RealtimeVoiceEvent, RealtimeVoiceSession } from "@/features/speech/model/realtimeVoice";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";

/**
 * What live talk takes from the chat screen it runs on: the chat a turn lands in and
 * how its bubbles show. Speech owns this shape, so it never imports the chat feature
 * (code-health audit ARCH-10).
 */
type Options = {
  token: string | null;
  chatId: string | null;
  /** The open chat's id, or a new chat made the open one; null when none could be made (no call then). */
  ensureChatId: () => Promise<string | null>;
  /** Changes the thread on screen, which the chat owns: live talk's turns, named "live_talk". */
  editThread: (update: SetStateAction<Message[]>, source: "live_talk") => void;
  isOffline: boolean;
  onUpgrade: () => void;
  onScrollToLatest: () => void;
  newMessageCountRef: MutableRefObject<number>;
  onFirstReply: (chatId?: string | null) => void;
  t: (key: string) => string;
};

/** A turn handed on to be saved, with the chat and call it was spoken in. */
type CompletedTurn = LiveTalkTurn & { chatId: string | null; callId: string | null };

function clearTimer(timer: MutableRefObject<ReturnType<typeof setTimeout> | null>): void {
  if (timer.current != null) clearTimeout(timer.current);
  timer.current = null;
}

// The WebRTC session, its turn state and the chimes load when Live Talk is
// started, not with the chat screen. The hook itself stays static.
function loadRealtimeVoice() {
  return import("@/features/speech/model/realtimeVoice");
}

/** Best-effort, as the cue itself is: a chime that cannot load never fails Live Talk. */
function playCue(kind: "start" | "end"): Promise<void> {
  return import("@/features/speech/model/liveTalkSfx")
    .then(({ playLiveTalkCue }) => playLiveTalkCue(kind))
    .catch(() => {});
}

/** Why live talk did not start, or stopped: the plans, Settings for the mic, or a message. */
function showLiveTalkGate(
  gate: LiveTalkGate,
  { feedback, onUpgrade, t }: {
    feedback: ReturnType<typeof useActionFeedbackOptional>;
    onUpgrade: () => void;
    t: (key: string) => string;
  },
): void {
  if (gate === "upgrade") {
    onUpgrade();
    return;
  }
  // The API client already sent the account to the consent step.
  if (gate === "consent") return;
  if (gate === "mic_permission") {
    // The OS asks only once; after a denial only Settings can turn it on.
    void confirmDialog({
      title: t("chat.live_talk_mic_permission_title"),
      message: t("chat.live_talk_mic_permission_body"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("chat.location_open_settings"),
    }).then((open) => {
      if (open) void Linking.openSettings();
    });
    return;
  }
  reportRecoverableError(feedback, t(liveTalkGateMessageKey(gate)));
}

export function useLiveTalk({
  token,
  chatId,
  ensureChatId,
  editThread,
  isOffline,
  onUpgrade,
  onScrollToLatest,
  newMessageCountRef,
  onFirstReply,
  t,
}: Options) {
  const feedback = useActionFeedbackOptional();
  // Read when Back is pressed, not subscribed: the chat screen that calls this
  // hook must not render again every time the drawer opens or closes.
  const drawer = useDrawerControls();
  const [visible, setVisible] = useState(false);
  const [phase, setPhase] = useState<LiveTalkPhase>("idle");
  const [muted, setMuted] = useState(false);
  /** The reply's audio is playing on the phone: the only time the orb moves. */
  const [voicePlaying, setVoicePlaying] = useState(false);
  const [status, setStatus] = useState<LiveTalkStatus | null>(null);
  const sessionRef = useRef<RealtimeVoiceSession | null>(null);
  const callIdRef = useRef<string | null>(null);
  const turnChatIdRef = useRef<string | null>(null);
  const sourcesRef = useRef<Message["search_sources"]>([]);
  const visibleRef = useRef(false);
  const sessionGenRef = useRef(0);
  const finishTurnRef = useRef<(completed: CompletedTurn) => Promise<void>>(async () => {});
  // Each turn is saved with the chat and call it was spoken in, read as it is handed on.
  const [turns] = useState(() => createLiveTalkTurns((turn) => {
    void finishTurnRef.current({ ...turn, chatId: turnChatIdRef.current, callId: callIdRef.current });
  }));
  // The saves, and the hang-up's end after them, go one at a time (createInOrder).
  const [inOrder] = useState(createInOrder);
  const sessionLimitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeRef = useRef<() => void>(() => {});
  /** Aborts the call still connecting: a hang-up gives its route, mic and minutes back at once. */
  const connectingRef = useRef<AbortController | null>(null);

  const alertForGate = useCallback(
    (gate: LiveTalkGate) => showLiveTalkGate(gate, { feedback, onUpgrade, t }),
    [feedback, onUpgrade, t],
  );

  const applyEvent = useCallback(
    (event: LiveTalkSpeakEvent, turnId: string) => {
      editThread((prev) => applyLiveTalkChatEvent(prev, turnId, event), "live_talk");
    },
    [editThread],
  );

  const finishTurn = useCallback(
    async (completed: CompletedTurn) => {
      newMessageCountRef.current += Number(Boolean(completed.userText)) + Number(Boolean(completed.assistantText));
      onScrollToLatest();
      // Persistence, title generation, memory extraction, todo extraction, and
      // RAG indexing stay outside the audio path. Snapshot the completed turn
      // so a later utterance cannot mutate what gets saved.
      if (token && completed.chatId && completed.callId && (completed.userText || completed.assistantText)) {
        const save = { chatId: completed.chatId, callId: completed.callId, turnId: completed.id };
        void inOrder(() => api.persistRealtimeLiveTalkTurn(token, {
          ...save, userText: completed.userText, assistantText: completed.assistantText,
        }))
          .then((saved) => {
            // Reconcile this turn in place, never replace the whole thread
            // with a delayed list fetch while the next utterance is streaming.
            if (saved) applyEvent({ type: "done", remaining: 0, limit: 0,
              user_message: saved.user_message, assistant_message: saved.assistant_message }, completed.id);
          })
          .catch((error: unknown) => {
            const gate = liveTalkErrorGate(error);
            if (!liveTalkSaveEndsCall(gate)) {
              reportRecoverableError(feedback, t(liveTalkSaveFailedKey(gate)));
            } else if (callIdRef.current === completed.callId) {
              // Once: the hang-up's own save of the last turn is refused the same way.
              closeRef.current();
              alertForGate(gate);
            }
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
    [alertForGate, applyEvent, feedback, inOrder, newMessageCountRef, onFirstReply, onScrollToLatest, status, t, token],
  );
  finishTurnRef.current = finishTurn;

  const handleRealtimeEvent = useCallback(
    (event: RealtimeVoiceEvent) => {
      const dropped = !visibleRef.current && event.type !== "connected";
      if (dropped) return;
      if (event.type === "output_audio") return setVoicePlaying(event.playing);
      if (event.type === "connected") {
        setPhase("recording");
        return;
      }
      if (event.type === "speech_started") {
        // The turn before is saved now, or once its own line lands (liveTalkTurns).
        turns.utterance(event.turnId ?? String(Date.now()));
        sourcesRef.current = [];
        setPhase("recording");
        return;
      }
      if (event.type === "response_interrupted") {
        // Transcripts run ahead of the audio, so the unspoken text is not saved,
        // nor a "Stopped" label as if Recall said it: the turn keeps the user's
        // line alone. OpenAI truncates its own conversation buffer.
        if (turns.current()) applyEvent({ type: "assistant_cut" }, turns.assistant(""));
        turns.replied();
        setPhase("recording");
        return;
      }
      if (event.type === "search_sources") {
        sourcesRef.current = event.sources;
        const turn = turns.current();
        if (turn?.assistantText) applyEvent({ type: "assistant", text: turn.assistantText, sources: event.sources }, turn.id);
        return;
      }
      if (event.type === "speech_stopped") {
        setPhase(event.replying ? "thinking" : "recording");
        return;
      }
      if (event.type === "response_started") {
        turns.replyStarted();
        setPhase("thinking");
        return;
      }
      if (event.type === "user_transcript") {
        // Shown above the reply it prompted, then saved with it (a turn waiting for it saves now).
        const turnId = turns.turnFor(event.turnId);
        if (!turnId) return;
        applyEvent({ type: "user", text: event.text }, turnId);
        turns.user(turnId, event.text);
        return;
      }
      if (event.type === "assistant_transcript") {
        applyEvent({ type: "assistant", text: event.text, sources: sourcesRef.current }, turns.assistant(event.text));
        setPhase("speaking");
        return;
      }
      if (event.type === "response_done") {
        turns.replied();
        setPhase("idle");
        return;
      }
      if (event.type === "error" || event.type === "interrupted") {
        reportRecoverableError(feedback, t(liveTalkCallErrorKey(event)));
        setPhase("idle");
        // The same hang-up as the user's: the turn so far is saved and the call ended once.
        if (liveTalkCallEnds(event)) closeRef.current();
      }
    },
    [applyEvent, feedback, t, turns],
  );

  const close = useCallback(() => {
    sessionGenRef.current += 1;
    connectingRef.current?.abort();
    connectingRef.current = null;
    const shouldCueEnd = visibleRef.current || sessionRef.current != null;
    visibleRef.current = false;
    clearTimer(sessionLimitTimerRef);
    // Every turn still open is saved, under this call's id, before it is let go.
    turns.finishAll();
    sessionRef.current?.close();
    // Settle this month's minutes to the time actually used (best-effort: a
    // session never reported stays charged for its whole reservation).
    const endedCallId = callIdRef.current;
    if (token && endedCallId) {
      void inOrder(() => api.endRealtimeSession(token, endedCallId))
        .then((next) => setStatus(next))
        .catch(() => {});
    }
    sessionRef.current = null;
    callIdRef.current = null;
    setMuted(false);
    setVoicePlaying(false);
    setPhase("idle");
    setVisible(false);
    if (shouldCueEnd) void playCue("end");
  }, [inOrder, token, turns]);
  closeRef.current = close;

  const open = useCallback(async () => {
    if (!token) return;
    if (isOffline) {
      alertForGate("offline");
      return;
    }
    const voice = await loadRealtimeVoice().catch(() => null);
    if (!voice?.isRealtimeVoiceAvailable()) {
      alertForGate("unavailable");
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
      // Its turns are saved to this chat: without one, a call spent minutes and kept nothing.
      if (!activeChatId) return alertForGate("no_chat");
      turnChatIdRef.current = activeChatId;
      // A reply still read aloud stops as the call takes over: a clip that failed then fell back
      // to the phone's voice, which reset the audio mode under the call.
      stopReadAloud();
      visibleRef.current = true;
      setMuted(false);
      setPhase("thinking");
      setVisible(true);
      // Finish and release the open chime before getUserMedia. A leftover
      // expo-audio player keeps the session in playback and WebRTC is mute.
      await playCue("start");
      if (!liveTalkShouldAttachSession(gen, sessionGenRef.current)) return;
      const connecting = new AbortController();
      connectingRef.current = connecting;
      const session = await voice.createRealtimeVoiceSession({
        token,
        chatId: activeChatId,
        onEvent: handleRealtimeEvent,
        signal: connecting.signal,
      });
      if (connectingRef.current === connecting) connectingRef.current = null;
      if (!liveTalkShouldAttachSession(gen, sessionGenRef.current)) {
        session.close();
        if (session.callId) void api.endRealtimeSession(token, session.callId).catch(() => {});
        return;
      }
      sessionRef.current = session;
      callIdRef.current = session.callId;
      clearTimer(sessionLimitTimerRef);
      const limitMs = liveTalkSessionLimitMs(session.maxDurationSeconds);
      sessionLimitTimerRef.current = setTimeout(() => {
        sessionLimitTimerRef.current = null;
        closeRef.current();
        // It hung up with no word: say whether the month's minutes or only this call ran out.
        reportRecoverableError(feedback, t(liveTalkTimeUpKey(next, limitMs)));
      }, limitMs);
      setPhase("recording");
    } catch (error) {
      if (!liveTalkShouldAttachSession(gen, sessionGenRef.current)) return;
      visibleRef.current = false;
      setVisible(false);
      setPhase("idle");
      alertForGate(liveTalkErrorGate(error));
    }
  }, [token, isOffline, alertForGate, ensureChatId, handleRealtimeEvent, feedback, t]);

  const toggleMute = useCallback(() => {
    const next = !muted;
    setMuted(next);
    sessionRef.current?.setMuted(next);
  }, [muted]);

  // Half-duplex: VAD still chunks speech; the client starts each reply.
  // interrupt_response stays off so echo cannot barge into playback.
  const toggle = useCallback(async () => {
    if (phase === "thinking") {
      sessionRef.current?.cancelResponse();
      setPhase("idle");
    }
  }, [phase]);

  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (drawer.isOpenNow()) return false;
      close();
      return true;
    });
    return () => sub.remove();
  }, [visible, drawer, close]);

  useEffect(() => {
    if (!liveTalkShouldCloseOnChatChange(turnChatIdRef.current, chatId)) return;
    close();
  }, [chatId, close]);

  useEffect(() => {
    if (!visible) return;
    const sub = AppState.addEventListener("change", (state) => {
      if (liveTalkShouldCloseOnAppState(state)) closeRef.current();
    });
    return () => sub.remove();
  }, [visible]);

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
    voicePlaying,
    muted,
    open,
    close,
    toggle,
    toggleMute,
  };
}
