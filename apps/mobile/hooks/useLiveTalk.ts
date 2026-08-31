import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, BackHandler } from "react-native";
import { useRouter } from "expo-router";

import { useDrawer } from "@/contexts/DrawerContext";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { api } from "@/lib/api";
import type { Message } from "@/lib/api";
import { isSseAbortError } from "@/lib/chatSse";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import {
  LIVE_TALK_ECHO_GUARD_MS,
  liveTalkAbortRefundNeeded,
  liveTalkCanTakeFloor,
  liveTalkDiscardListenOnMute,
  liveTalkErrorGate,
  liveTalkGate,
  liveTalkOrbAction,
  liveTalkSilenceDecision,
  type LiveTalkGate,
  type LiveTalkPhase,
  type LiveTalkStatus,
} from "@/lib/liveTalkLogic";
import { applyLiveTalkChatEvent, type LiveTalkSpeakEvent } from "@/lib/liveTalkEvents";
import {
  beginSpeechPlayback,
  playSpeechAudioClip,
  stopSpeaking,
  type SpeakResult,
} from "@/lib/pronunciation";
import { isVoiceInputAvailable, readRecordingBase64, speechUploadFromUri } from "@/lib/voiceAudio";

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
  const phaseRef = useRef(phase);
  const visibleRef = useRef(false);
  const mutedRef = useRef(false);
  const sessionGen = useRef(0);
  const heardSpeechRef = useRef(false);
  const silenceStartedAtRef = useRef<number | null>(null);
  const recordingStartedAtRef = useRef(0);
  const endingUtteranceRef = useRef(false);
  const autoListenRef = useRef(false);
  const emptyStreakRef = useRef(0);
  const speakAbortRef = useRef<AbortController | null>(null);

  phaseRef.current = phase;
  visibleRef.current = visible;
  mutedRef.current = muted;

  const alertForGate = useCallback(
    (gate: LiveTalkGate, opts?: { overModal?: boolean }) => {
      if (gate === "upgrade") {
        onUpgrade();
        return;
      }
      const overModal = opts?.overModal === true;
      const message =
        gate === "limit"
          ? t("chat.live_talk_limit_body")
          : gate === "offline"
            ? t("chat.offline_body")
            : t("chat.live_talk_unavailable_body");
      if (overModal) {
        const title =
          gate === "limit"
            ? t("chat.live_talk_limit_title")
            : gate === "offline"
              ? t("common.error")
              : t("chat.live_talk_unavailable_title");
        Alert.alert(title, message);
        return;
      }
      reportRecoverableError(feedback, message);
    },
    [feedback, onUpgrade, t],
  );

  const voice = useVoiceInput({
    token,
    t,
    recordingFormat: "wav",
    onTranscript: () => undefined,
    onTranscribeError: () => undefined,
  });

  const startRecordingRef = useRef(voice.startRecording);
  const cancelRecordingRef = useRef(voice.cancelRecording);
  startRecordingRef.current = voice.startRecording;
  cancelRecordingRef.current = voice.cancelRecording;

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

  const applyChatEvent = useCallback(
    (turnId: string, event: LiveTalkSpeakEvent) => {
      setMessages((prev) => applyLiveTalkChatEvent(prev, turnId, event));
      if (event.type === "done") {
        newMessageCountRef.current += 2;
        onScrollToLatest();
      }
    },
    [newMessageCountRef, onScrollToLatest, setMessages],
  );

  const beginListen = useCallback(async () => {
    if (!token || isOffline || !visibleRef.current || mutedRef.current) return;
    if (phaseRef.current === "recording" || phaseRef.current === "thinking") return;
    heardSpeechRef.current = false;
    silenceStartedAtRef.current = null;
    recordingStartedAtRef.current = Date.now();
    const started = await startRecordingRef.current();
    if (!started) return;
    if (!visibleRef.current || mutedRef.current) {
      void cancelRecordingRef.current();
      return;
    }
    setPhase("recording");
  }, [token, isOffline]);

  const finishListen = useCallback(async () => {
    if (!token || endingUtteranceRef.current) return;
    endingUtteranceRef.current = true;
    const gen = sessionGen.current;
    setPhase("thinking");
    const uri = await cancelRecordingRef.current();
    if (sessionGen.current !== gen) {
      endingUtteranceRef.current = false;
      return;
    }
    if (!uri) {
      endingUtteranceRef.current = false;
      emptyStreakRef.current += 1;
      autoListenRef.current = emptyStreakRef.current < 3;
      setPhase("idle");
      return;
    }
    const audioBase64 = await readRecordingBase64(uri);
    if (sessionGen.current !== gen) {
      endingUtteranceRef.current = false;
      return;
    }
    if (!audioBase64) {
      endingUtteranceRef.current = false;
      emptyStreakRef.current += 1;
      autoListenRef.current = emptyStreakRef.current < 3;
      setPhase("idle");
      return;
    }
    emptyStreakRef.current = 0;
    const abort = new AbortController();
    speakAbortRef.current = abort;
    let gotAudio = false;
    try {
      const turnChatId = await ensureChatId();
      if (sessionGen.current !== gen) {
        endingUtteranceRef.current = false;
        return;
      }
      const turnId = String(Date.now());
      let playbackGen = 0;
      let playbackStarted = false;
      let playChain: Promise<SpeakResult> = Promise.resolve({ ok: true });
      await api.liveTalkSpeak({
        token,
        audioBase64,
        filename: speechUploadFromUri(uri).name,
        chatId: turnChatId,
        signal: abort.signal,
        onEvent: (event: LiveTalkSpeakEvent) => {
          if (sessionGen.current !== gen) return;
          applyChatEvent(turnId, event);
          if (event.type === "done") {
            setStatus({
              enabled: true,
              entitled: true,
              remaining: event.remaining,
              limit: event.limit,
            });
            onFirstReply(turnChatId);
          }
          if (event.type !== "audio") return;
          gotAudio = true;
          if (!playbackStarted) {
            playbackStarted = true;
            playbackGen = beginSpeechPlayback();
            setPhase("speaking");
          }
          const clip = event;
          playChain = playChain.then(() => {
            if (sessionGen.current !== gen) return { ok: true };
            return playSpeechAudioClip(clip.audio_base64, clip.content_type, playbackGen);
          });
        },
      });
      if (sessionGen.current !== gen) {
        endingUtteranceRef.current = false;
        return;
      }
      const played = await playChain;
      if (sessionGen.current !== gen) {
        endingUtteranceRef.current = false;
        return;
      }
      if (playbackStarted && !played.ok) {
        Alert.alert(t("chat.read_aloud_unavailable_title"), t("chat.read_aloud_unavailable_body"));
      } else if (playbackStarted) {
        await new Promise((resolve) => setTimeout(resolve, LIVE_TALK_ECHO_GUARD_MS));
        if (sessionGen.current !== gen) {
          endingUtteranceRef.current = false;
          return;
        }
      }
      autoListenRef.current = !mutedRef.current;
      setPhase("idle");
    } catch (error) {
      const aborted =
        isSseAbortError(error) ||
        (error instanceof Error &&
          (error.name === "AbortError" || error.name === "CanceledError"));
      if (aborted && liveTalkAbortRefundNeeded(gotAudio)) {
        void api.refundLiveTalkTurn(token);
      }
      if (sessionGen.current !== gen || aborted) {
        endingUtteranceRef.current = false;
        return;
      }
      alertForGate(liveTalkErrorGate(error), { overModal: true });
      setPhase("idle");
    } finally {
      if (speakAbortRef.current === abort) speakAbortRef.current = null;
      endingUtteranceRef.current = false;
    }
  }, [token, alertForGate, t, ensureChatId, applyChatEvent, onFirstReply]);

  const close = useCallback(() => {
    sessionGen.current += 1;
    speakAbortRef.current?.abort();
    speakAbortRef.current = null;
    stopSpeaking();
    endingUtteranceRef.current = false;
    autoListenRef.current = false;
    void cancelRecordingRef.current();
    setPhase("idle");
    setMuted(false);
    setVisible(false);
  }, []);

  const open = useCallback(async () => {
    if (!token) return;
    if (!isVoiceInputAvailable() || !voice.voiceInputAvailable) {
      reportRecoverableError(feedback, t("chat.live_talk_unavailable_body"));
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
      sessionGen.current += 1;
      emptyStreakRef.current = 0;
      autoListenRef.current = true;
      setMuted(false);
      setPhase("idle");
      setVisible(true);
    } catch (error) {
      alertForGate(liveTalkErrorGate(error));
    }
  }, [token, isOffline, voice.voiceInputAvailable, t, alertForGate, feedback]);

  const toggle = useCallback(async () => {
    const action = liveTalkOrbAction(phase);
    if (action === "none") return;
    if (action === "cancelThink") {
      sessionGen.current += 1;
      speakAbortRef.current?.abort();
      speakAbortRef.current = null;
      endingUtteranceRef.current = false;
      autoListenRef.current = !mutedRef.current;
      setPhase("idle");
      return;
    }
    if (action === "finishListen") {
      await finishListen();
      return;
    }
    await beginListen();
  }, [phase, finishListen, beginListen]);

  const toggleMute = useCallback(() => {
    if (mutedRef.current) {
      mutedRef.current = false;
      setMuted(false);
      if (phaseRef.current === "idle" && visibleRef.current) {
        autoListenRef.current = true;
        void beginListen();
      }
      return;
    }
    mutedRef.current = true;
    setMuted(true);
    autoListenRef.current = false;
    if (liveTalkDiscardListenOnMute(phaseRef.current)) {
      sessionGen.current += 1;
      endingUtteranceRef.current = false;
      speakAbortRef.current?.abort();
      speakAbortRef.current = null;
      void cancelRecordingRef.current();
      setPhase("idle");
    }
  }, [beginListen]);

  const interrupt = useCallback(() => {
    if (!liveTalkCanTakeFloor(phase)) return;
    sessionGen.current += 1;
    speakAbortRef.current?.abort();
    speakAbortRef.current = null;
    stopSpeaking();
    autoListenRef.current = !mutedRef.current;
    void cancelRecordingRef.current();
    setPhase("idle");
  }, [phase]);

  const yieldToComposer = useCallback(() => {
    if (!visibleRef.current) return;
    sessionGen.current += 1;
    speakAbortRef.current?.abort();
    speakAbortRef.current = null;
    stopSpeaking();
    endingUtteranceRef.current = false;
    autoListenRef.current = false;
    void cancelRecordingRef.current();
    setPhase("idle");
  }, []);

  useEffect(() => {
    if (!visible || phase !== "idle" || !autoListenRef.current) return;
    autoListenRef.current = false;
    void beginListen();
  }, [visible, phase, beginListen]);

  useEffect(() => {
    if (phase !== "recording") return;
    const next = liveTalkSilenceDecision({
      meter: voice.voiceMeterLevel,
      now: Date.now(),
      recordingStartedAt: recordingStartedAtRef.current,
      heardSpeech: heardSpeechRef.current,
      silenceStartedAt: silenceStartedAtRef.current,
    });
    heardSpeechRef.current = next.heardSpeech;
    silenceStartedAtRef.current = next.silenceStartedAt;
    if (next.shouldStop) void finishListen();
  }, [phase, voice.voiceMeterLevel, finishListen]);

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
    return () => {
      stopSpeaking();
    };
  }, []);

  return {
    visible,
    phase,
    meterLevel: voice.voiceMeterLevel,
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
